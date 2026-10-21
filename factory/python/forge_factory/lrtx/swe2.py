"""LRTX-T014/T015 (LRTX-FR-011/012): SWE.2 as coherent structured tasks for the local profile (LL layer).

Task "interfaces" (model): the concrete LL functions (names, signatures, operation, register fields), the allocation
of every functional SWR to functions, and the C call of every SWE.1 register-effect case. Component-level constraints
(resource budgets, initial-state invariants) are allocated to the software component itself - no function is invented
for them (LRTX-FR-011).
Task "design" (model): the design decisions and rationale the SWE.2 checklist judges - register ownership/volatile/RMW
semantics, timing and error handling, concurrency/ISR/reentrancy, safety mechanisms and dependencies, budget
justification - and the call sequences of the dynamic view.
Rendering (deterministic): software_architecture.md with its tables, the static and dynamic PlantUML views (exactly one
<<SWC>> element, an 'Allocated:' note naming every SWR, interface ids) and api_calls.json - judged by the unchanged
SWE.2 gates and inspector.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import sha256_bytes, utc_now
from . import structured as S
from . import visit as V
from .swe1 import _manifest, _section_files, system_name

PHASE = "SWE.2"
ARCH = "workproducts/SWE.2/software_architecture.md"
STATIC = "workproducts/SWE.2/architecture_static.puml"
DYNAMIC = "workproducts/SWE.2/architecture_dynamic.puml"
CALLS = "workproducts/SWE.2/api_calls.json"
SAFE_ARG = re.compile(r"^[A-Za-z0-9_&(){}.=, +\-*/\[\]]*$")

FN_SCHEMA = {"type": "object", "additionalProperties": False,
             "required": ["name", "returns", "params", "operation", "fields"],
             "properties": {"name": {"type": "string", "pattern": "^[A-Z]{2,4}_[A-Z0-9]+_[A-Za-z0-9_]+$"},
                            "returns": {"type": "string", "enum": ["void", "uint32_t"]},
                            "params": {"type": "array", "items": {
                                "type": "object", "additionalProperties": False, "required": ["name", "type"],
                                "properties": {"name": {"type": "string", "pattern": "^[a-z][a-z0-9_]{0,30}$"},
                                               "type": {"type": "string", "enum": ["uint32_t"]}}}},
                            "operation": {"type": "string", "minLength": 10},
                            "fields": {"type": "array", "items": {"type": "string"}}}}
INTERFACES_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["functions", "allocation", "calls"],
                     "properties": {
                         "functions": {"type": "array", "minItems": 1, "items": FN_SCHEMA},
                         "allocation": {"type": "array", "items": {
                             "type": "object", "additionalProperties": False,
                             "required": ["swr", "functions", "responsibility"],
                             "properties": {"swr": {"type": "string", "pattern": "^SWR-[0-9]{3}$"},
                                            "functions": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                                            "responsibility": {"type": "string", "minLength": 5}}}},
                         "calls": {"type": "array", "items": {
                             "type": "object", "additionalProperties": False, "required": ["case", "function", "args"],
                             "properties": {"case": {"type": "string"}, "function": {"type": "string"},
                                            "args": {"type": "array", "items": {"type": "string"}}}}}}}
TEXTS = ("components", "register_access", "timing_and_error_handling", "memory_and_stack",
         "concurrency_and_reentrancy", "safety_and_dependencies")
DESIGN_SCHEMA = {"type": "object", "additionalProperties": False, "required": [*TEXTS, "decisions", "sequences"],
                 "properties": {**{t: {"type": "string", "minLength": 80} for t in TEXTS},
                                "decisions": {"type": "array", "minItems": 1, "items": {"type": "string", "minLength": 10}},
                                "sequences": {"type": "array", "minItems": 1, "items": {
                                    "type": "object", "additionalProperties": False, "required": ["title", "steps"],
                                    "properties": {"title": {"type": "string", "minLength": 5},
                                                   "steps": {"type": "array", "minItems": 1, "items": {
                                                       "type": "object", "additionalProperties": False,
                                                       "required": ["function", "repeat_until", "note"],
                                                       "properties": {"function": {"type": "string"},
                                                                      "repeat_until": {"type": "string"},
                                                                      "note": {"type": "string"}}}}}}}}}


# ---- inputs ------------------------------------------------------------------------------------------------------------
def requirements(ws: Path) -> dict[str, str]:
    from ..assurance.register_contract import _requirements

    return _requirements(ws)


def effects(ws: Path) -> list[dict]:
    p = Path(ws) / "workproducts/SWE.1/register_effects.json"
    return json.loads(p.read_text()).get("effects", []) if p.is_file() else []


def component_level(ws: Path) -> set[str]:
    from ..inspection.swtrace import component_constraints

    return component_constraints(Path(ws))


def _ident(ws: Path) -> dict:
    from ..layer import profile, register_prefix

    p = profile(ws)
    return {"pfx": register_prefix(ws), "fn": p["ll"]["function_prefix"], "header": p["ll"]["header"],
            "stem": Path(p["ll"]["header"]).stem, "block": p["ll"]["register_block"], "base": p["base_address"],
            "mm": p.get("mm_page"), "void": p["ll"].get("void_signatures", True), "prompt": p.get("prompt") or {}}


def _guidance(ws: Path) -> str:
    """The LL architecture rules of the agent prompt (profile texts for a non-RCC peripheral), not new policy."""
    from ..workflow import prompts

    i = _ident(ws)
    api = " ".join((i["prompt"].get("ll_api") or prompts.LL_API).split())
    return (f"LL functions: {api}. Header-only static inline functions in {i['header']}; no waiting, no timeouts, no "
            "error codes at LL level (callers bound their own polling); no driver-owned state; register access through "
            f"the extern volatile uint32_t register-block array {i['block']} placed at the base {i['base']} by the "
            "linker, indexed by offset/4, no integer-to-pointer casts; a field update is a read-modify-write that "
            "preserves the other bits unless the register is write-only (then a whole-register write).")


def _fn_rx(ws: Path) -> re.Pattern:
    return re.compile(rf"\b{re.escape(_ident(ws)['fn'])}\w+")


# ---- packets -----------------------------------------------------------------------------------------------------------
def interfaces_packet(ws: Path, model: str, findings=None, previous=None) -> dict:
    reqs, cl = requirements(ws), component_level(ws)
    func = {k: v for k, v in reqs.items() if k not in cl}
    listing = "\n".join(f"{k}: {v}" for k, v in func.items())
    cases = "\n".join(f"{e['case']}: {e['swr']} {e.get('register', '')}.{e.get('field', '')} op {e['op']}"
                      + (f" value {e['value']}" if e.get("value") is not None else "") for e in effects(ws))
    art = [{"path": "workproducts/SWE.1/software_requirements.md#functional", "text": listing,
            "sha256": sha256_bytes(listing.encode())},
           {"path": "workproducts/SWE.1/register_effects.json#cases", "text": cases, "sha256": sha256_bytes(cases.encode())}]
    i = _ident(ws)
    instr = (f"Design the interface of the {system_name(ws)} (SWE.2 architecture, LL layer). {_guidance(ws)} "
             "functions: one concrete function per operation the requirements need (never a placeholder such as "
             f"{i['fn']}<Name>_Enable), with its return type (void for commands, uint32_t 1U/0U for queries), its "
             "uint32_t parameters (" + ("none: LL functions take no arguments" if i["void"] else
                                         "only value setters take one uint32_t value") +
             "), a one-line operation and the REGISTER.FIELD names it accesses. allocation: one entry for EVERY "
             "requirement listed (and only those) naming the function(s) that implement it and its architectural "
             "responsibility. calls: one entry per register-effect case: the function allocated to the case's "
             "requirement and its C arguments (decimal or hex integer constants with a U suffix; a write case passes "
             "exactly the case value). Every function a requirement statement names must exist with that exact name.")
    crit = ["every listed requirement is allocated", "every function is allocated to at least one requirement",
            "every case has one call of a function allocated to its requirement"]
    return S.packet(phase=PHASE, task="interfaces", role="swe2-author", instructions=instr, sources=[],
                    artifacts=art, criteria=crit, output_schema=INTERFACES_SCHEMA, model=model, findings=findings,
                    previous=previous)


def design_packet(ws: Path, model: str, iface: dict, findings=None, previous=None) -> dict:
    m = _manifest(ws)
    i = _ident(ws)
    fns = "\n".join(f"{f['returns']} {f['name']}({', '.join(p['type'] + ' ' + p['name'] for p in f['params']) or 'void'})"
                    f": {f['operation']} [{', '.join(f['fields'])}]" for f in iface["functions"])
    b = m["budgets"]
    view = " ".join((i["prompt"].get("swe2_dynamic_view") or "an oscillator enable followed by the caller polling the "
                     "LL ready query (the caller bounds the loop), plus a peripheral clock enable and a reset "
                     "assert/release sequence").split())
    instr = (f"Write the design decisions and rationale of the {system_name(ws)} architecture (SWE.2, LL layer) for "
             f"the interface below. {_guidance(ws)} Work-order scope: " + " | ".join(m["scope"]) + ". Texts: components "
             "(the single developed software component SWC_LL, what it owns and what the caller/integration owns); "
             "register_access (register ownership, volatile access, read-modify-write vs whole-register writes per "
             "register, clock and reset semantics); timing_and_error_handling (no waiting or error codes at LL level, "
             "caller-bounded polling); memory_and_stack (justify the budgets flash <= "
             f"{b['flash_bytes']} B, static RAM <= {b['static_ram_bytes']} B, stack <= {b['stack_bytes']} B); "
             "concurrency_and_reentrancy (reentrancy, ISR use, whether a read-modify-write is atomic, how callers "
             "serialise access); safety_and_dependencies (safety mechanisms and degraded states the LL does or does "
             "not provide, dependencies on the caller/integration; never claim compliance). decisions: the "
             f"architecture decisions in one line each. sequences: the dynamic view - {view}; each step calls one "
             "function of the interface; repeat_until is the condition of a caller-bounded loop around that step "
             "('' for no loop).")
    art = [{"path": "lrtx:SWE.2/interfaces", "text": fns, "sha256": sha256_bytes(fns.encode())}]
    return S.packet(phase=PHASE, task="design", role="swe2-author", instructions=instr, sources=[], artifacts=art,
                    criteria=["no compliance or safety-approval claim", "sequence steps use interface functions only"],
                    output_schema=DESIGN_SCHEMA, model=model, findings=findings, previous=previous)


# ---- validation ---------------------------------------------------------------------------------------------------------
def _int(arg: str) -> int | None:
    try:
        return int(arg.strip().rstrip("uUlL"), 0)
    except ValueError:
        return None


def validate_interfaces(ws: Path, doc: dict, idx: dict) -> list[str]:
    i, reqs, cl = _ident(ws), requirements(ws), component_level(ws)
    func = {k: v for k, v in reqs.items() if k not in cl}
    out, fns = [], {}
    for f in doc["functions"]:
        n = f["name"]
        if not n.startswith(i["fn"]) or "<" in n:
            out.append(f"function {n}: the name must start with {i['fn']} and be concrete")
        if n in fns:
            out.append(f"function {n} is defined twice")
        fns[n] = f
        if i["void"] and f["params"]:
            out.append(f"function {n}: LL functions of this work order take no parameters")
        for fld in f["fields"]:
            reg, _, name = fld.partition(".")
            if reg not in idx or name not in idx[reg]["fields"]:
                out.append(f"function {n}: {fld} is not a field of the RM0486 register index")
    alloc = {}
    for a in doc["allocation"]:
        if a["swr"] in alloc:
            out.append(f"{a['swr']} is allocated twice (merge the entries)")
        alloc[a["swr"]] = a["functions"]
        if a["swr"] not in func:
            out.append(f"{a['swr']} is not a functional requirement of this task (component-level or unknown)")
        out += [f"{a['swr']}: function {x} is not defined in functions" for x in a["functions"] if x not in fns]
    out += [f"{s} is not allocated" for s in func if s not in alloc]
    used = {x for v in alloc.values() for x in v}
    out += [f"function {n} is not allocated to any requirement" for n in fns if n not in used]
    for s, text in func.items():
        out += [f"{s} names {n}, which is not a defined function" for n in set(_fn_rx(ws).findall(text))
                if n not in fns and not n.endswith(("_OFFSET", "_MSK", "_POS"))]
    calls = {c["case"]: c for c in doc["calls"]}
    for e in effects(ws):
        c = calls.get(e["case"])
        if c is None:
            out.append(f"case {e['case']} has no call")
            continue
        if c["function"] not in alloc.get(e["swr"], []):
            out.append(f"case {e['case']}: {c['function']} is not allocated to {e['swr']}")
        f = fns.get(c["function"])
        if f is not None and len(c["args"]) != len(f["params"]):
            out.append(f"case {e['case']}: {c['function']} takes {len(f['params'])} argument(s), the call passes "
                       f"{len(c['args'])}")
        if any(not SAFE_ARG.match(a) or re.search(r"[A-Za-z_]\w*\s*\(", a) or ";" in a for a in c["args"]):
            out.append(f"case {e['case']}: arguments must be plain C constants (no calls, no ';')")
        if e["op"] == "write" and f is not None and f["params"] and c["args"]:
            if _int(c["args"][0]) != _int(str(e.get("value"))):
                out.append(f"case {e['case']}: the argument must be the case value {e.get('value')}")
    known = {e["case"] for e in effects(ws)}
    out += [f"call {k} has no register-effect case" for k in calls if k not in known]
    return out


def validate_design(ws: Path, doc: dict, iface: dict) -> list[str]:
    out = []
    ra, cc = doc["register_access"].lower(), doc["concurrency_and_reentrancy"].lower()
    if "volatile" not in ra:
        out.append("register_access must state the volatile access of the register block")
    if not re.search(r"read-modify-write|rmw|whole-register|whole register", ra):
        out.append("register_access must state read-modify-write or whole-register writes per register")
    if "reentran" not in cc or not re.search(r"\bisr\b|interrupt", cc):
        out.append("concurrency_and_reentrancy must address reentrancy and ISR/interrupt use")
    b = _manifest(ws)["budgets"]
    for k in ("flash_bytes", "static_ram_bytes", "stack_bytes"):
        if str(b[k]) not in doc["memory_and_stack"]:
            out.append(f"memory_and_stack must state the {k} budget {b[k]}")
    claims = re.search(r"\b(complian\w*|certif\w*|approved|qualified)\b", " ".join(doc[t] for t in TEXTS), re.I)
    if claims:
        out.append(f"no compliance/approval claim ('{claims.group(0)}'): state facts and open dependencies only")
    names = {f["name"] for f in iface["functions"]}
    for s in doc["sequences"]:
        out += [f"sequence '{s['title']}': {st['function']} is not an interface function" for st in s["steps"]
                if st["function"] not in names]
    if any(f["returns"] == "uint32_t" for f in iface["functions"]) and not any(
            st["repeat_until"].strip() for s in doc["sequences"] for st in s["steps"]):
        out.append("the dynamic view must show a caller-bounded polling loop (repeat_until on a query step)")
    return out


# ---- rendering ----------------------------------------------------------------------------------------------------------
def _sig(f: dict) -> str:
    return f"static inline {f['returns']} {f['name']}({', '.join(p['type'] + ' ' + p['name'] for p in f['params']) or 'void'})"


def render(ws: Path, iface: dict, design: dict) -> dict[str, str]:
    from ..assurance.hardware import index
    from ..inspection.engine import Store

    ws = Path(ws)
    m, i, reqs, cl = _manifest(ws), _ident(ws), requirements(ws), component_level(ws)
    idx = index(ws / "inputs/sections/RM0486")
    secs = _section_files(ws)
    page = {r: next((s["page"] for n, s in secs.items() if s["title"].endswith(f"({r})")), None) for r in idx}
    bl = Store(ws).latest_baseline("SWE.1") or {}
    allswr = sorted(reqs)
    md = ["# Software architecture", "",
          f"Work order: {m['work_order']}. Input baseline: {bl.get('baseline_id', 'UNKNOWN')} (hash "
          f"{bl.get('baseline_hash', 'UNKNOWN')}). Authority: the frozen SWE.1 work products, the work-order manifest and "
          f"the RM0486 sections supplied with the work order.", "",
          "## Components", "", design["components"].strip(), "",
          f"Developed software component: SWC_LL, the header-only LL library {i['header']} (static inline functions). "
          f"The {i['pfx']} register block is hardware, not a software component.", "",
          "## Register access", "", f"Register block: `extern volatile uint32_t {i['block']}[];` placed at the "
          f"{i['pfx']} base address {i['base']}" + (f" (RM0486 p.{i['mm']})" if i["mm"] else "") +
          f" by the linker; host tests define the array in RAM. Every access uses {i['block']}[LL_{i['pfx']}_<REG>_OFFSET "
          "/ 4U]; no integer-to-pointer casts.", "", design["register_access"].strip(), "",
          "## Interfaces", "", "| Function signature | Operation | Register fields |", "| --- | --- | --- |"]
    md += [f"| {_sig(f)} | {f['operation']} | {', '.join(f['fields']) or '-'} |" for f in iface["functions"]]
    md += ["", "Interface ids: IF-01 Caller -> SWC_LL (LL API above); IF-02 SWC_LL -> register block (volatile "
           "register-array access).", "", "## Timing and error handling", "", design["timing_and_error_handling"].strip(),
           "", "## Memory and stack budget", "", "| Budget | Limit | Allocated to | Requirement |", "| --- | --- | --- | --- |"]
    for label, key, word in (("Flash", "flash_bytes", "flash"), ("Static RAM", "static_ram_bytes", "static ram"),
                             ("Stack per API call", "stack_bytes", "stack")):
        ids = [s for s in sorted(cl) if word in reqs[s].lower()]
        md.append(f"| {label} | {m['budgets'][key]} B | SWC_LL | {', '.join(ids) or '-'} |")
    md += ["", design["memory_and_stack"].strip(), "", "## Concurrency and reentrancy", "",
           design["concurrency_and_reentrancy"].strip(), "", "## Safety mechanisms, degraded states and dependencies", "",
           design["safety_and_dependencies"].strip(), "", "## Architecture decisions", ""]
    md += [f"- {d.strip()}" for d in design["decisions"]]
    md += ["", "## Requirement allocation table", "", "| Requirement | Function allocation | Responsibility |",
           "| --- | --- | --- |"]
    alloc = {a["swr"]: a for a in iface["allocation"]}
    for s in allswr:
        if s in alloc:
            md.append(f"| {s} | {', '.join(alloc[s]['functions'])} | {alloc[s]['responsibility']} |")
        else:
            md.append(f"| {s} | all LL functions (component-level constraint of SWC_LL, no dedicated function) | "
                      f"{reqs[s].strip()[:120]} |")
    md += ["", "## Register table", "", f"{i['pfx']} base address {i['base']}. Offsets are bytes; the array index is "
           "offset / 4U.", "", "| Name | Offset | Bit position(s) | Access | RM0486 page |", "| --- | --- | --- | --- | --- |"]
    used = []
    for f in iface["functions"]:
        used += [x for x in f["fields"] if x not in used]
    used += [f"{e['register']}.{e['field']}" for e in effects(ws) if e.get("register") and
             f"{e['register']}.{e['field']}" not in used]
    for x in used:
        reg, _, fld = x.partition(".")
        r = idx[reg]
        fd = r["fields"][fld]
        bits = f"{fd['msb']}:{fd['lsb']}" if fd["msb"] != fd["lsb"] else f"{fd['lsb']}"
        md.append(f"| {reg} | 0x{r['offset']:02X} | {bits} ({fld}) | {'/'.join(fd.get('access') or []) or '-'} | "
                  f"p.{page.get(reg) or '?'} |")
    md.append("")
    st = ["@startuml", f"title {i['pfx']} LL component architecture ({m['work_order']})", "actor Caller",
          f'component "{i["pfx"]}_LL\\n{i["stem"]}" <<SWC>> as SWC_LL',
          f'rectangle "{i["pfx"]} register block ({i["base"]})" as REGS', "",
          f"Caller --> SWC_LL : IF-01 LL API ({len(iface['functions'])} functions)",
          "SWC_LL --> REGS : IF-02 volatile register-array access", "", "note right of SWC_LL",
          "Allocated: " + ", ".join(allswr), "end note", "@enduml", ""]
    dy = ["@startuml", "title " + "; ".join(s["title"] for s in design["sequences"])[:150], "actor Caller",
          f"participant {i['stem']} as LL", f'participant "{i["pfx"]} registers" as REGS']
    fns = {f["name"]: f for f in iface["functions"]}
    for s in design["sequences"]:
        dy.append(f"== {s['title'].strip()} ==")
        for stp in s["steps"]:
            f = fns[stp["function"]]
            if stp["repeat_until"].strip():
                dy.append(f"loop caller-bounded, until {stp['repeat_until'].strip()}")
            dy += [f"Caller -> LL : {f['name']}({', '.join(p['name'] for p in f['params'])})",
                   f"LL -> REGS : {', '.join(f['fields']) or 'register access'}",
                   f"LL --> Caller : {f['returns']}"]
            if stp["repeat_until"].strip():
                dy.append("end")
            if stp["note"].strip():
                dy.append(f"note right : {stp['note'].strip()[:120]}")
    dy += ["@enduml", ""]
    calls = {"schema": "forge-c/api-calls/1",
             "calls": {c["case"]: {"function": c["function"], "args": list(c["args"])} for c in iface["calls"]}}
    return {ARCH: "\n".join(md), STATIC: "\n".join(st), DYNAMIC: "\n".join(dy), CALLS: json.dumps(calls, indent=2) + "\n"}


def self_check(ws: Path) -> list[str]:
    """The deterministic SWE.2 checks the author gate and inspection apply (no new criteria)."""
    from ..assurance import register_contract as RC
    from ..assurance.scope import workspace_scope_findings
    from ..inspection.architecture import check_architecture
    from ..inspection.swtrace import check_architecture_model
    from ..inspection.views import check_views

    ws = Path(ws)
    out = check_architecture(ws)["major_findings"] + check_views(ws, render=False)["major_findings"]
    out += check_architecture_model(ws)["major_findings"] + RC.check_calls(ws) + workspace_scope_findings(ws, PHASE)
    return out


# ---- visit --------------------------------------------------------------------------------------------------------------
def reply(ws: Path, status: str, issues: list[str], budget: dict | None = None, artifacts: list[str] | None = None) -> dict:
    return V.reply(ws, PHASE, status, issues, budget, artifacts)


def visit(ws: Path, model: str, max_calls: int | None = None) -> dict:
    from ..assurance.hardware import index
    from ..layer import layer_of
    from ..registry.agents import load_agents

    ws = Path(ws)
    if layer_of(ws) != "LL":
        return reply(ws, "FAILED", ["LRTX_SWE2_LAYER_NOT_SUPPORTED_YET (structured SWE.2 covers LL work orders)"])
    role = {a.id: a for a in load_agents()[0]}["swe2-author"]
    vlog = ws / ".forge-run/lrtx/SWE.2/visits.jsonl"
    since = json.loads(vlog.read_text().splitlines()[-1])["at"] if vlog.is_file() and vlog.read_text().strip() else ""
    findings = V.rework_findings(ws, PHASE, since) if since else []
    routed: dict[str, list[str]] = {}
    for f in findings:  # requirement/case/function findings belong to the interface task, the rest to the design
        key = "interfaces" if re.search(r"SWR-\d{3}|CONTRACT_|ALLOCAT|INTERFACE_NOT|PLACEHOLDER", f) else "design"
        routed.setdefault(key, []).append(f)
    budget = {"calls": 0, "max_calls": max_calls or role.max_turns, "schema_mode": "json_schema"}
    idx = index(ws / "inputs/sections/RM0486")
    iface = V.run_task(ws, PHASE, "interfaces", lambda fi, pr: interfaces_packet(ws, model, fi, pr),
                       lambda d: validate_interfaces(ws, d, idx), budget, routed.get("interfaces"))
    if iface["status"] != "VALID":
        return reply(ws, "FAILED", [f"interfaces: {e}" for e in iface["errors"][:10]], budget)
    design = V.run_task(ws, PHASE, "design", lambda fi, pr: design_packet(ws, model, iface["doc"], fi, pr),
                        lambda d: validate_design(ws, d, iface["doc"]), budget, routed.get("design"))
    if design["status"] != "VALID":
        return reply(ws, "FAILED", [f"design: {e}" for e in design["errors"][:10]], budget)
    files = render(ws, iface["doc"], design["doc"])
    V.write_scoped(ws, files, "swe2_author")
    checks = self_check(ws)
    if checks and budget["calls"] < budget["max_calls"]:  # one localized repair round on the gates' own findings
        iv = [c for c in checks if re.search(r"SWR|CONTRACT_|ALLOCAT|INTERFACE|PLACEHOLDER|UNKNOWN", c)]
        if iv:
            iface = V.run_task(ws, PHASE, "interfaces", lambda fi, pr: interfaces_packet(ws, model, fi, pr),
                               lambda d: validate_interfaces(ws, d, idx), budget, iv)
        rest = [c for c in checks if c not in iv]
        if rest and iface["status"] == "VALID":
            design = V.run_task(ws, PHASE, "design", lambda fi, pr: design_packet(ws, model, iface["doc"], fi, pr),
                                lambda d: validate_design(ws, d, iface["doc"]), budget, rest)
        bad = [r for r in (iface, design) if r["status"] != "VALID"]
        if bad:
            return reply(ws, "FAILED", [f"{r['task']}: {e}" for r in bad for e in r["errors"][:8]], budget)
        files = render(ws, iface["doc"], design["doc"])
        V.write_scoped(ws, files, "swe2_author")
        checks = self_check(ws)
    S.record(ws, "SWE.2/assembly.json", {"schema": "forge-c/lrtx-swe2-assembly/1", "at": utc_now(), "files": sorted(files)})
    if checks:
        return reply(ws, "FAILED", checks[:20], budget)
    return reply(ws, "PASS", [], budget, artifacts=sorted(files))
