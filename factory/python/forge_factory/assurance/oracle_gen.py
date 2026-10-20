"""EASA-T040/T041 and AT-040 — independent test oracles derived from frozen requirements + the baselined RM.

For every SWR of the form "When <trigger>, the <driver> shall set|clear RCC_<REG>.<FIELD>" the allocated function
(SWE.2 allocation table) is exercised and the expected register effect is computed from the RM index: register word
from the RM offset, bit from the RM field position, and "all other bits keep their value". The generated C test
uses ONLY literal RM constants (never the generated LL macros), counts register accesses through a shim, and is
compiled against the implementation under test. The oracle's provenance (requirements digest, RM section digests,
author role oracle-builder, implementation not seen) is recorded and assessed by `oracle.assess`.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
from pathlib import Path

from . import hardware, oracle

SET_CLEAR = re.compile(r"When (?P<trig>.+?), the [\w ]+? shall (?P<op>set|clear) (?P<reg>RCC_[A-Z0-9]+)\.(?P<fld>[A-Z0-9_]+)")
SHIM = ("#include <stdint.h>\nvolatile uint32_t (*shim_regs(void))[1024];\n#define ll_rcc_regs (*shim_regs())\n")


def shim_text(block: str = "ll_rcc_regs", count: int = 1024) -> str:
    """Feature 009: the oracle's register-block shim for the work order's peripheral (RCC: SHIM)."""
    return SHIM.replace("ll_rcc_regs", block).replace("[1024]", f"[{count}]")


def allocation(arch_md: str, names: set[str] | None = None, prefixes: tuple[str, ...] = ("HAL_RCC_", "LL_RCC_")
               ) -> dict[str, list[str]]:
    """SWR -> allocated API functions, from the rows of the SWE.2 architecture tables. `names`: further function
    names to recognise (feature 008: the delivered scope functions, e.g. ST's LL_AHB1_GRP1_EnableClock)."""
    out: dict[str, list[str]] = {}
    for line in arch_md.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        swrs = re.findall(r"\bSWR-\d{3}\b", line)
        fns = re.findall(r"\b((?:" + "|".join(re.escape(x) for x in prefixes) + r")[A-Za-z0-9_]+)\b", line)
        fns += [w for w in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", line) if names and w in names and w not in fns]
        fns = [f for f in fns if not re.search(r"_(OFFSET|MSK|POS|VALUE)$", f)]
        for s in swrs:
            out.setdefault(s, [])
            out[s] += [f for f in fns if f not in out[s]]
    return out


def prototypes(header: str) -> dict[str, str]:
    """Function name -> parameter list (from prototypes or static inline definitions)."""
    return {m.group(1): m.group(2).strip() for m in re.finditer(r"\b((?:HAL|LL)_RCC_\w+)\s*\(([^)]*)\)\s*[;{]", header)}


SELECTED = re.compile(r"When (?P<trig>.+?), the [\w ]+? shall (?P<op>set|clear) the selected (?P<kind>enable|reset) bit "
                      r"of (?P<reg>RCC_[A-Z0-9]+)")


def _selected(sid: str, sel: re.Match, fns: list[str], protos: dict[str, str], idx: dict[str, dict],
              notes: list[str]) -> list[dict]:
    """HAL_RCC_<P>_Enable/_Disable -> <P>EN, _Reset/_ReleaseReset -> <P>RST (or LL_RCC_<P>_ForceReset...) of the
    register the requirement names; the bit position comes from the RM index."""
    reg = idx.get(sel["reg"])
    out = []
    if reg is None:
        notes.append(f"ORACLE_NOT_DERIVABLE:{sid}:{sel['reg']} not in RM")
        return out
    suffix = "EN" if sel["kind"] == "enable" else "RST"
    for fn in fns:
        m = re.match(r"(?:HAL|LL)_RCC_([A-Z0-9]+)_(\w+)$", fn)
        if not m or fn not in protos or "*" in protos[fn]:
            continue
        fld = reg["fields"].get(m.group(1) + suffix)
        if fld is None:
            notes.append(f"ORACLE_NOT_DERIVABLE:{sid}:{m.group(1) + suffix} not a field of {sel['reg']}")
            continue
        mask = ((1 << (fld["msb"] - fld["lsb"] + 1)) - 1) << fld["lsb"]
        out.append({"swr": sid, "function": fn, "params": protos[fn], "op": sel["op"], "word": reg["offset"] // 4,
                    "mask": mask, "register": sel["reg"], "field": m.group(1) + suffix, "ready": None})
    return out


def derive(requirements_md: str, arch_md: str, header: str, idx: dict[str, dict]) -> tuple[list[dict], list[str]]:
    alloc, protos = allocation(arch_md), prototypes(header)
    cases, notes = [], []
    for m in re.finditer(r"\*\*(SWR-\d{3})\*\*\s*(.+)", requirements_md):
        sid, text = m.group(1), m.group(2)
        sm = SET_CLEAR.search(text)
        if not sm:
            sel = SELECTED.search(text)
            if sel:  # "set the selected enable bit of RCC_AHB1ENR": field from the SWE.2 API name contract
                cases += _selected(sid, sel, alloc.get(sid, []), protos, idx, notes)
            continue
        reg, fld = idx.get(sm["reg"]), sm["fld"]
        if reg is None or fld not in reg["fields"]:
            notes.append(f"ORACLE_NOT_DERIVABLE:{sid}:{sm['reg']}.{fld} not in RM")
            continue
        f = reg["fields"][fld]
        mask = ((1 << (f["msb"] - f["lsb"] + 1)) - 1) << f["lsb"]
        fns = [x for x in alloc.get(sid, []) if x in protos and "*" not in protos[x]]
        for x in alloc.get(sid, []):  # dry-run FP r96: a struct-pointer argument is not derivable from requirements
            if x in protos and "*" in protos[x]:
                notes.append(f"ORACLE_NOT_DERIVABLE:{sid}:{x} takes a pointer argument")
        if not fns:
            notes.append(f"ORACLE_NOT_DERIVABLE:{sid}:no allocated function with a prototype")
            continue
        ready = None
        if sm["op"] == "set" and fld.endswith("ON") and "RCC_SR" in idx:
            rdy = idx["RCC_SR"]["fields"].get(fld[:-2] + "RDY")
            if rdy:
                ready = (idx["RCC_SR"]["offset"] // 4, 1 << rdy["lsb"])
        for fn in fns:
            cases.append({"swr": sid, "function": fn, "params": protos[fn], "op": sm["op"], "word": reg["offset"] // 4,
                          "mask": mask, "register": sm["reg"], "field": fld, "ready": ready})
    return cases, notes


TIMEOUT_RQ = re.compile(r"does not set within .*?(?P<n>HAL_RCC_TIMEOUT_VALUE|\d+).*?shall clear the enable bit.*?"
                        r"return HAL_TIMEOUT", re.I)
INVALID_RQ = re.compile(r"invalid parameter.*?shall return HAL_ERROR without any register write.*?timeout argument of 0 "
                        r"or greater than (?P<max>HAL_RCC_TIMEOUT_VALUE|\d+)", re.I | re.S)


def derive_timeouts(requirements_md: str, header: str, idx: dict[str, dict]) -> list[dict]:
    """Timeout/rollback (SWR-013/015 style) and invalid-timeout (SWR-014 style) cases for every oscillator enable
    with a timeout parameter. Expected values: the requirement text and the RM bit positions; HAL_TIMEOUT/HAL_ERROR
    are the API contract symbols of the interface header (SWE.2), not implementation behaviour."""
    out = []
    protos = prototypes(header)
    has_to = any(TIMEOUT_RQ.search(m.group(0)) for m in re.finditer(r"\*\*SWR-\d{3}\*\*.+", requirements_md))
    inv = INVALID_RQ.search(requirements_md)
    cr, sr = idx.get("RCC_CR"), idx.get("RCC_SR")
    for fn, params in sorted(protos.items()):
        m = re.match(r"HAL_RCC_(\w+?)_Enable$", fn)
        if not (m and cr and re.search(r"uint32_t\s+\w+", params or "")) or "*" in (params or ""):
            continue
        on = cr["fields"].get(m.group(1) + "ON")
        if on is None:
            continue
        mask = 1 << on["lsb"]
        if has_to:
            out.append({"kind": "timeout", "function": fn, "word": cr["offset"] // 4, "mask": mask,
                        "sr_word": (sr or {"offset": 4})["offset"] // 4, "t": 5})
        if inv:
            out.append({"kind": "invalid", "function": fn, "arg": "0U"})
            out.append({"kind": "invalid", "function": fn, "arg": "HAL_RCC_TIMEOUT_VALUE + 1U"})
    return out


def timeout_source(cases: list[dict], start: int) -> list[str]:
    lines = []
    for i, c in enumerate(cases, start):
        if c["kind"] == "timeout":
            lines += [f"    /* rollback + bound: ready never set, timeout {c['t']} (requirement text, RM bit) */",
                      "    memset((void *)regs, 0, sizeof regs); shim_n = 0UL;",
                      f"    {{ hal_status_t st = {c['function']}({c['t']}U);",
                      f"      int ok = (st == HAL_TIMEOUT) && ((regs[{c['word']}U] & 0x{c['mask']:08X}U) == 0U)"
                      f" && (shim_n <= {c['t'] + 2}UL) && (shim_n >= 2UL);",
                      f'      printf("OR-{i:03d} TIMEOUT {c["function"]} %s\\n", ok ? "PASS" : "FAIL"); fails += !ok; }}']
        else:
            lines += ["    memset((void *)regs, 0, sizeof regs); shim_n = 0UL;",
                      f"    {{ hal_status_t st = {c['function']}({c['arg']});",
                      "      int ok = (st == HAL_ERROR) && (shim_n == 0UL);",
                      f'      printf("OR-{i:03d} INVALID {c["function"]} %s\\n", ok ? "PASS" : "FAIL"); fails += !ok; }}']
    return lines


def _call(fn: str, params: str) -> str:
    if params in ("", "void"):
        return f"{fn}()"
    args = []
    for p in params.split(","):
        p = p.strip()
        args.append("10U" if re.search(r"\b(uint\d+_t|unsigned)\b", p) and not p.endswith("*") else "0")
    return f"{fn}({', '.join(args)})"


def c_source(cases: list[dict], include: str, extra: list[dict] | None = None) -> str:
    lines = [f'#include "{include}"', "#undef ll_rcc_regs", "#include <stdio.h>", "#include <string.h>",
             "volatile uint32_t regs[1024];", "unsigned long shim_n;",
             "volatile uint32_t (*shim_regs(void))[1024] { shim_n++; return &regs; }", "static int fails;",
             "int main(void)", "{", "    uint32_t before[1024];"]
    for i, c in enumerate(cases, 1):
        pre = c["mask"] if c["op"] == "clear" else 0
        other = 0xA5A5A5A5 & ~c["mask"] & 0xFFFFFFFF
        lines += [f"    /* {c['swr']} {c['op']} {c['register']}.{c['field']} via {c['function']} (RM-derived constants) */",
                  "    memset((void *)regs, 0, sizeof regs);",
                  f"    regs[{c['word']}U] = 0x{(pre | other):08X}U;"]
        if c["ready"]:
            lines.append(f"    regs[{c['ready'][0]}U] |= 0x{c['ready'][1]:08X}U;")
        lines += ["    memcpy(before, (const void *)regs, sizeof before);",
                  f"    (void){_call(c['function'], c['params'])};",
                  f"    {{ int ok = ((regs[{c['word']}U] & 0x{c['mask']:08X}U) {'!=' if c['op'] == 'set' else '=='} 0U)"
                  f" && ((regs[{c['word']}U] & ~0x{c['mask']:08X}U) == (before[{c['word']}U] & ~0x{c['mask']:08X}U));",
                  f'      printf("OR-{i:03d} {c["swr"]} {c["function"]} %s\\n", ok ? "PASS" : "FAIL"); fails += !ok; }}']
    lines += timeout_source(extra or [], len(cases) + 1)
    lines += ["    return fails ? 1 : 0;", "}", ""]
    return "\n".join(lines)


def contract_source(cases: list[dict], include: str, block: str = "ll_rcc_regs", count: int = 1024) -> str:
    """C oracle from the register contract (register_contract.cases): expected bit and status per case, all other
    bits of the register unchanged, a no_write case leaves its named register unchanged (no register named: no
    register access at all), a bounded poll for a never-ready case."""
    from .register_contract import call_text

    lines = [f'#include "{include}"', f"#undef {block}", "#include <stddef.h>", "#include <stdio.h>",
             "#include <string.h>", f"volatile uint32_t regs[{count}];", "unsigned long shim_n;",
             f"volatile uint32_t (*shim_regs(void))[{count}] {{ shim_n++; return &regs; }}", "static int fails;",
             "int main(void)", "{", f"    uint32_t before[{count}];"]
    for i, c in enumerate(cases, 1):
        t = 5 if c["never_ready"] or c.get("busy") else 10
        lines += [f"    /* {c['swr']} {c['case']}: {c['op']} {c.get('register', '')}.{c.get('field', '')} via "
                  f"{c['function']} (contract + RM constants) */", "    memset((void *)regs, 0, sizeof regs);"]
        if c["op"] != "no_write":
            other = 0xA5A5A5A5 & ~c["mask"] & 0xFFFFFFFF
            pre = c["mask"] if c["op"] == "clear" and not c["never_ready"] else 0
            if c["op"] == "write":  # feature 009: the field is preset to the complement of the value written
                pre = (~(c["value"] << c["lsb"])) & c["mask"]
            lines.append(f"    regs[{c['word']}U] = 0x{(pre | other):08X}U;")
            if c["ready"] and c["op"] == "set":
                lines.append(f"    regs[{c['ready'][0]}U] |= 0x{c['ready'][1]:08X}U;")
        if c.get("busy"):  # a status flag held set: the call must give up after a bounded wait
            lines.append(f"    regs[{c['busy'][0]}U] |= 0x{c['busy'][1]:08X}U; /* busy, never clears */")
        lines += ["    memcpy(before, (const void *)regs, sizeof before);", "    shim_n = 0UL;"]
        call = call_text(c, f"{t}U")
        lines.append(f"    {{ hal_status_t st = {call};" if c["status"] else f"    {{ (void){call};")
        conds = []
        if c["op"] == "no_write" and "word" in c:  # CAPA-047: the named register is unchanged by the call
            conds.append(f"(regs[{c['word']}U] == before[{c['word']}U])")
        elif c["op"] == "no_write":                # no register named: no register access at all
            conds.append("(shim_n == 0UL)")
        elif c["op"] == "write":  # feature 009: the field holds the value (a key/value register is written whole)
            conds.append(f"((regs[{c['word']}U] & 0x{c['mask']:08X}U) == 0x{(c['value'] << c['lsb']) & c['mask']:08X}U)")
        else:
            conds.append(f"((regs[{c['word']}U] & 0x{c['mask']:08X}U) {'!=' if c['op'] == 'set' else '=='} 0U)")
            conds.append(f"((regs[{c['word']}U] & ~0x{c['mask']:08X}U) == (before[{c['word']}U] & ~0x{c['mask']:08X}U))")
        if c["never_ready"]:
            conds.append(f"(shim_n <= {t + 2}UL) && (shim_n >= 2UL)")
        if c.get("busy"):  # bounded: at most a few register accesses per poll of the timeout
            conds.append(f"(shim_n <= {4 * (t + 2) + 8}UL) && (shim_n >= {t}UL)")
        if c["status"]:
            conds.append(f"(st == {c['status']})")
        lines += [f"      int ok = {' && '.join(conds)};",
                  f'      printf("OR-{i:03d} {c["swr"]} {c["case"]} %s\\n", ok ? "PASS" : "FAIL"); fails += !ok; }}']
    lines += ["    return fails ? 1 : 0;", "}", ""]
    return "\n".join(lines)


def run(ws: Path, include_dirs: list[Path], sources: list[Path], api_header: str) -> dict:
    ws = Path(ws)
    req = (ws / "workproducts/SWE.1/software_requirements.md").read_text(errors="replace")
    arch = (ws / "workproducts/SWE.2/software_architecture.md").read_text(errors="replace")
    hdr_path = next((d / api_header for d in include_dirs if (d / api_header).is_file()), None)
    if hdr_path is None:
        return {"status": "BLOCKED", "reason": f"{api_header} not found"}
    sections = ws / "inputs/sections/RM0486"
    idx = hardware.index(sections)
    from . import register_contract as RC

    contract = (ws / RC.EFFECTS).is_file() and (ws / RC.CALLS).is_file()
    if contract:  # owner decision 2026-10-19 (option B): the machine-readable contract replaces sentence parsing
        cases, notes = RC.cases(ws)
        extra: list[dict] = []
        from ..layer import profile

        pr = profile(ws)
        src = contract_source(cases, api_header, pr["ll"]["register_block"], pr["ll"]["register_count"])
        contract_digests = [hashlib.sha256((ws / p).read_bytes()).hexdigest() for p in (RC.EFFECTS, RC.CALLS)]
    else:
        cases, notes = derive(req, arch, hdr_path.read_text(errors="replace"), idx)
        extra = derive_timeouts(req, hdr_path.read_text(errors="replace"), idx) if api_header.endswith("hal_rcc.h") else []
        src = c_source(cases, api_header, extra)
        contract_digests = []
    prov = {"oracle_id": "OR-" + hashlib.sha256(src.encode()).hexdigest()[:12], "work_order_id": ws.parent.name,
            "requirement_refs": sorted({c["swr"] for c in cases if c.get("swr")}),
            "source_digests": [hashlib.sha256(req.encode()).hexdigest()] + contract_digests + sorted({
                hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(sections.glob("*.md"))
                if any(f"({c['register']})" in p.read_text(errors="replace")[:400] for c in cases if c.get("register"))}),
            "author_role": "oracle-builder", "implementation_hash_seen": None, "independence_status": "UNKNOWN",
            "contamination_reason": None, "holdout_digest": None,
            "oracle_file_hash": hashlib.sha256(src.encode()).hexdigest()}
    impl = {str(p): p.read_text(errors="replace") for p in [hdr_path, *sources]}
    prov = oracle.assess(prov, test_text=src.replace("OR-", "CHECK("), impl=impl)
    if not cases and not extra:
        return {"status": "NOT_RUN", "notes": notes, "provenance": prov}
    with tempfile.TemporaryDirectory() as td:
        t = Path(td)
        from ..layer import profile as _profile

        (t / "shim.h").write_text(shim_text(_profile(ws)["ll"]["register_block"], _profile(ws)["ll"]["register_count"]))
        (t / "oracle.c").write_text(src)
        inc = sum((["-I", str(d)] for d in include_dirs), []) + ["-include", str(t / "shim.h")]
        objs = []
        for s in [*sources, t / "oracle.c"]:
            o = t / (Path(s).stem + ".o")
            b = subprocess.run(["gcc", "-std=c99", "-O0", "-w", *inc, "-c", str(s), "-o", str(o)], capture_output=True,
                               text=True)
            if b.returncode:
                return {"status": "BUILD_FAILED", "reason": b.stderr[-300:], "notes": notes, "provenance": prov,
                        "contract": contract}
            objs.append(str(o))
        b = subprocess.run(["gcc", *objs, "-o", str(t / "oracle")], capture_output=True, text=True)
        if b.returncode:  # CAPA-046 (r159): an unresolved symbol is a build failure, never a verifier crash
            return {"status": "BUILD_FAILED", "reason": b.stderr[-300:], "notes": notes, "provenance": prov,
                    "contract": contract}
        r = subprocess.run([str(t / "oracle")], capture_output=True, text=True, timeout=60)
    res = re.findall(r"^(OR-\d{3}) (SWR-\d{3}|TIMEOUT|INVALID) (\S+) (PASS|FAIL)$", r.stdout, re.M)
    if contract and len(res) < len(cases):  # a crash or hang mid-run: the missing cases are failures, not passes
        res += [(f"OR-{i:03d}", c["swr"], c["case"], "FAIL") for i, c in enumerate(cases, 1)
                if f"OR-{i:03d}" not in {x[0] for x in res}]
    return {"status": "PASS" if r.returncode == 0 and res else "FAIL", "cases": len(cases) + len(extra), "results": res,
            "notes": notes, "provenance": prov, "source": src, "output_sha256": hashlib.sha256(r.stdout.encode()).hexdigest()}
