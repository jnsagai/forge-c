"""Formal verifiers (observe-only): CBMC bounded proof and Frama-C Eva over the public driver API of a workspace.

Both build a harness from FACTS only: the public functions of the layer (LL: static inline functions of the LL header;
HAL: functions declared in the HAL header and defined in the HAL sources) and the register file the LL header declares
(`extern volatile uint32_t <name>[<COUNT>]`). Every register word and every scalar argument is unconstrained, so a
result covers all input values and all register states, within the stated model:
  * registers are plain memory with any initial value (no hardware side effects: a register does not change between
    two reads), single thread, no interrupts;
  * CBMC is bounded: loops unwound to UNWIND with unwinding assertions, so a loop that needs more iterations is
    INCONCLUSIVE, never PASS;
  * Eva is a sound abstract interpretation of the C semantics for the analysed entry point; an alarm is a POSSIBLE
    runtime error to review, not a proven defect.
Enum-typed parameters take any integer value; a pointer parameter points to an object of its type with unconstrained
contents. The verdict assumes valid pointers; a second, informational CBMC run per such function allows NULL and
records whether the function handles it. Function-pointer/array parameters are not harnessed (LIMITATION).
No property here is a functional requirement: these checks prove absence of runtime errors and bounded
termination, nothing about register semantics (that is the independent oracle's job). Not an ISO 26262 method-conformance claim.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..common import data_root
from ..layer import layer_of
from . import swe3

UNWIND = 1100          # > HAL_RCC_TIMEOUT_VALUE (1000) polls + loop exit
SCALARS = {"void", "uint8_t", "uint16_t", "uint32_t", "int8_t", "int16_t", "int32_t", "int", "unsigned", "unsigned int",
           "bool", "_Bool", "hal_status_t"}
_DEF = re.compile(r"^(?:static\s+inline\s+|static\s+|inline\s+)?([A-Za-z_][\w ]*?)\s*\b([A-Z]{2,4}_[A-Za-z0-9_]+)\s*"
                  r"\(([^;{)]*)\)\s*\{", re.M)
_DECL = re.compile(r"^(?:extern\s+)?([A-Za-z_][\w ]*?)\s*\b([A-Z]{2,4}_[A-Za-z0-9_]+)\s*\(([^;{)]*)\)\s*;", re.M)
_NAMED = re.compile(r"\b([A-Z]{2,4}_[A-Za-z0-9_]+)\s*\((?:[^;{}]|\([^;{}]*\))*\)\s*[;{]")  # any declaration/definition
_TYPEDEF = re.compile(r"typedef\s+(enum|struct)\b[^;{]*\{[^}]*\}\s*(\w+)\s*;", re.S)
_REGS = re.compile(r"extern\s+volatile\s+uint32_t\s+(\w+)\s*\[\s*(\w+)\s*\]\s*;")


def tool(name: str) -> str | None:
    p = data_root() / "toolchains/formal/bin" / name
    return str(p) if p.is_file() else shutil.which(name)


def _params(text: str, enums: set[str], structs: set[str]) -> list[dict] | None:
    """[{type, ptr}] per parameter, or None when one cannot be harnessed (function pointer, array, unknown type)."""
    text = text.strip()
    if text in ("", "void"):
        return []
    out = []
    for p in text.split(","):
        p = re.sub(r"\b(const|volatile)\b", " ", p).strip()
        if "[" in p or "(" in p:
            return None
        ptr = p.count("*") == 1
        if p.count("*") > 1:
            return None
        p = p.replace("*", " ").strip()
        t = re.sub(r"\s+\w+$", "", p).strip() if len(p.split()) > 1 else p
        if t in SCALARS | enums or (ptr and t in structs):
            out.append({"type": t, "ptr": ptr})
        else:
            return None
    return out


def api(ws: Path) -> dict:
    """Public API of the developed layer, the sources to compile, the register file and the limitations."""
    ws = Path(ws)
    layer = layer_of(ws)
    ll = sorted((ws / "software/ll").glob("*.h"))
    hal_h, hal_c = sorted((ws / "software/hal").glob("*.h")), sorted((ws / "software/hal").glob("*.c"))
    funcs, limits = [], []
    tds = [m.groups() for h in ll + hal_h for m in _TYPEDEF.finditer(h.read_text(errors="replace"))]
    enums, structs = {n for k, n in tds if k == "enum"}, {n for k, n in tds if k == "struct"}
    if layer == "LL":
        cands = [(m.group(2), m.group(1).strip(), m.group(3)) for h in ll for m in _DEF.finditer(h.read_text(errors="replace"))]
        headers, sources = ll, []
    else:
        cands = [(m.group(2), m.group(1).strip(), m.group(3))
                 for h in hal_h for m in _DECL.finditer(h.read_text(errors="replace"))]
        headers, sources = hal_h, hal_c
    texts = [h.read_text(errors="replace") for h in (ll if layer == "LL" else hal_h)]
    seen = {c[0] for c in cands}
    for name in dict.fromkeys(n for x in texts for n in _NAMED.findall(x)):
        if name not in seen:  # e.g. a function-pointer parameter the signature parser cannot represent
            limits.append(f"LIMITATION:UNSUPPORTED_PARAMETER:{name}")
    for name, ret, params in dict.fromkeys(cands):
        ps = _params(params, enums, structs)
        if ps is None:
            limits.append(f"LIMITATION:UNSUPPORTED_PARAMETER:{name}")
            continue
        funcs.append({"name": name, "ret": re.sub(r"\b(static|inline|extern)\b", "", ret).strip(), "params": ps})

    regs = None
    for h in ll + hal_h:
        m = _REGS.search(h.read_text(errors="replace"))
        if m:
            regs = {"name": m.group(1), "count": m.group(2)}
            break
    defined = regs and any(re.search(rf"^\s*volatile\s+uint32_t\s+{regs['name']}\s*\[", s.read_text(errors="replace"),
                                     re.M) for s in sources)
    return {"layer": layer, "functions": funcs, "headers": headers, "sources": sources, "regs": regs,
            "regs_defined_in_sources": bool(defined), "includes": [ws / "software/hal", ws / "software/ll"],
            "limitations": limits}


def _prelude(a: dict) -> list[str]:
    lines = ["#include <stdint.h>", "#include <stdbool.h>"] + [f'#include "{h.name}"' for h in a["headers"]]
    lines += [f'#include "{s}"' for s in a["sources"]]
    if a["regs"] and not a["regs_defined_in_sources"]:
        lines.append(f"volatile uint32_t {a['regs']['name']}[{a['regs']['count']}];")
    return lines


def _call(f: dict, scalar: str, havoc: str, nullable: str | None = None) -> list[str]:
    """Statements calling f with unconstrained arguments; pointer arguments address a havocked local object (or, with
    `nullable`, that object or NULL)."""
    lines, args = [], []
    for i, x in enumerate(f["params"]):
        if x["ptr"]:
            v = f"a_{f['name']}_{i}"
            lines += [f"    {x['type']} {v};", "    " + havoc.format(v=v)]
            args.append(nullable.format(v=v) if nullable else f"&{v}")
        else:
            args.append(f"({x['type']}){scalar}")
    call = f"{f['name']}({', '.join(args)});"
    return ["    {"] + lines + [f"    (void){call}" if f["ret"] != "void" else f"    {call}", "    }"]


def cbmc(ws: Path, functions: list[str] | None = None) -> dict:
    exe = tool("cbmc")
    a = api(ws)
    if exe is None:
        return {"status": "NOT_SUPPORTED", "findings": ["CBMC is not installed on this host"]}
    if not a["functions"]:
        return {"status": "NOT_SUPPORTED", "findings": ["no harnessable public API function found"] + a["limitations"]}
    per, findings = {}, list(a["limitations"])

    def prove(f: dict, td: str, nullable: str | None) -> dict:
        h = Path(td) / f"h_{f['name']}{'_null' if nullable else ''}.c"
        body = ["uint32_t nondet_u32(void);", "_Bool nondet_bool(void);", "void harness(void)", "{"]
        if a["regs"]:
            body.append(f"    __CPROVER_havoc_object((void *){a['regs']['name']});")
        body += _call(f, "nondet_u32()", "__CPROVER_havoc_object(&{v});", nullable) + ["}"]
        h.write_text("\n".join(_prelude(a) + body) + "\n")
        try:
            return swe3.bounded_proof(h, a["includes"], unwind=UNWIND)
        except subprocess.TimeoutExpired:
            return {"status": "ERROR", "claims": [], "reason": "timeout"}

    with tempfile.TemporaryDirectory() as td:
        for f in a["functions"]:
            if functions and f["name"] not in functions:
                continue
            r = prove(f, td, None)
            failed = [c[0] for c in r.get("claims", []) if c[1] == "FAILURE"]
            unwind_only = failed and all(".unwind." in c for c in failed)
            st = "INCONCLUSIVE" if unwind_only else r["status"]
            per[f["name"]] = {"status": st, "failed_claims": failed[:10], "claims": len(r.get("claims", []))}
            if any(x["ptr"] for x in f["params"]):  # informational: does the function handle a NULL argument?
                n = prove(f, td, "(nondet_bool() ? (void *)0 : &{v})")
                per[f["name"]]["null_argument"] = n["status"]
                if n["status"] == "FAIL":
                    findings.append(f"INFO_NULL_ARGUMENT_NOT_HANDLED:{f['name']}")
            if st == "FAIL":
                findings += [f"CBMC_FAILURE:{f['name']}:{c}" for c in failed[:5]]
            elif st in ("INCONCLUSIVE", "ERROR"):
                findings.append(f"CBMC_{st}:{f['name']}")
    sts = {v["status"] for v in per.values()}
    status = "FAIL" if "FAIL" in sts else ("PASS" if sts == {"PASS"} else "UNKNOWN")
    return {"status": status, "findings": findings, "functions": per, "unwind": UNWIND,
            "version": subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.strip(),
            "scope": "bounded model of the C semantics; registers as unconstrained plain memory; not hardware behaviour"}


def eva(ws: Path) -> dict:
    exe = tool("frama-c")
    a = api(ws)
    if exe is None:
        return {"status": "NOT_SUPPORTED", "findings": ["Frama-C is not installed on this host"]}
    if not a["functions"]:
        return {"status": "NOT_SUPPORTED", "findings": ["no analysable public API function found"] + a["limitations"]}
    body = ['#include "__fc_builtin.h"', "int main(void)", "{"]
    if a["regs"]:
        body.append(f"    for (unsigned i = 0U; i < (unsigned)({a['regs']['count']}); i++) "
                    f"{a['regs']['name']}[i] = Frama_C_unsigned_int_interval(0U, 0xFFFFFFFFU);")
    for f in a["functions"]:
        body += _call(f, "Frama_C_unsigned_int_interval(0U, 0xFFFFFFFFU)",
                      "Frama_C_make_unknown((char *)&{v}, sizeof {v});")
    body += ["    return 0;", "}"]
    with tempfile.TemporaryDirectory() as td:
        m = Path(td) / "eva_main.c"
        m.write_text("\n".join(_prelude(a) + body) + "\n")
        inc = " ".join(f"-I{i}" for i in a["includes"])
        r = subprocess.run([exe, f"-cpp-extra-args={inc}", str(m), "-eva", "-eva-precision", "3",
                            "-eva-no-show-progress", "-eva-warn-key", "*=active"],
                           capture_output=True, text=True, timeout=900)
    out = r.stdout + r.stderr
    alarms = re.search(r"(\d+) alarms? generated", out)
    cov = re.findall(r"(\d+) functions analyzed \(out of (\d+)\)|(\d+) statements reached \(out of (\d+)\)", out)
    lines = out.splitlines()
    warn = []
    for i, ln in enumerate(lines):  # '[eva:alarm] file:line: Warning: ' + the message on the following line(s)
        if "Warning:" in ln and "alarm" in ln:
            loc = ln.split("]", 1)[-1].split(": Warning:", 1)[0].strip().rsplit("/", 1)[-1]
            msg = ln.split("Warning:", 1)[1].strip() or (lines[i + 1].strip() if i + 1 < len(lines) else "")
            warn.append(f"{loc}: {msg}"[:160])
    if r.returncode != 0 or alarms is None:
        return {"status": "ERROR", "findings": [ln[:160] for ln in out.splitlines() if "error" in ln.lower()][:5]}
    n = int(alarms.group(1))
    stmts = next(((int(c[2]), int(c[3])) for c in cov if c[2]), None)
    findings = [f"EVA_ALARM:{w}" for w in warn][:20] + a["limitations"]
    if stmts and stmts[0] < stmts[1]:  # e.g. NULL checks: the entry point passes valid pointers only -> not dead code
        findings.append(f"LIMITATION:EVA_UNREACHED:{stmts[1] - stmts[0]} of {stmts[1]} statements not reached from "
                        "the generated entry point (NULL arguments are not exercised); review before calling it dead")
    return {"status": "FAIL" if n else "PASS", "findings": findings, "alarms": n, "statements": stmts,
            "version": subprocess.run([exe, "-version"], capture_output=True, text=True).stdout.strip(),
            "scope": "abstract interpretation of the C semantics from the generated entry point; registers as "
                     "unconstrained plain memory; an alarm is a possible runtime error, not a proven defect"}


def survey(zips: list[Path], inputs_from: Path | None) -> dict:
    """Both formal verifiers over copies of sealed review packages (the archives are only read; hash re-checked)."""
    import zipfile

    from ..common import sha256_file, utc_now
    from . import shadow

    out = {"schema": "forge-c/easa-formal-survey/0.1", "generated_at": utc_now(), "packages": {}}
    for z in zips:
        z = Path(z)
        before = sha256_file(z)
        with tempfile.TemporaryDirectory() as td:
            x = Path(td) / "x"
            with zipfile.ZipFile(z) as zf:
                zf.extractall(x)
            ws = shadow._workspace_from_package(x, inputs_from)
            c, e, layer = cbmc(ws), eva(ws), layer_of(ws)
        out["packages"][z.parent.name] = {
            "archive_sha256": before, "archive_unchanged": sha256_file(z) == before, "layer": layer,
            "cbmc": {k: c.get(k) for k in ("status", "findings", "unwind")} |
                    {"functions": {n: v["status"] for n, v in (c.get("functions") or {}).items()},
                     "null_argument": {n: v["null_argument"] for n, v in (c.get("functions") or {}).items()
                                       if "null_argument" in v}},
            "eva": {k: e.get(k) for k in ("status", "alarms", "statements", "findings")}}
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    ap = argparse.ArgumentParser(prog="forge_factory.assurance.formal")
    ap.add_argument("zips", nargs="+", type=Path)
    ap.add_argument("--inputs", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    r = survey(a.zips, a.inputs)
    a.out.write_text(json.dumps(r, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: {"cbmc": v["cbmc"]["status"], "eva": v["eva"]["status"]} for k, v in r["packages"].items()}))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
