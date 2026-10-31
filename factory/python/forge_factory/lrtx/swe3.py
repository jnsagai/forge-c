"""LRTX-T022 (P4, LL layer): SWE.3 as coherent structured tasks for the local profile.

Code ("code" visit, replaces the LL author and the fix author): one task per software unit. A unit is one function
of the SWE.2 interface, in interface order, SWU-LL-01, -02, ... Each packet gets:
- the function's SWE.2 signature, operation and register fields;
- the generated register defines it may use;
- the SWRs allocated to it and their register-effect cases;
- the coding rules of the agent prompt.
The answer is the function definition with its Doxygen @unit/@spec block, plus the unit's specification items
(behaviour + SWR traces). The validation of each function is deterministic:
- exact signature;
- only generated defines and the register block;
- no casts to pointers, no other function calls;
- Doxygen tags of its own unit;
- the function compiles in the generated header.
Functions are assembled at the generator's marker. The factory tools then run with the swe3-author role's grants:
compile on both profiles, the swe3_all checks and cppcheck. Their findings are mapped back to functions and repaired
locally.

Design ("author" visit, deterministic): the unit specifications are rendered from the validated spec items,
replacing the scaffold's TODO markers. The shared component constraints (budgets, initial-state invariants) are
traced on the first unit's first item and listed in their own section. The detailed design is rendered from the
interface, the spec items and the measured tool results (static analysis, size, stack), exactly as the tools
reported them. The unchanged SWE.3 gate, the verify node and the inspector decide.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
from pathlib import Path

from ..common import sha256_bytes, utc_now
from . import structured as S
from . import visit as V

PHASE = "SWE.3"
CODE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["code", "spec_items"],
               "properties": {"code": {"type": "string", "minLength": 40},
                              "spec_items": {"type": "array", "minItems": 1, "items": {
                                  "type": "object", "additionalProperties": False,
                                  "required": ["id", "behaviour", "traces"],
                                  "properties": {"id": {"type": "string", "pattern": "^USPEC-LL-[0-9]{2,}-[0-9]{2,}$"},
                                                 "behaviour": {"type": "string", "minLength": 20},
                                                 "traces": {"type": "array", "minItems": 1, "items": {
                                                     "type": "string", "pattern": "^SWR-[0-9]{3}$"}}}}}}}
FORBIDDEN = [(re.compile(r"\(\s*(?:volatile\s+)?(?:uint32_t|unsigned|int|void)\s*\*\s*\)"), "integer-to-pointer cast"),
             (re.compile(r"^\s*#", re.M), "preprocessor directive"),
             (re.compile(r"\bwhile\b|\bfor\b|\bgoto\b"), "loop or goto (LL functions never wait)"),
             (re.compile(r"\bstatic\s+(?!inline\b)\w"), "static storage (the LL keeps no state)")]


def _ident(ws: Path) -> dict:
    from .swe2 import _ident as i2

    return i2(ws)


def interfaces(ws: Path) -> dict:
    """The validated SWE.2 interface (functions in order + allocation), from the structured SWE.2 checkpoint."""
    p = Path(ws) / ".forge-run/lrtx/SWE.2/packets/interfaces.json"
    rec = json.loads(p.read_text()) if p.is_file() else None
    if not rec or rec.get("status") != "VALID":
        raise ValueError("LRTX_SWE3_NEEDS_STRUCTURED_SWE2_INTERFACE")
    return rec["doc"]


def units(ws: Path) -> list[dict]:
    iface = interfaces(ws)
    alloc: dict[str, list[str]] = {}
    for a in iface["allocation"]:
        for f in a["functions"]:
            alloc.setdefault(f, []).append(a["swr"])
    return [{"id": f"SWU-LL-{n:02d}", "n": n, "function": f, "swrs": sorted(alloc.get(f["name"], []))}
            for n, f in enumerate(iface["functions"], 1)]


def _header(ws: Path) -> Path:
    from ..layer import ll_header

    return Path(ws) / ll_header(ws)


def _defines(ws: Path, fields: list[str]) -> str:
    """Generated defines of the registers the function accesses (offsets, field masks/positions, key constants)."""
    i = _ident(ws)
    text = _header(ws).read_text()
    regs = {f.split(".")[0].split("_", 1)[1] for f in fields}
    keep = [ln for ln in text.splitlines() if ln.startswith("#define ") and (
        any(f"LL_{i['pfx']}_{r}_" in ln for r in regs) or "_KEY_" in ln or "REG_COUNT" in ln)]
    return "\n".join(keep)


def _sig(f: dict) -> str:
    return f"static inline {f['returns']} {f['name']}({', '.join(p['type'] + ' ' + p['name'] for p in f['params']) or 'void'})"


def code_packet(ws: Path, u: dict, model: str, findings=None, previous=None) -> dict:
    from ..assurance.register_contract import _requirements

    i = _ident(ws)
    reqs = _requirements(ws)
    eff = json.loads((Path(ws) / "workproducts/SWE.1/register_effects.json").read_text())["effects"]
    cases = [e for e in eff if e["swr"] in u["swrs"]]
    f = u["function"]
    listing = "\n".join(f"{s}: {reqs.get(s, '')}" for s in u["swrs"]) + "\n" + "\n".join(
        f"case {e['case']} ({e['swr']}): {e.get('register', '')}.{e.get('field', '')} op {e['op']}"
        + (f" value {e['value']}" if e.get("value") is not None else "") for e in cases)
    defs = _defines(ws, f["fields"])
    instr = (f"Implement software unit {u['id']}: the single function `{_sig(f)}` of the header-only "
             f"{i['header']} - {f['operation']}. Use ONLY the generated defines listed below and the register-block "
             f"array {i['block']} indexed as {i['block']}[LL_{i['pfx']}_<REG>_OFFSET / 4U]: no integer-to-pointer "
             "casts, no loops or waiting, no other function calls, no static state. A field update reads the register "
             "once, clears the field with its _MSK define, ORs the new value shifted by its _POS define and masked, "
             "then writes once; a write-only key register is written whole (never read). A query returns 1U when the "
             "flag bit is set, else 0U. MISRA C:2012 style: one return statement at the end, unsigned constants with a "
             "U suffix, no implicit conversions. code = the complete function definition preceded by exactly this "
             f"Doxygen block: '/**', ' * @brief <one line>', ' * @unit {u['id']}', ' * @spec <spec ids>', ' */'. "
             f"spec_items: the unit's specification items USPEC-LL-{u['n']:02d}-01, -02 ... (one per distinct "
             "behaviour), each with the behaviour the unit shall implement and the requirement ids it refines (traces, "
             f"only from: {', '.join(u['swrs']) or 'none'}). The @spec line lists exactly these ids.")
    art = [{"path": "requirements+cases", "text": listing, "sha256": sha256_bytes(listing.encode())},
           {"path": f"{i['header']}#generated-defines", "text": defs, "sha256": sha256_bytes(defs.encode())}]
    return S.packet(phase=PHASE, task=f"code:{u['id']}", role="swe3-author", instructions=instr, sources=[],
                    artifacts=art, criteria=["compiles in the generated header", "only generated defines are used",
                                             "every allocated requirement is traced by a spec item"],
                    output_schema=CODE_SCHEMA, model=model, findings=findings, previous=previous)


def _compile_alone(ws: Path, code: str, function: str) -> list[str]:
    """Compile the candidate in a temporary CURRENT header, replacing its old definition.

    Revalidation after assembly must not insert a duplicate. The pristine assembly
    snapshot can have stale defines after an upstream repair, so use today's
    header and preserve every unrelated declaration. Comments/literals are masked
    before balancing braces; no change is made to the actual workproduct.
    """
    hdr = _header(ws).read_text()
    from ..inspection.guideline import strip_c
    from ..inspection.regmap import functions_marker

    marker = functions_marker(ws)
    if marker not in hdr:
        return ["the generated header has no functions marker (regenerate the register map)"]
    masked = strip_c(hdr)
    definitions = list(re.finditer(r"^[ \t]*static\s+inline\s+(?:void|uint32_t)\s+" + re.escape(function)
                                  + r"\s*\([^;{}]*\)\s*\{", masked, re.M))
    if len(definitions) > 1:
        return [f"compile: current header has multiple definitions of {function}"]
    if definitions:
        definition = definitions[0]
        depth, end = 1, definition.end()
        while end < len(masked) and depth:
            depth += (masked[end] == "{") - (masked[end] == "}")
            end += 1
        if depth:
            return [f"compile: current header has an unbalanced definition of {function}"]
        candidate = hdr[:definition.start()] + code + hdr[end:]
    else:
        candidate = hdr.replace(marker, code + "\n" + marker, 1)
    with tempfile.TemporaryDirectory() as td:
        h = Path(td) / "unit.h"
        h.write_text(candidate)
        c = Path(td) / "unit.c"
        c.write_text('#include "unit.h"\nvolatile uint32_t ' + _ident(ws)["block"] + "[LL_" + _ident(ws)["pfx"]
                     + "_REG_COUNT];\n")
        r = subprocess.run(["gcc", "-std=c99", "-Wall", "-Wextra", "-Wconversion", "-Werror", "-fsyntax-only", str(c)],
                           capture_output=True, text=True, cwd=td)
    return [f"compile: {ln.split(' error: ', 1)[1][:160]}" for ln in r.stderr.splitlines() if " error: " in ln][:6] \
        or ([f"compile failed: {r.stderr.strip()[:160]}"] if r.returncode else [])


def validate_code(ws: Path, doc: dict, u: dict) -> list[str]:
    from ..inspection.swtrace import functions_with_docs

    f, code, out = u["function"], doc["code"], []
    fns = functions_with_docs(code)
    if [x["function"] for x in fns] != [f["name"]]:
        out.append(f"code must define exactly one function, {f['name']} (found {[x['function'] for x in fns]})")
    head = code[code.find("static"):code.find("{")] if "static" in code and "{" in code else ""
    if re.sub(r"\s+", " ", head).strip() != _sig(f):
        out.append(f"signature must be exactly: {_sig(f)}")
    for rx, what in FORBIDDEN:
        if rx.search(code.split("*/", 1)[-1]):
            out.append(f"forbidden construct: {what}")
    i = _ident(ws)
    known = set(re.findall(r"#define\s+(\w+)", _header(ws).read_text()))
    used = set(re.findall(rf"\bLL_{i['pfx']}_\w+", code.split("*/", 1)[-1])) - {f["name"]}
    out += [f"{x} is not a generated define (use only the defines listed)" for x in sorted(used - known)]
    calls = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", code.split("{", 1)[-1])) - {"if", "return", "sizeof"}
    out += [f"call to {c}: LL functions call no other function" for c in sorted(calls)]
    d = fns[0] if fns else {"units": [], "specs": []}
    ids = sorted(s["id"] for s in doc["spec_items"])
    if d["units"] != [u["id"]]:
        out.append(f"the Doxygen block needs '@unit {u['id']}' (found {d['units']})")
    if sorted(d["specs"]) != ids:
        out.append(f"the @spec line must list exactly the spec item ids {ids} (found {d['specs']})")
    out += [f"spec item {s['id']} is not of unit {u['id']}" for s in doc["spec_items"]
            if not s["id"].startswith(f"USPEC-LL-{u['n']:02d}-")]
    traced = {t for s in doc["spec_items"] for t in s["traces"]}
    out += [f"spec traces {t}, which is not allocated to {f['name']}" for t in sorted(traced - set(u["swrs"]))]
    out += [f"{t} (allocated to {f['name']}) is traced by no spec item" for t in u["swrs"] if t not in traced]
    if not out:
        out += _compile_alone(ws, code, f["name"])
    return out


# ---- assembly and the factory tools --------------------------------------------------------------------------------
def assemble_code(ws: Path, recs: list[tuple[dict, dict]]) -> None:
    """Insert the validated functions before the generator's marker of the GENERATED header (kept pristine on the first
    assembly), so re-assembly after a repair never duplicates functions."""
    from ..inspection.regmap import functions_marker

    hdr = _header(ws)
    pristine = Path(ws) / ".forge-run/lrtx/SWE.3/generated-header.h"
    if not pristine.is_file():
        pristine.parent.mkdir(parents=True, exist_ok=True)
        pristine.write_text(hdr.read_text())
    marker = functions_marker(ws)
    text = pristine.read_text()
    body = "\n\n".join(r["doc"]["code"].strip() for _u, r in recs)
    V.write_scoped(ws, {str(hdr.relative_to(ws)): text.replace(marker, body + "\n\n" + marker, 1)}, "swe3_ll_author")


def tool_findings(ws: Path) -> tuple[list[str], dict]:
    """Compile (both profiles), swe3_all and cppcheck through the role-granted operations, journaled like agent calls."""
    from . import tools as T

    res = {}
    out = []
    for prof in ("target-cm55-gcc", "host-clang"):
        r = T.call(ws, "forge-build-mcp", "compile", {"profile": prof}, "swe3-author", PHASE)
        res[f"compile:{prof}"] = r
        if r["status"] != "PASS":
            out += [f"compile {prof}: {i}" for i in r["issues"][:6]]
    r = T.call(ws, "forge-docs-mcp", "validate_artifact", {"path": ".", "check": "swe3_all"}, "swe3-author", PHASE)
    res["swe3_all"] = r
    if r["status"] != "PASS":
        out += [f"swe3_all: {i}" for i in r["issues"][:8]]
    r = T.call(ws, "forge-analysis-mcp", "cppcheck", {}, "swe3-author", PHASE)
    res["cppcheck"] = r
    if r["status"] != "PASS":
        out += [f"cppcheck: {i}" for i in r["issues"][:8]]
    return out, res


def _route(findings: list[str], us: list[dict]) -> dict[str, list[str]]:
    """Tool findings to the unit whose function they name (unattributable findings go to every unit once)."""
    per: dict[str, list[str]] = {}
    for f in findings:
        hit = [u for u in us if u["function"]["name"] in f]
        for u in hit or us:
            per.setdefault(f"code:{u['id']}", []).append(f)
    return per


def visit_code(ws: Path, model: str, max_calls: int | None = None, resume: bool = False,
               time_budget_s: float | None = None) -> dict:
    from ..layer import layer_of
    from ..registry.agents import load_agents

    ws = Path(ws)
    if layer_of(ws) != "LL":
        return V.reply(ws, PHASE, "FAILED", ["LRTX_SWE3_LAYER_NOT_SUPPORTED_YET (structured SWE.3 covers LL)"])
    role = {a.id: a for a in load_agents()[0]}["swe3-author"]
    since = V.last_finished(ws, PHASE)
    budget, findings = V.open_visit(ws, PHASE, resume, lambda: V.rework_findings(ws, PHASE, since) if since else [],
                                    V.author_call_limit(ws, PHASE, role.max_turns, max_calls), time_budget_s)
    try:
        return _visit_code(ws, model, budget, findings)
    except V.Continue as c:
        return V.reply(ws, PHASE, "CONTINUE", [f"time box used; the next node execution resumes at {c}"], budget)
    except ValueError as exc:
        return V.reply(ws, PHASE, "FAILED", [str(exc)], budget)


def _visit_code(ws: Path, model: str, budget: dict, findings: list[str]) -> dict:
    us = units(ws)
    routed = _route(findings, us) if findings else {}
    recs = []
    for u in us:
        task = f"code:{u['id']}"
        rec = V.run_task(ws, PHASE, task, lambda fi, pr, u=u: code_packet(ws, u, model, fi, pr),
                         lambda d, u=u: validate_code(ws, d, u), budget, routed.get(task))
        recs.append((u, rec))
    bad = [r for _u, r in recs if r["status"] != "VALID"]
    if bad:
        return V.reply(ws, PHASE, "FAILED", [f"{r['task']}: {e}" for r in bad for e in r["errors"][:4]], budget)
    assemble_code(ws, recs)
    issues, _res = tool_findings(ws)
    if issues and budget["calls"] < budget["max_calls"]:
        for task, fs in _route(issues, us).items():
            u = next(x for x in us if f"code:{x['id']}" == task)
            rec = V.run_task(ws, PHASE, task, lambda fi, pr, u=u: code_packet(ws, u, model, fi, pr),
                             lambda d, u=u: validate_code(ws, d, u), budget, fs)
            recs = [(x, rec if x is u else r) for x, r in recs]
        bad = [r for _u, r in recs if r["status"] != "VALID"]
        if bad:
            return V.reply(ws, PHASE, "FAILED", [f"{r['task']}: {e}" for r in bad for e in r["errors"][:4]], budget)
        assemble_code(ws, recs)
        issues, _res = tool_findings(ws)
    S.record(ws, "SWE.3/code-assembly.json", {"at": utc_now(), "units": [u["id"] for u, _r in recs]})
    if issues:
        return V.reply(ws, PHASE, "FAILED", issues[:20], budget)
    return V.reply(ws, PHASE, "PASS", [], budget, artifacts=[str(_header(ws).relative_to(ws))])


# ---- design (deterministic) -------------------------------------------------------------------------------------------
def visit_design(ws: Path, model: str = "", **_k) -> dict:
    """Render unit specifications and the detailed design from the validated code tasks and the measured tools; no
    model call (the semantic content was authored and validated in the code tasks)."""
    from ..inspection.swtrace import UNITS_MD, component_constraints
    from ..inspection.swtrace import parse_units as _pu
    from . import tools as T

    ws = Path(ws)
    try:
        us = units(ws)
    except ValueError as exc:
        return V.reply(ws, PHASE, "FAILED", [str(exc)])
    recs = {}
    for u in us:
        ck = V._ckpt(ws, PHASE, f"code:{u['id']}")
        rec = json.loads(ck.read_text()) if ck.is_file() else None
        if not rec or rec.get("status") != "VALID":
            return V.reply(ws, PHASE, "FAILED", [f"code:{u['id']} has no valid code task"])
        recs[u["id"]] = rec["doc"]
    cl = sorted(component_constraints(ws))
    from ..assurance.register_contract import _requirements

    reqs = _requirements(ws)
    md = ["# Software unit specifications", "",
          "Rendered from the validated SWE.3 code tasks of the local profile (ADR-0014): each unit is one function of "
          "the SWE.2 interface; its specification items are the behaviour the unit implements and the requirements it "
          "refines.", ""]
    if cl:
        md += ["## Shared component constraints", "", " ".join(f"{s}: {reqs.get(s, '').strip()}" for s in cl) +
               " These constrain the whole SWC_LL; they are traced through USPEC-LL-01-01 for allocation coverage and "
               "define no unit or function of their own.", ""]
    for n, u in enumerate(us):
        doc = recs[u["id"]]
        md += [f"## {u['id']}: {u['function']['name']}", "- SWC: SWC_LL", f"- Functions: {u['function']['name']}",
               f"- Design: workproducts/SWE.3/detailed_design/{u['id']}.puml"]
        for k, s in enumerate(sorted(doc["spec_items"], key=lambda x: x["id"])):
            traces = list(s["traces"]) + (cl if n == 0 and k == 0 else [])
            md.append(f"- **{s['id']}** {s['behaviour'].strip()} Traces: {', '.join(dict.fromkeys(traces))}")
        md.append("")
    files = {UNITS_MD: "\n".join(md)}
    res = {}
    for op, args in (("measure_elf", {"profile": "target-cm55-gcc"}), ("stack_usage", {"profile": "target-cm55-gcc"})):
        res[op] = T.call(ws, "forge-build-mcp", op, args, "swe3-author", PHASE)
    res["cppcheck"] = T.call(ws, "forge-analysis-mcp", "cppcheck", {}, "swe3-author", PHASE)
    res["clang_analyze"] = T.call(ws, "forge-analysis-mcp", "clang_analyze", {}, "swe3-author", PHASE)
    i = _ident(ws)
    dd = ["# Detailed design", "", f"SWC_LL is implemented by {i['header']} as {len(us)} static inline functions, one "
          "software unit each, on the generated register map (extern volatile register-block array; no state, no "
          "waiting). Behaviour per unit: workproducts/SWE.3/unit_specifications.md.", "",
          "| Function | Purpose | Registers/bits | SWR IDs |", "| --- | --- | --- | --- |"]
    dd += [f"| {u['function']['name']} | {u['function']['operation']} | {', '.join(u['function']['fields']) or '-'} | "
           f"{', '.join(u['swrs']) or '-'} |" for u in us]
    dd += ["", "## Static analysis and MISRA (subset)", "", "Results exactly as the tools reported them; MISRA compliance "
           "is not claimed."]
    for k in ("cppcheck", "clang_analyze"):
        r = res[k]
        dd.append(f"- {k}: status {r['status']}; summary \"{r['summary']}\"; issues {r['issues']}; metrics "
                  f"{json.dumps(r.get('metrics') or {}, sort_keys=True)}")
    dd += ["", "## Resource usage", ""]
    for k in ("measure_elf", "stack_usage"):
        r = res[k]
        dd.append(f"- {k} (target-cm55-gcc): status {r['status']}; summary \"{r['summary']}\"; metrics "
                  f"{json.dumps(r.get('metrics') or {}, sort_keys=True)}")
    dd.append("")
    files["workproducts/SWE.3/detailed_design.md"] = "\n".join(dd)
    V.write_scoped(ws, files, "swe3_author")
    _pu  # noqa: B018 - parse_units is the format the gate reads (kept imported for readers)
    return V.reply(ws, PHASE, "PASS", [], None, artifacts=sorted(files))
