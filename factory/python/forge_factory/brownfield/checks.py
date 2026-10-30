"""OD-2026-10-20-02: the v0.4-brownfield SWE.3 checklist items, decided on the DELIVERED code.

* SWE3-07 `delivered_guideline`: forge style - the Cube2 rule subset (as greenfield); vendor style - the rule hits
  inside the scope functions (and file-level rules) are delivered-code findings for the owner.
* SWE3-08 `delivered_register_definitions`: forge style - the LL_<PPP>_ offset/mask defines (check_regmap); CMSIS
  style - static-assertion probes of the <PPP>_TypeDef member offsets and the <PPP>_<REG>_<FIELD>(_Msk|_Pos) masks the
  scope functions use, against the RM0486 register sections, compiled with the target compiler.
* SWE3-09 `delivered_implementation`: every SWE.2-allocated function exists in the delivered code, and the delivered
  fingerprints are unchanged (or changed only by a linked fix).

`findings(ws)` is what the SWE.3 verify node records in code_findings.json; `item(ws, check)` is the checklist verdict.
In FROZEN mode, and for vendor style, a finding is RECORDED (a package gap with an owner disposition), not a rework:
the item fails only when a finding is missing from the record, the probes cannot be built, or the fingerprints differ.
FIX_ALLOWED forge-style deliveries keep the greenfield verdicts (the author can fix them)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from ..common import pretty_json
from . import DELIVERY_DIR, code_mode, manifest_of, reference_paths
from . import scope as S

CHECKS = ("delivered_guideline", "delivered_register_definitions", "delivered_implementation")
FINDINGS = f"{DELIVERY_DIR}/code_findings.json"
REPORTS = {"delivered_guideline": "verification/static/delivered_guideline.json",
           "delivered_register_definitions": "verification/static/delivered_register_definitions.json",
           "delivered_implementation": "verification/static/delivered_implementation.json"}
PROBE = "FORGE_PROBE"


def style_of(m: dict) -> str:
    return (m.get("delivery") or {}).get("build", {}).get("style", "forge")


def _prefix(ws: Path) -> str:
    from ..layer import register_prefix

    return register_prefix(ws)


def _defs(ws: Path, m: dict) -> dict[str, S.Definition]:
    texts = {rel: (ws / rel).read_text(errors="replace") for rel in reference_paths(m) if (ws / rel).is_file()}
    return {d.name: d for rel in reversed(list(texts)) for d in S.index(texts[rel], rel)}  # delivered wins


def _macros(ws: Path, m: dict) -> set[str]:
    """Names the delivered code #defines (constants and function-like macros)."""
    return {n for rel in reference_paths(m) if (ws / rel).is_file()
            for n in re.findall(r"^[ \t]*#[ \t]*define[ \t]+([A-Za-z_]\w*)", (ws / rel).read_text(errors="replace"), re.M)}


def undelivered(allocated: set[str], defs, macros: set[str]) -> list[str]:
    """F015 GPIO-R3: SWE.2 rows name the parameter constants next to a function (SWR-012 | LL_GPIO_SetPinPull |
    LL_GPIO_PULL_NO=0, ...); a name the delivered code #defines is delivered, not a missing function."""
    return [f"ALLOCATED_NOT_DELIVERED:{f}" for f in sorted(allocated) if f not in defs and f not in macros]


def _scope(ws: Path) -> list[dict]:
    p = ws / DELIVERY_DIR / "scope.json"
    return json.loads(p.read_text()).get("functions", []) if p.is_file() else []


def _reached(names: list[str], defs: dict[str, S.Definition], depth: int = 4) -> list[S.Definition]:
    """The scope definitions and the delivered definitions they call (up to `depth` levels)."""
    seen: dict[str, S.Definition] = {}
    todo = [(n, 0) for n in names]
    while todo:
        n, d = todo.pop()
        if n in seen or n not in defs:
            continue
        seen[n] = defs[n]
        if d < depth:
            todo += [(c, d + 1) for c in re.findall(r"\b([A-Za-z_]\w*)\s*\(", defs[n].body)]
    return list(seen.values())


