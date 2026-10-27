"""Deterministic RCC register map: generate the LL register definitions from RM0486 and check conformance.

Why: qwen3:8b invents register offsets and bit masks (r13: per-bit "offsets", LSEON at 0x1). Register
definitions are data, not design: like vendor device headers generated from register descriptions, they
are produced here deterministically from the work-order's RM0486 section files, for exactly the registers
the inspected SWE.2 register table names. The LL author then writes only the inline access functions.
`check_regmap` verifies every LL_RCC_<REG>_OFFSET / _<FIELD>_POS / _<FIELD>_MSK define against the RM.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from ..common import sha256_file, utc_now
from .architecture import ARCH, SECTIONS_DIR, _rows, _sections

LL_HEADER = "software/ll/stm32n6xx_ll_rcc.h"
GUARD = "STM32N6XX_LL_RCC_H"
FUNCTIONS_MARKER = "// LL_RCC access functions (SWE.3 LL author)"  # line comment: a dropped '*/' cannot hide code
_BIT = re.compile(r"^\s*Bits?\s+(\d+)(?::(\d+))?\s+([A-Z][A-Z0-9_]*)(?:\[\d+(?::\d+)?\])?\s*:", re.M)
# feature 015: one line for all pins of a port, field y of width (msb-lsb+1)/pins (GPIO MODEy, BSy, BRy, AFSELy)
_PIN = re.compile(r"^\s*Bits?\s+(\d+):(\d+)\s+([A-Z][A-Z0-9_]*?)y(?:\[\d+(?::\d+)?\])?\s*:.*?\(y\s*=\s*(\d+)\s+to\s+(\d+)\)",
                  re.M)
# CAPA-050 (LL r166): a table row may name the register alone (RCC_CR) or with its field (RCC_CR.HSION, RCC_CR[HSION],
# `RCC_CR`); the register is the leading RCC_ name. A '_' joined name (RCC_CR_HSION) stays one name: NOT_IN_RM.
_REG_CELL = re.compile(r"`?(RCC_[A-Z0-9_]+)`?(?:$|[\s.\[(:/,])")


def _ident(ws: Path | None) -> dict:
    """Feature 009: peripheral identity of the workspace (RCC when the manifest names none)."""
    from ..layer import profile

    p = profile(ws)
    pfx = p["register_prefix"]
    return {"prefix": pfx, "define": p["ll"]["function_prefix"], "header": f"software/ll/{p['ll']['header']}",
            "guard": f"STM32N6XX_LL_{pfx}_H", "marker": f"// LL_{pfx} access functions (SWE.3 LL author)",
            "block": p["ll"]["register_block"], "count": p["ll"]["register_count"], "base": p["base_address"],
            "cell": re.compile(rf"`?({pfx}_[A-Z0-9_]+)`?(?:$|[\s.\[(:/,])")}


def functions_marker(ws: Path | None = None) -> str:
    return _ident(ws)["marker"]


def _register_name(text: str, prefix: str) -> str | None:
    name = re.search(rf"^#+ .*\(({prefix}_[A-Z0-9_]+)\)\s*$", text, re.M)
    if name or prefix == "RCC":  # RCC results unchanged (its wrapped headings stay unparsed, as the pilots saw them)
        return name.group(1) if name else None
    # feature 015 (F015-T040): a multi-instance register is named by its placeholder (GPIOx_MODER, TIMx_CR1), maybe
    # with its instances "(x = A to H, N to Q)" / "(x = 2 to 5)", and the name may wrap onto the first lines after the
    # heading; it is normalised to the CMSIS form (GPIO_MODER, TIM_CR1)
    head = "\n".join(text.splitlines()[:6])
    m = re.search(rf"^(?:#+ .*|[ \t]*)\(({prefix})x?(_[A-Z0-9_]+)\)\s*(?:\(\s*x\s*=[^)]*\)\s*)?$", head, re.M)
    return m.group(1) + m.group(2) if m else None


def parse_section(text: str, prefix: str = "RCC") -> dict | None:
    name = _register_name(text, prefix)
    off = re.search(r"Address offset:\s*(0x[0-9a-fA-F]+)", text)
    if not (name and off):
        return None
    reset = re.search(r"Reset value:\s*(0x[0-9a-fA-F]{4}\s?[0-9a-fA-F]{4})", text)
    if prefix != "RCC":  # feature 015: per-port values (GPIO: Port A's, the benchmark instance GPIOA, comes first)
        # and 16-bit registers (TIMx_CR1 'Reset value: 0x0000')
        reset = re.search(r"Reset value:\s*Port [A-Z]:\s*(0x[0-9a-fA-F]{4}\s?[0-9a-fA-F]{4})", text) or reset or \
            re.search(r"Reset value:\s*(0x[0-9a-fA-F]{4})\s*$", text, re.M)
    fields: dict[str, tuple[int, int]] = {}
    for m in _BIT.finditer(text):
        msb = int(m.group(1))
        lsb = int(m.group(2)) if m.group(2) else msb
        if msb < lsb or msb > 31:
            continue
        fields.setdefault(m.group(3), (msb, lsb))
    for m in _PIN.finditer(text):  # 'Bits 31:0 MODEy[1:0]: ... pin y (y = 15 to 0)': MODE0..MODE15, 2 bits each
        msb, lsb, base = int(m.group(1)), int(m.group(2)), m.group(3)
        n = abs(int(m.group(4)) - int(m.group(5))) + 1
        y0 = min(int(m.group(4)), int(m.group(5)))  # GPIOx_AFRH: AFSELy (y = 15 to 8) starts at pin 8
        width = (msb - lsb + 1) // n if msb >= lsb else 0
        if width and width * n == msb - lsb + 1:
            for y in range(n):
                fields.setdefault(f"{base}{y0 + y}", (lsb + (y + 1) * width - 1, lsb + y * width))
    return {"name": name, "offset": int(off.group(1), 16),
            "reset": reset.group(1).replace(" ", "") if reset else None, "fields": fields}


def rm_registers(ws: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    d = ws / SECTIONS_DIR
    pfx = _ident(ws)["prefix"]
    for f in sorted(d.glob("*.md")) if d.is_dir() else []:
        reg = parse_section(f.read_text(errors="replace"), pfx)
        if reg and reg["name"] not in out:
            out[reg["name"]] = {**reg, "source": f.relative_to(ws).as_posix(), "sha256": sha256_file(f)}
    return out


def architecture_registers(ws: Path) -> list[str]:
    p = ws / ARCH
    if not p.is_file():
        return []
    body = next((b for h, b in _sections(p.read_text(errors="replace")).items() if re.search(r"register\s+table", h)), "")
    names = []
    cell = _ident(ws)["cell"]
    for row in _rows(body):
        m = cell.match(row[0].strip()) if row and row[0] else None
        if m and m.group(1) not in names:
            names.append(m.group(1))
    return names


def _short(reg: str) -> str:
    return reg.split("_", 1)[1]


def render(regs: list[dict], ws: Path | None = None) -> str:
    i = _ident(ws)
    guard, d, pfx = i["guard"], i["define"], i["prefix"]
    L = [f"#ifndef {guard}", f"#define {guard}", "",
         "/* Register definitions GENERATED by forge_factory.inspection.regmap from RM0486 section inputs",
         " * (" + ", ".join(f"{r['name']}: {Path(r['source']).name}" for r in regs) + ").",
         " * Do not edit the generated definitions; SWE.3 verification checks them against RM0486. */", "",
         "#include <stdint.h>", "",
         f"#define {d}REG_COUNT {i['count']}U",
         f"/* {pfx} register block, placed at the {pfx} base address ({i['base']}) by the linker; host tests define it. */",
         f"extern volatile uint32_t {i['block']}[{d}REG_COUNT];", ""]
    for r in regs:
        s = _short(r["name"])
        L.append(f"/* {r['name']} (RM0486 {Path(r['source']).name.split('_')[0]}) */")
        L.append(f"#define {d}{s}_OFFSET 0x{r['offset']:03X}U")
        for field, (msb, lsb) in sorted(r["fields"].items(), key=lambda kv: -kv[1][0]):
            mask = ((1 << (msb - lsb + 1)) - 1) << lsb
            L.append(f"#define {d}{s}_{field}_POS {lsb}U")
            L.append(f"#define {d}{s}_{field}_MSK 0x{mask:08X}U")
        L.append("")
    L += [i["marker"], "", f"#endif /* {guard} */", ""]
    return "\n".join(L)


def generate(ws: Path) -> dict:
    wanted = architecture_registers(ws)
    rm = rm_registers(ws)
    missing = [n for n in wanted if n not in rm]
    regs = [rm[n] for n in wanted if n in rm]
    from ..layer import layer_of, ll_tu, ll_tu_text

    LL_TU, LL_TU_TEXT = ll_tu(ws), ll_tu_text(ws)  # noqa: N806 - feature 009: per-peripheral names
    if layer_of(ws) == "LL":  # ADR-0009: compile unit of the header-only LL (build/analysis/size tools need one)
        # CAPA-050: written even when the map is BLOCKED, so no author writes its own unit (CAPA-046 rejects it and
        # the author has no tool to delete it: LL r166 ended BLOCKED on that loop)
        (ws / LL_TU).parent.mkdir(parents=True, exist_ok=True)
        (ws / LL_TU).write_text(LL_TU_TEXT, encoding="utf-8")
    if not regs:
        return {"status": "BLOCKED", "issues": ["NO_REGISTERS_FROM_SWE2_TABLE"] + [f"NOT_IN_RM:{n}" for n in missing]}
    i = _ident(ws)
    out = ws / i["header"]
    out.parent.mkdir(parents=True, exist_ok=True)
    text = render(regs, ws)
    if out.is_file():  # ADR-0008 re-entry (upstream loop): keep the authored access functions, regenerate the defines
        old = out.read_text(encoding="utf-8", errors="replace")
        end = f"#endif /* {i['guard']} */"
        if i["marker"] in old and end in old:
            authored = old.split(i["marker"], 1)[1].rsplit(end, 1)[0]
            text = text.replace(i["marker"] + "\n\n" + end, i["marker"] + authored + end)
    out.write_text(text, encoding="utf-8")
    rec = {"schema": "forge-c/regmap/0.4", "generated_at": utc_now(), "header": i["header"],
           "registers": {r["name"]: {"offset": r["offset"], "fields": len(r["fields"]), "source": r["source"],
                                     "source_sha256": r["sha256"]} for r in regs},
           "not_in_rm_inputs": missing}
    d = ws / "verification" / "static"
    d.mkdir(parents=True, exist_ok=True)
    (d / "register_map_generation.json").write_text(json.dumps(rec, indent=1, sort_keys=True))
    return {"status": "PASS" if not missing else "PARTIAL", "registers": len(regs), "issues":
            [f"NOT_IN_RM:{n}" for n in missing]}


def check_regmap(ws: Path) -> dict:
    """Every LL_RCC_<REG>_OFFSET/_<FIELD>_POS/_<FIELD>_MSK define in the LL header must match RM0486."""
    i = _ident(ws)
    p = ws / i["header"]
    if not p.is_file():
        return {"verdict": "FAIL", "major_findings": ["REGMAP:NO_LL_HEADER"], "stats": {}}
    rm = {_short(k): v for k, v in rm_registers(ws).items()}
    findings, checked = [], 0
    for m in re.finditer(rf"^\s*#\s*define\s+{re.escape(i['define'])}([A-Z0-9_]+?)_(OFFSET|POS|MSK)\s+\(?\s*"
                         r"(0x[0-9A-Fa-f]+|\d+)U?L?\b", p.read_text(errors="replace"), re.M):
        key, kind, val = m.group(1), m.group(2), int(m.group(3), 0)
        if kind == "OFFSET":
            if key not in rm:
                findings.append(f"REGMAP:OFFSET_FOR_UNKNOWN_REGISTER:{key}")
            elif rm[key]["offset"] != val:
                findings.append(f"REGMAP:OFFSET_MISMATCH:{key}:0x{val:X}!=0x{rm[key]['offset']:X}")
            checked += 1
            continue
        reg = next((r for r in sorted(rm, key=len, reverse=True) if key.startswith(r + "_")), None)
        field = key[len(reg) + 1:] if reg else None
        if reg is None or field not in rm[reg]["fields"]:
            findings.append(f"REGMAP:{kind}_FOR_UNKNOWN_FIELD:{key}")
            continue
        msb, lsb = rm[reg]["fields"][field]
        want = lsb if kind == "POS" else ((1 << (msb - lsb + 1)) - 1) << lsb
        if val != want:
            findings.append(f"REGMAP:{kind}_MISMATCH:{key}:{val:#x}!={want:#x}")
        checked += 1
    if checked == 0:
        findings.append("REGMAP:NO_REGISTER_DEFINES")
    return {"verdict": "FAIL" if findings else "PASS", "major_findings": findings, "stats": {"defines_checked": checked}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate the RCC LL register definitions from RM0486 inputs")
    ap.add_argument("--workspace", type=Path, default=Path("."))
    a = ap.parse_args(argv)
    res = generate(a.workspace.resolve())
    print(json.dumps(res))
    return 0 if res["status"] in ("PASS", "PARTIAL") else 1


if __name__ == "__main__":
    sys.exit(main())
