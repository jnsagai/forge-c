"""Machine-readable register contract (owner decision 2026-10-19, option B) - the input of the independent EASA oracle.

The oracle used to parse requirement sentences ("shall set RCC_CR.HSION") and skipped every API with a pointer
argument; on the pilot packages it derived nothing (r149: 4 of 6 seeded defects missed). Instead:

  SWE.1  workproducts/SWE.1/register_effects.json  what each requirement does to a register bit (RM names), per case
  SWE.2  workproducts/SWE.2/api_calls.json         which allocated API call exercises each case, with C arguments
  SWE.3  the calls compile against the interface header (the code follows the SWE.2 interface)

Gates check the contract against the requirement text, the RM index and the allocation table; the oracle reads only
the contract and the RM (bit positions), never the implementation. Work orders prepared from now carry
`register_contract` in the manifest; older ones keep the sentence-parsing oracle.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

EFFECTS = "workproducts/SWE.1/register_effects.json"
CALLS = "workproducts/SWE.2/api_calls.json"
OPS = ("set", "clear", "no_write")
STATUSES = ("HAL_OK", "HAL_TIMEOUT", "HAL_ERROR")
CASE_RX = re.compile(r"^[A-Z][A-Z0-9_]{1,47}$")
FIELD_RX = re.compile(r"^(RCC_[A-Z0-9]+)\.([A-Z0-9_]+)$")
SAFE_ARG = re.compile(r"^[A-Za-z0-9_&(){}.=, +\-*/\[\]]*$")
CALL_IN_ARG = re.compile(r"[A-Za-z_]\w*\s*\(")  # a function call inside an argument is refused (no hidden logic)
SWR_LINE = re.compile(r"\*\*(SWR-\d{3})\*\*\s*(.+)")


def enabled(ws: Path) -> bool:
    from ..layer import register_contract_enabled

    return register_contract_enabled(ws)


def _load(ws: Path, rel: str) -> tuple[dict | None, list[str]]:
    p = Path(ws) / rel
    if not p.is_file():
        return None, [f"CONTRACT_MISSING:{rel}"]
    try:
        d = json.loads(p.read_text())
    except ValueError as exc:
        return None, [f"CONTRACT_NOT_JSON:{rel}:{str(exc)[:80]}"]
    return (d, []) if isinstance(d, dict) else (None, [f"CONTRACT_NOT_OBJECT:{rel}"])


def _rm_index(ws: Path) -> dict:
    from .hardware import index

    d = Path(ws) / "inputs/sections/RM0486"
    return index(d) if d.is_dir() else {}


def _requirements(ws: Path) -> dict[str, str]:
    p = Path(ws) / "workproducts/SWE.1/software_requirements.md"
    return {m.group(1): m.group(2) for m in SWR_LINE.finditer(p.read_text(errors="replace"))} if p.is_file() else {}


def _needs_contract(text: str) -> bool:
    """A requirement that sets or clears a named register bit through the driver API (not a reset-value statement)."""
    return bool(re.search(r"\bRCC_[A-Z0-9]+\.[A-Z0-9_]+", text)) and bool(
        re.search(r"\b(set|clear|clears|assert|release)\b", text, re.I)) and "reset value" not in text.lower()


def check_effects(ws: Path, layer: str = "HAL") -> list[str]:
    d, f = _load(ws, EFFECTS)
    if d is None:
        return f
    effects = d.get("effects")
    if d.get("schema") != "forge-c/register-effects/1" or not isinstance(effects, list) or not effects:
        return [f"CONTRACT_SCHEMA:{EFFECTS}: need schema forge-c/register-effects/1 and a non-empty effects list"]
    reqs, idx, out, seen = _requirements(ws), _rm_index(ws), [], set()
    for i, e in enumerate(effects):
        case = str(e.get("case", ""))
        where = f"{EFFECTS}:{case or i}"
        if not CASE_RX.match(case) or case in seen:
            out.append(f"CONTRACT_CASE_ID:{where} (unique UPPER_CASE id)")
        seen.add(case)
        swr, op = e.get("swr"), e.get("op")
        if swr not in reqs:
            out.append(f"CONTRACT_UNKNOWN_SWR:{where}:{swr}")
        if op not in OPS:
            out.append(f"CONTRACT_OP:{where}:{op} (set|clear|no_write)")
            continue
        if layer == "HAL" and e.get("status") not in STATUSES:
            out.append(f"CONTRACT_STATUS:{where}:{e.get('status')} (HAL_OK|HAL_TIMEOUT|HAL_ERROR)")
        if op == "no_write":
            continue
        reg, fld = e.get("register"), e.get("field")
        r = idx.get(reg)
        if r is None or fld not in r["fields"]:
            out.append(f"CONTRACT_NOT_IN_RM:{where}:{reg}.{fld}")
        elif swr in reqs and f"{reg}.{fld}" not in reqs[swr] and not (reg in reqs[swr] and fld in reqs[swr]):
            out.append(f"CONTRACT_FIELD_NOT_IN_SWR:{where}:{reg}.{fld} is not named by {swr}")
        ready = e.get("ready")
        if ready not in (None, "never"):
            m = FIELD_RX.match(str(ready))
            if not m or m.group(1) not in idx or m.group(2) not in idx[m.group(1)]["fields"]:
                out.append(f"CONTRACT_READY_NOT_IN_RM:{where}:{ready}")
        if ready == "never" and (op != "clear" or e.get("status") != "HAL_TIMEOUT"):
            out.append(f"CONTRACT_TIMEOUT_CASE:{where}: a never-ready case clears the enable bit and returns HAL_TIMEOUT")
    covered = {e.get("swr") for e in effects}
    out += [f"CONTRACT_SWR_NOT_COVERED:{s} (it sets or clears a register bit: add its effects)"
            for s, t in sorted(reqs.items()) if _needs_contract(t) and s not in covered]
    return out[:15]


def check_calls(ws: Path) -> list[str]:
    from .oracle_gen import allocation

    eff, f = _load(ws, EFFECTS)
    d, g = _load(ws, CALLS)
    if eff is None or d is None:
        return f + g
    calls = d.get("calls")
    if d.get("schema") != "forge-c/api-calls/1" or not isinstance(calls, dict):
        return [f"CONTRACT_SCHEMA:{CALLS}: need schema forge-c/api-calls/1 and a calls object"]
    arch = Path(ws) / "workproducts/SWE.2/software_architecture.md"
    alloc = allocation(arch.read_text(errors="replace")) if arch.is_file() else {}
    out = []
    for e in eff.get("effects") or []:
        case, c = e.get("case"), calls.get(e.get("case"))
        if not isinstance(c, dict):
            out.append(f"CONTRACT_CASE_WITHOUT_CALL:{CALLS}:{case}")
            continue
        fn, args = c.get("function"), c.get("args", [])
        if fn not in alloc.get(e.get("swr"), []):
            out.append(f"CONTRACT_FUNCTION_NOT_ALLOCATED:{CALLS}:{case}:{fn} is not allocated to {e.get('swr')}")
        if not isinstance(args, list) or any(not isinstance(a, str) or not SAFE_ARG.match(a) or CALL_IN_ARG.search(
                a.replace("{timeout}", "")) or ";" in a for a in args):
            out.append(f"CONTRACT_UNSAFE_ARGS:{CALLS}:{case} (C argument expressions only: no calls, no ';')")
    known = {e.get("case") for e in eff.get("effects") or []}
    out += [f"CONTRACT_CALL_WITHOUT_CASE:{CALLS}:{k}" for k in sorted(set(calls) - known)]
    return out[:15]


def cases(ws: Path) -> tuple[list[dict], list[str]]:
    """Oracle cases from the contract: expected values from the RM index and the SWE.1 effects only."""
    eff, f = _load(ws, EFFECTS)
    d, g = _load(ws, CALLS)
    if eff is None or d is None:
        return [], f + g
    idx, out, notes = _rm_index(ws), [], []
    for e in eff.get("effects") or []:
        c = (d.get("calls") or {}).get(e.get("case"))
        if not isinstance(c, dict) or e.get("op") not in OPS:
            notes.append(f"ORACLE_NOT_DERIVABLE:{e.get('case')}:no call or op")
            continue
        case = {"case": e["case"], "swr": e.get("swr"), "function": c["function"], "args": list(c.get("args") or []),
                "op": e["op"], "status": e.get("status"), "never_ready": e.get("ready") == "never", "ready": None}
        if e["op"] != "no_write":
            r = idx.get(e.get("register"))
            fld = (r or {}).get("fields", {}).get(e.get("field"))
            if fld is None:
                notes.append(f"ORACLE_NOT_DERIVABLE:{e['case']}:{e.get('register')}.{e.get('field')} not in RM")
                continue
            case.update(word=r["offset"] // 4, mask=((1 << (fld["msb"] - fld["lsb"] + 1)) - 1) << fld["lsb"],
                        register=e["register"], field=e["field"])
            m = FIELD_RX.match(str(e.get("ready") or ""))
            if m and m.group(1) in idx and m.group(2) in idx[m.group(1)]["fields"]:
                rf = idx[m.group(1)]["fields"][m.group(2)]
                case["ready"] = (idx[m.group(1)]["offset"] // 4, 1 << rf["lsb"])
        out.append(case)
    return out, notes


def call_text(case: dict, timeout: str) -> str:
    return f"{case['function']}({', '.join(a.replace('{timeout}', timeout) for a in case['args'])})"


def check_compiles(ws: Path, include_dirs: list[Path], api_header: str) -> list[str]:
    """SWE.3: every contract call compiles against the interface header (the code follows the SWE.2 interface)."""
    cs, notes = cases(ws)
    if not cs:
        return []
    src = [f'#include "{api_header}"', "#include <stddef.h>", "void forge_contract_calls(void);",
           "void forge_contract_calls(void)", "{"]
    src += [f"    (void){call_text(c, '10U')}; /* {c['case']} */" for c in cs] + ["}", ""]
    with tempfile.TemporaryDirectory() as td:
        t = Path(td) / "contract_calls.c"
        t.write_text("\n".join(src))
        r = subprocess.run(["gcc", "-std=c99", "-fsyntax-only", "-Werror=implicit-function-declaration",
                            *sum((["-I", str(d)] for d in include_dirs), []), str(t)], capture_output=True, text=True)
    if r.returncode == 0:
        return []
    errs = [ln.split(" error: ", 1)[1][:120] for ln in r.stderr.splitlines() if " error: " in ln]
    return [f"CONTRACT_CALL_DOES_NOT_COMPILE:{CALLS}:{e}" for e in errs[:6]] or ["CONTRACT_CALL_DOES_NOT_COMPILE:" + CALLS]