# ---- SWE3-07 ---------------------------------------------------------------------------------------------------
def guideline(ws: Path, m: dict) -> dict:
    from ..inspection.guideline import check_workspace

    rep = check_workspace(ws)
    if style_of(m) == "forge":
        hits = rep["violations"]
    else:  # vendor code: only the delivered scope (plus file-level rules) is the work order's subject
        spans: dict[str, list[tuple[int, int]]] = {}
        defs = _defs(ws, m)
        for f in _scope(ws):
            d = defs.get(f["name"])
            if d is not None:
                spans.setdefault(d.file, []).append((d.line, d.line + d.body.count("\n") + 1))
        hits = [v for v in rep["violations"] if v.get("file") in spans and (
            not v.get("line") or any(a <= int(v["line"]) <= b for a, b in spans[v["file"]]))]
    return {"check": "delivered_guideline", "style": style_of(m), "guideline_verdict": rep["verdict"],
            "guideline": rep.get("guideline"), "guideline_sha256": rep.get("guideline_sha256"),
            "files_checked": rep.get("files_checked"), "violations_total": len(rep["violations"]),
            "findings": sorted(f"GUIDELINE:{v['rule']}:{v.get('file', '')}:{v.get('line', '')}" for v in hits)}


# ---- SWE3-08 ---------------------------------------------------------------------------------------------------
def _expected_mask(token: str, reg: str, field: str, rm: dict) -> tuple[str, int] | None:
    """('mask'|'pos', value) the RM gives for <PPP>_<REG>_<FIELD>[_Msk|_Pos|_<n>], None when the field is unknown."""
    fields = rm[reg]["fields"]
    kind = "pos" if token.endswith("_Pos") else "mask"
    f = re.sub(r"_(Msk|Pos)$", "", field)
    bit = None
    if f not in fields and re.fullmatch(r".+_\d+", f) and f.rsplit("_", 1)[0] in fields:  # one bit of a field: SYSSW_0
        f, bit = f.rsplit("_", 1)[0], int(f.rsplit("_", 1)[1])
    if f not in fields and "_" in f:  # F015: CMSIS joins the names one bit has in the RM's alternate sections
        known = [x for x in f.split("_") if x in fields]  # (USART_ISR_RXNE_RXFNE: RXNE FIFO disabled, RXFNE enabled)
        if known and all(fields[x] == fields[known[0]] for x in known):
            f = known[0]
    if f not in fields and f"{f}0" in fields:  # F015: a field the RM splits (USART_CR1_M = M0 bit 12 | M1 bit 28)
        parts = [fields[f"{f}{i}"] for i in range(8) if f"{f}{i}" in fields]
        if kind == "pos":
            return ("pos", min(lsb for _, lsb in parts))
        return ("mask", sum(((1 << (msb - lsb + 1)) - 1) << lsb for msb, lsb in parts))
    if f not in fields:
        return None
    msb, lsb = fields[f]
    if kind == "pos":
        return ("pos", lsb + (bit or 0))
    if bit is not None:
        return ("mask", 1 << (lsb + bit))
    return ("mask", ((1 << (msb - lsb + 1)) - 1) << lsb)


def register_definitions(ws: Path, m: dict) -> dict:
    if style_of(m) == "forge":
        from ..inspection.regmap import check_regmap

        rep = check_regmap(ws)
        return {"check": "delivered_register_definitions", "style": "forge", "build": "NOT_APPLICABLE",
                "findings": sorted(f"REGISTER_MAP:{x}" for x in rep["major_findings"]), "probes": 0}
    from ..inspection.regmap import rm_registers

    pfx = _prefix(ws)
    rm = rm_registers(ws)
    defs = _defs(ws, m)
    bodies = "\n".join(d.body for d in _reached([f["name"] for f in _scope(ws)], defs))
    regs = sorted(set(re.findall(rf"\b{pfx}\s*->\s*([A-Z][A-Z0-9_]*)", bodies))  # LL: CRCx->CR; ST HAL: the
                  | set(re.findall(r"->\s*Instance\s*->\s*([A-Z][A-Z0-9_]*)", bodies)))  # handle, hcrc->Instance->CR
    tokens = sorted(set(re.findall(rf"\b({pfx}_[A-Z][A-Z0-9]*_[A-Za-z0-9_]+)\b", bodies)))
    findings, probes = [], []
    for r in regs:
        if f"{pfx}_{r}" not in rm:
            findings.append(f"REGISTER_NOT_IN_RM:{pfx}_{r}")
        else:
            probes.append((f"offset {pfx}_{r}", f"offsetof({pfx}_TypeDef, {r}) == {rm[f'{pfx}_{r}']['offset']:#x}U"))
    for t in tokens:
        reg, field = t[len(pfx) + 1:].split("_", 1)
        if f"{pfx}_{reg}" not in rm:  # not a register field token (e.g. a peripheral base or an instance name)
            continue
        exp = _expected_mask(t, f"{pfx}_{reg}", field, rm)
        if exp is None:
            findings.append(f"FIELD_NOT_IN_RM:{t}")
        else:
            probes.append((f"{exp[0]} {t}", f"({t}) == {exp[1]:#x}UL"))
    build = "NOT_RUN"
    log = ""
    if probes:
        build, log, failed = _probe(ws, m, probes)
        findings += [f"REGISTER_DEFINITION_MISMATCH:{p}" for p in failed]
    return {"check": "delivered_register_definitions", "style": style_of(m), "build": build,
            "probes": len(probes), "registers": regs, "tokens": tokens, "findings": sorted(findings), "log": log[-3000:]}


def _probe(ws: Path, m: dict, probes: list[tuple[str, str]]) -> tuple[str, str, list[str]]:
    gcc = shutil.which("arm-none-eabi-gcc")
    if not gcc:
        return "NOT_RUN", "arm-none-eabi-gcc not found on PATH", []
    b = (m.get("delivery") or {}).get("build", {})
    out = ws / "verification/static/register_probes.c"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("#include <stddef.h>\n#include <stdint.h>\n#include \"stm32n6xx.h\"\n" + "".join(
        f'_Static_assert({expr}, "{PROBE} {i} {label}");\n' for i, (label, expr) in enumerate(probes)))
    cmd = [gcc, "-std=c11", "-fsyntax-only", "-mcpu=cortex-m55", "-mthumb", *(["-mcmse"] if b.get("secure") else []),
           f"-I{ws / 'inputs/vendor/include'}", *[f"-D{d}" for d in b.get("defines") or []], str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=False)
    log = (r.stdout + r.stderr).replace(str(ws), "<ws>")
    failed = sorted(set(re.findall(rf'"{PROBE} \d+ ([^"]+)"', log)))
    other = [ln for ln in log.splitlines() if ": error:" in ln and PROBE not in ln]
    if r.returncode != 0 and (other or not failed):
        return "FAIL", log, failed
    return "PASS", log, failed


# ---- SWE3-09 ---------------------------------------------------------------------------------------------------
def implementation(ws: Path, m: dict) -> dict:
    from .conformance import ARCH
    from .verify import verify

    defs = _defs(ws, m)
    arch = ws / ARCH
    allocated: set[str] = set()
    if arch.is_file():
        from ..assurance.oracle_gen import allocation
        from ..layer import profile

        pr = profile(ws)
        names = {f["name"] for f in _scope(ws)}
        pfx = (pr["hal"]["function_prefix"], pr["ll"]["function_prefix"])
        allocated = {f for fns in allocation(arch.read_text(errors="replace"), names, pfx).values() for f in fns}
    v = verify(ws, "swe3_verify")
    findings = undelivered(allocated, defs, _macros(ws, m))
    return {"check": "delivered_implementation", "allocated": sorted(allocated), "delivery": v["status"],
            "fingerprint_issues": v["issues"], "findings": findings + [f"DELIVERY:{i}" for i in v["issues"]]}


RUN = {"delivered_guideline": guideline, "delivered_register_definitions": register_definitions,
       "delivered_implementation": implementation}


def findings(ws: Path, write: bool = True) -> dict:
    """All three checks; the SWE.3 verify node records them (code_findings.json) and writes their reports."""
    ws = Path(ws)
    m = manifest_of(ws)
    out = {}
    for name, fn in RUN.items():
        rep = fn(ws, m)
        out[name] = rep
        if write:
            (ws / REPORTS[name]).parent.mkdir(parents=True, exist_ok=True)
            (ws / REPORTS[name]).write_text(pretty_json(rep))
    return out


def item(ws: Path, check: str) -> dict:
    """Checklist verdict of one v0.4-brownfield item (engine deterministic item)."""
    ws = Path(ws)
    m = manifest_of(ws)
    rep = RUN[check](ws, m)
    mode, style = code_mode(m), style_of(m)
    fixable = mode == "FIX_ALLOWED" and style == "forge"
    try:
        recorded = set((json.loads((ws / FINDINGS).read_text()).get("code_checks") or {}).get("findings") or [])
    except (OSError, ValueError):
        recorded = set()
    major = []
    if check == "delivered_register_definitions" and rep.get("build") == "FAIL":
        major.append("REGISTER_PROBES_NOT_BUILT")
    if check == "delivered_register_definitions" and rep.get("build") == "NOT_RUN" and rep.get("probes"):
        major.append("REGISTER_PROBES_NOT_RUN")
    if check == "delivered_implementation" and rep["fingerprint_issues"]:
        major += [f"DELIVERY:{i}" for i in rep["fingerprint_issues"]]
    if fixable:
        major += [f for f in rep["findings"] if f not in major]
    else:
        major += [f"NOT_RECORDED:{f}" for f in rep["findings"] if f not in recorded and not f.startswith("DELIVERY:")]
    return {"verdict": "FAIL" if major else "PASS", "major_findings": major, "recorded_findings":
            [f for f in rep["findings"] if f in recorded], "code_mode": mode, "style": style, "report": rep}
