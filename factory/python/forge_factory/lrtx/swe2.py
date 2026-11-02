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

from ..assurance import register_contract as RC
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
# F011 (local-rtx-v2, structured.swe2_named_functions): the frozen SWE.1 requirements fix the names of the functions
# they name. Measured 2026-10-22 (F011-T032): qwen3-coder:30b kept LL_IWDG_IsActive for a requirement naming
# LL_IWDG_IsEnabled through every repair with the exact finding. The name becomes a key of the output schema; the model
# describes the function, it cannot rename it. Functions no requirement names stay free (other_functions).
FN_DETAIL_SCHEMA = {**FN_SCHEMA, "required": [k for k in FN_SCHEMA["required"] if k != "name"],
                    "properties": {k: v for k, v in FN_SCHEMA["properties"].items() if k != "name"}}
# Instance mode (operation_scope.instance): the declared API contract fixes every signature, so the model answers only
# the operation and the fields of each declared function; normalize_interfaces fills returns/params from the contract.
FIXED_SIG = ("returns", "params")
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


def _cell(text: str) -> str:
    """A whole text in one markdown table cell (no truncation; pipes and line breaks cannot split the row)."""
    return " ".join(str(text).split()).replace("|", "\\|")


def _field_bits(ws: Path) -> dict[str, str]:
    """REGISTER.FIELD -> 'REGISTER.FIELD (bits m:l)' from the RM0486 register index the register table is rendered from
    (CAPA-109: the design task saw field names only and called the PR width/mask undecidable)."""
    from ..assurance.hardware import index

    out = {}
    for reg, r in index(Path(ws) / "inputs/sections/RM0486").items():
        for fld, fd in (r.get("fields") or {}).items():
            b = f"{fd['msb']}:{fd['lsb']}" if fd["msb"] != fd["lsb"] else f"{fd['lsb']}"
            out[f"{reg}.{fld}"] = f"{reg}.{fld} (bit{'s' if ':' in b else ''} {b})"
    return out


def _ident(ws: Path) -> dict:
    from ..layer import profile, register_prefix

    p = profile(ws)
    return {"pfx": register_prefix(ws), "fn": p["ll"]["function_prefix"], "header": p["ll"]["header"],
            "stem": Path(p["ll"]["header"]).stem, "block": p["ll"]["register_block"], "base": p["base_address"],
            "mm": p.get("mm_page"), "void": p["ll"].get("void_signatures", True), "prompt": p.get("prompt") or {}}


def instance(ws: Path) -> dict | None:
    from ..layer import ll_instance

    return ll_instance(ws)


def _param(p: dict) -> str:
    """`uint32_t value`; a pointer type is rendered `CRC_TypeDef *CRCx` (instance mode)."""
    return f"{p['type']}{p['name']}" if p["type"].endswith("*") else f"{p['type']} {p['name']}"


def _access(ws: Path, inst: dict) -> str:
    """Instance mode: how the LL reaches its registers (the caller's instance, never the register-block array)."""
    i = _ident(ws)
    members = ", ".join(f"{r}: {inst['parameter']}->{m}" for r, m in inst["members"].items())
    return (f"register access only through the caller-supplied instance pointer {inst['parameter']} of type "
            f"{inst['type_name']} * declared in the pinned device header {inst['device_header']} ({members}); the "
            f"caller passes the instance macro {inst['macro']} (the {i['pfx']} base {i['base']} on the target, the RAM "
            f"object {inst['host_object']} in host tests); no register-block array, no singleton, no integer-to-pointer "
            "casts in the driver")


def _guidance(ws: Path) -> str:
    """The LL architecture rules of the agent prompt (profile texts for a non-RCC peripheral), not new policy."""
    from ..workflow import prompts

    i = _ident(ws)
    api = " ".join((i["prompt"].get("ll_api") or prompts.LL_API).split())
    inst = instance(ws)
    if inst is not None:
        return (f"LL functions: {api}. Header-only static inline functions in {i['header']}; no waiting, no timeouts, "
                "no error codes at LL level (callers bound their own polling); no driver-owned state; "
                f"{_access(ws, inst)}; a field update is a read-modify-write that preserves the other bits unless the "
                "register is write-only (then a whole-register write).")
    return (f"LL functions: {api}. Header-only static inline functions in {i['header']}; no waiting, no timeouts, no "
            "error codes at LL level (callers bound their own polling); no driver-owned state; register access through "
            f"the extern volatile uint32_t register-block array {i['block']} placed at the base {i['base']} by the "
            "linker, indexed by offset/4, no integer-to-pointer casts; a field update is a read-modify-write that "
            "preserves the other bits unless the register is write-only (then a whole-register write).")


def _fn_rx(ws: Path) -> re.Pattern:
    return re.compile(rf"\b{re.escape(_ident(ws)['fn'])}\w+")


# ---- packets -----------------------------------------------------------------------------------------------------------
def _structured_flag(ws: Path, key: str) -> bool:
    man = Path(ws) / ".forge-run/manifest.json"
    prof_id = (json.loads(man.read_text()).get("local_profile") or {}).get("id") if man.is_file() else None
    if not prof_id:
        return False
    from .profile import load

    return bool((load(prof_id).get("structured") or {}).get(key))


def named_mode(ws: Path) -> bool:
    return _structured_flag(ws, "swe2_named_functions")


def constrained_design(ws: Path) -> bool:
    """F011-T032 (local-rtx-v2, structured.swe2_constrained_design): the design answer may name only the functions of
    the accepted interface in its sequence steps, and the prompt no longer seeds the words the claim check refuses."""
    return _structured_flag(ws, "swe2_constrained_design")


def design_schema(ws: Path, iface: dict) -> dict:
    if not constrained_design(ws):
        return DESIGN_SCHEMA
    schema = json.loads(json.dumps(DESIGN_SCHEMA))
    step = schema["properties"]["sequences"]["items"]["properties"]["steps"]["items"]["properties"]
    step["function"] = {"type": "string", "enum": [f["name"] for f in iface["functions"]]}
    return schema


def named_functions(ws: Path) -> list[str]:
    """The functions the functional requirements name (register-name constants excluded), in first-mention order."""
    reqs, cl, rx = requirements(ws), component_level(ws), _fn_rx(ws)
    out: list[str] = []
    for s, text in reqs.items():
        if s in cl:
            continue
        out += [n for n in rx.findall(text) if n not in out and not n.endswith(("_OFFSET", "_MSK", "_POS"))]
    return out


def _fn_schemas(ws: Path) -> tuple[dict, dict]:
    """(function item, named-function detail) schemas; instance mode: declared names only, no signature fields."""
    inst = instance(ws)
    if inst is None:
        return FN_SCHEMA, FN_DETAIL_SCHEMA
    props = {k: v for k, v in FN_SCHEMA["properties"].items() if k not in FIXED_SIG}
    fn = {**FN_SCHEMA, "required": [k for k in FN_SCHEMA["required"] if k not in FIXED_SIG],
          "properties": {**props, "name": {"type": "string", "enum": list(inst["signatures"])}}}
    detail = {**fn, "required": [k for k in fn["required"] if k != "name"],
              "properties": {k: v for k, v in props.items() if k != "name"}}
    return fn, detail


def interfaces_schema(ws: Path) -> dict:
    fn, detail = _fn_schemas(ws)
    names = named_functions(ws) if named_mode(ws) else []
    if not names:  # measured (T032, RCC-LL rc1): requirements naming no function left no place for any function
        if fn is FN_SCHEMA:
            return INTERFACES_SCHEMA
        schema = json.loads(json.dumps(INTERFACES_SCHEMA))
        schema["properties"]["functions"]["items"] = fn
        return schema
    props = {k: v for k, v in INTERFACES_SCHEMA["properties"].items() if k != "functions"}
    return {"type": "object", "additionalProperties": False,
            "required": ["named_functions", "other_functions", "allocation", "calls"],
            "properties": {"named_functions": {"type": "object", "additionalProperties": False, "required": names,
                                               "properties": {n: detail for n in names}},
                           "other_functions": {"type": "array", "items": fn}, **props}}


def normalize_interfaces(ws: Path, doc: dict) -> dict:
    """The named-function answer in the feature 010 shape every check and renderer reads (instance mode: with the
    signatures of the declared API contract; a function it does not declare gets none and is a validation finding)."""
    inst = instance(ws)
    if "named_functions" in doc:
        fns = [{"name": n, **v} for n, v in doc["named_functions"].items()] + list(doc.get("other_functions") or [])
        doc = {"functions": fns, **{k: v for k, v in doc.items() if k not in ("named_functions", "other_functions")}}
    elif inst is None:
        return doc
    if inst is None:
        return doc
    sigs = inst["signatures"]
    fns = [{**f, **json.loads(json.dumps(sigs.get(f["name"], {"returns": "void", "params": []})))}
           for f in doc["functions"]]
    return {**doc, "functions": fns}


def interfaces_packet(ws: Path, model: str, findings=None, previous=None) -> dict:
    reqs, cl = requirements(ws), component_level(ws)
    func = {k: v for k, v in reqs.items() if k not in cl}
    listing = "\n".join(f"{k}: {v}" for k, v in func.items())
    cases = "\n".join(f"{e['case']}: {e['swr']} {e.get('register', '')}.{e.get('field', '')} op {e['op']}"
                      + RC.value_text(e) for e in effects(ws))
    art = [{"path": "workproducts/SWE.1/software_requirements.md#functional", "text": listing,
            "sha256": sha256_bytes(listing.encode())},
           {"path": "workproducts/SWE.1/register_effects.json#cases", "text": cases, "sha256": sha256_bytes(cases.encode())}]
    i, inst = _ident(ws), instance(ws)
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
    if any(e.get("requested") not in (None, "") for e in effects(ws)):  # CAPA-120: unchanged text without one
        instr += (" A write case that lists a requested input passes exactly that requested input, never the field "
                  "value it truncates to.")
    if inst is not None:
        sigs = "; ".join(_sig({"name": n, **s}) for n, s in inst["signatures"].items())
        instr = instr.replace(
            f"never a placeholder such as {i['fn']}<Name>_Enable), with its return type (void for commands, uint32_t "
            "1U/0U for queries), its uint32_t parameters (" + ("none: LL functions take no arguments" if i["void"]
                                                               else "only value setters take one uint32_t value") + ")",
            f"only the functions of the API contract {inst['api_contract']}, whose signatures are fixed: {sigs}; the "
            "answer gives no return type or parameters)")
        instr = instr.replace("its C arguments (decimal", f"its C arguments in parameter order: first the instance "
                              f"macro {inst['macro']}, then the value arguments (decimal")
    if named_mode(ws) and named_functions(ws):
        instr += (" The functions the frozen requirements name are fixed: describe each under named_functions, keyed by "
                  "that exact name; put any further function an operation needs under other_functions.")
    if cl:  # CAPA-109: say where the unlisted SWE.1 requirements are allocated (a responsibility called them "outside")
        instr += (f" The component-level constraints {', '.join(sorted(cl))} of the frozen SWE.1 requirements are not "
                  "listed: the architecture allocates them to SWC_LL as a whole and the design texts justify them.")
    crit = ["every listed requirement is allocated", "every function is allocated to at least one requirement",
            "every case has one call of a function allocated to its requirement"]
    return S.packet(phase=PHASE, task="interfaces", role="swe2-author", instructions=instr, sources=[],
                    artifacts=art, criteria=crit, output_schema=interfaces_schema(ws), model=model, findings=findings,
                    previous=previous)


def design_packet(ws: Path, model: str, iface: dict, findings=None, previous=None) -> dict:
    m = _manifest(ws)
    i = _ident(ws)
    bits = _field_bits(ws)
    fns = "\n".join(f"{f['returns']} {f['name']}({', '.join(_param(p) for p in f['params']) or 'void'})"
                    f": {f['operation']} [{', '.join(bits.get(x, x) for x in f['fields'])}]" for f in iface["functions"])
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
    if constrained_design(ws):  # measured (T032): models echo "compliance" from this instruction into their texts
        instr = instr.replace("; never claim compliance)", "; state facts only, with no statement about conformity "
                              "to a standard or about approval status)")
        instr += " Each step's function is the bare function name exactly as listed, without a parameter list."
    instr += (" The register fields of the interface carry their RM0486 bit positions (the architecture's register "
              "table shows the same); they are decided facts.")
    art = [{"path": "lrtx:SWE.2/interfaces", "text": fns, "sha256": sha256_bytes(fns.encode())}]
    reqs = requirements(ws)
    cons = "\n".join(f"{k}: {reqs[k]}" for k in sorted(component_level(ws)) if k in reqs)
    if cons:  # CAPA-109: the design texts justify these (the inspector asks for e.g. the instruction/time budgets)
        art.append({"path": "workproducts/SWE.1/software_requirements.md#component-level", "text": cons,
                    "sha256": sha256_bytes(cons.encode())})
    return S.packet(phase=PHASE, task="design", role="swe2-author", instructions=instr, sources=[], artifacts=art,
                    criteria=["no compliance or safety-approval claim", "sequence steps use interface functions only"],
                    output_schema=design_schema(ws, iface), model=model, findings=findings, previous=previous)


# ---- validation ---------------------------------------------------------------------------------------------------------
def _int(arg: str) -> int | None:
    try:
        return int(arg.strip().rstrip("uUlL"), 0)
    except ValueError:
        return None


def _value_index(ws: Path, f: dict) -> int:
    """Index of the value argument: the first parameter (legacy), the first non-instance parameter (instance mode)."""
    if instance(ws) is None:
        return 0
    return next((k for k, p in enumerate(f["params"]) if not p["type"].endswith("*")), len(f["params"]))


def validate_interfaces(ws: Path, doc: dict, idx: dict) -> list[str]:
    i, reqs, cl = _ident(ws), requirements(ws), component_level(ws)
    inst = instance(ws)
    func = {k: v for k, v in reqs.items() if k not in cl}
    out, fns = [], {}
    for f in doc["functions"]:
        n = f["name"]
        if not n.startswith(i["fn"]) or "<" in n:
            out.append(f"function {n}: the name must start with {i['fn']} and be concrete")
        if n in fns:
            out.append(f"function {n} is defined twice")
        fns[n] = f
        if inst is not None and n not in inst["signatures"]:
            out.append(f"function {n} is not declared by the API contract {inst['api_contract']} (declared: "
                       f"{', '.join(inst['signatures'])})")
        elif i["void"] and f["params"] and inst is None:
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
    if inst is not None:
        out += [f"function {n} of the API contract {inst['api_contract']} is not defined" for n in inst["signatures"]
                if n not in fns]
    used = {x for v in alloc.values() for x in v}
    out += [f"function {n} is not allocated to any requirement" for n in fns if n not in used]
    for s, text in func.items():
        # T016 SWE.2 trial (2026-10-21): the bare finding left the model naming the function differently through all
        # repairs (LL_IWDG_IsActive for LL_IWDG_IsEnabled); the frozen requirement fixes the name, so say what to do
        out += [f"{s} names {n}, which is not a defined function - the frozen SWE.1 requirement fixes this name: "
                f"define the function as {n} (rename the function you gave another name) and allocate {s} to it"
                + (f" (functions now allocated to {s}: {', '.join(alloc[s])})" if alloc.get(s) else "")
                for n in sorted(set(_fn_rx(ws).findall(text))) if n not in fns and not n.endswith(("_OFFSET", "_MSK", "_POS"))]
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
        if inst is not None and f is not None and c["args"] and c["args"][0].strip() != inst["macro"]:
            out.append(f"case {e['case']}: the first argument must be the instance macro {inst['macro']}")
        k = _value_index(ws, f) if f is not None else 0
        if e["op"] == "write" and f is not None and len(f["params"]) > k and len(c["args"]) > k:
            # CAPA-120: a truncating write passes the requested input (0x1234), not the field value it leaves (0x234)
            if _int(c["args"][k]) != _int(str(RC.call_input(e))):
                out.append(f"case {e['case']}: the argument must be the case value {e.get('value')}"
                           if e.get("requested") in (None, "") else
                           f"case {e['case']}: the argument must be the requested input {e['requested']} (the field "
                           f"keeps {e.get('value')})")
    known = {e["case"] for e in effects(ws)}
    out += [f"call {k} has no register-effect case" for k in calls if k not in known]
    return out


def _status_query(ws: Path, f: dict) -> bool:
    """Owner 2026-11-02 ("Status queries only"): a caller polls a status or flag, not a data value. A uint32_t query is a
    status query when it reads a one-bit field or a status register (<P>_SR, <P>_ISR); a data read such as
    LL_CRC_Read_IDR (CRC_IDR.IDR, 32 bits) needs no polling loop. Without the register index every uint32_t query
    counts, as before."""
    if f.get("returns") != "uint32_t":
        return False
    from ..assurance.hardware import index

    try:
        idx = index(Path(ws) / "inputs/sections/RM0486")
    except OSError:
        idx = {}
    fields = [fld.partition(".") for fld in f.get("fields") or []]
    if not idx or not fields:
        return True
    for reg, _, name in fields:
        bit = (idx.get(reg) or {}).get("fields", {}).get(name)
        if bit is None or bit["msb"] == bit["lsb"] or re.search(r"_I?SR$", reg):
            return True
    return False


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
    if any(_status_query(ws, f) for f in iface["functions"]) and not any(
            st["repeat_until"].strip() for s in doc["sequences"] for st in s["steps"]):
        out.append("the dynamic view must show a caller-bounded polling loop (repeat_until on a query step)")
    return out


# ---- rendering ----------------------------------------------------------------------------------------------------------
def _sig(f: dict) -> str:
    return f"static inline {f['returns']} {f['name']}({', '.join(_param(p) for p in f['params']) or 'void'})"


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
    inst = instance(ws)
    if inst is None:
        access = (f"Register block: `extern volatile uint32_t {i['block']}[];` placed at the {i['pfx']} base address "
                  f"{i['base']}" + (f" (RM0486 p.{i['mm']})" if i["mm"] else "") + " by the linker; host tests define "
                  f"the array in RAM. Every access uses {i['block']}[LL_{i['pfx']}_<REG>_OFFSET / 4U]; no "
                  "integer-to-pointer casts.")
        if2, table = "volatile register-array access", "the array index is offset / 4U."
    else:
        members = ", ".join(f"{r} -> {inst['parameter']}->{m}" for r, m in inst["members"].items())
        access = (f"Register instance: the caller supplies `{inst['type_name']} *{inst['parameter']}`, the typed "
                  f"register layout of the pinned device header {inst['device_header']} (offsets checked against "
                  f"RM0486). The caller passes the instance macro {inst['macro']}: the {i['pfx']} base address "
                  f"{i['base']}" + (f" (RM0486 p.{i['mm']})" if i["mm"] else "") + f" on the target, the RAM object "
                  f"{inst['host_object']} in host tests. Every access uses {inst['parameter']}-><MEMBER> ({members}); "
                  "no register-block array, no singleton, no integer-to-pointer casts in the driver.")
        if2 = f"volatile typed register access through the caller's {inst['type_name']} instance"
        table = f"each register is the {inst['type_name']} member at that offset."
    md = ["# Software architecture", "",
          f"Work order: {m['work_order']}. Input baseline: {bl.get('baseline_id', 'UNKNOWN')} (hash "
          f"{bl.get('baseline_hash', 'UNKNOWN')}). Authority: the frozen SWE.1 work products, the work-order manifest and "
          f"the RM0486 sections supplied with the work order.", "",
          "## Components", "", design["components"].strip(), "",
          f"Developed software component: SWC_LL, the header-only LL library {i['header']} (static inline functions). "
          f"The {i['pfx']} register block is hardware, not a software component.", "",
          "## Register access", "", access, "", design["register_access"].strip(), "",
          "## Interfaces", "", "| Function signature | Operation | Register fields |", "| --- | --- | --- |"]
    md += [f"| {_sig(f)} | {f['operation']} | {', '.join(f['fields']) or '-'} |" for f in iface["functions"]]
    md += ["", f"Interface ids: IF-01 Caller -> SWC_LL (LL API above); IF-02 SWC_LL -> register block ({if2}).",
           "", "## Timing and error handling", "", design["timing_and_error_handling"].strip(),
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
            # CAPA-106 (run WO-F014-CMP-SWE2-OBL-20261102-01): the text was cut at 120 characters, so the budgets of
            # SWR-012/SWR-013 ("within 64 executed target instructions", "100 microseconds") vanished from the
            # architecture and the inspector failed SWE2-05 three times; the full requirement is the allocation
            md.append(f"| {s} | all LL functions (component-level constraint of SWC_LL, no dedicated function) | "
                      f"{_cell(reqs[s])} |")
    md += ["", "## Register table", "", f"{i['pfx']} base address {i['base']}. Offsets are bytes; {table}", "",
           "| Name | Offset | Bit position(s) | Access | RM0486 page |", "| --- | --- | --- | --- | --- |"]
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
          f"SWC_LL --> REGS : IF-02 {if2}", "", "note right of SWC_LL",
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
    inst = instance(ws)
    if inst is not None:  # instance mode: the call contract compiles against the declared API contract (as the gate)
        out += RC.check_compiles(ws, [], inst["api_contract"])
    return out


# ---- visit --------------------------------------------------------------------------------------------------------------
# CAPA-109 (run WO-F014-CMP-SWE2-IWDG-20261102-03): every finding naming an SWR id went to the interface task only, so
# inspector findings on the design texts that cite a requirement as evidence ("Safety mechanisms ... lists the PR field
# width as unresolved, contradicting ... SWR-005") never reached the design task; its unchanged checkpoint was reused
# and SWE2-06 failed three times. A finding goes to the task(s) owning the architecture section(s) it locates.
SECTIONS = re.compile(
    r"\b(?P<design>components? section|register[ _]access|timing[ _]and[ _]error|memory[ _]and[ _]stack|concurren\w*|"
    r"reentran\w*|safety[ _]mechanisms?|safety[ _]and[ _]dependencies|degraded[ _]states?|dependencies|"
    r"architecture[ _]decisions?|decisions section|dynamic[ _]view|architecture_dynamic|sequences?)\b"
    r"|\b(?P<interfaces>interfaces(?: table| section)?|interface (?:table|section)|requirement[ _]allocation|"
    r"allocation[ _](?:table|rows?|entr(?:y|ies))|api_calls|static[ _]view|architecture_static|function signatures?)\b",
    re.I)
_LABEL = re.compile(r"^\s*(?:SWE\d-\d+|minor|major|critical)\s*(?::|-|\u2014|\u2013)\s*", re.I)


def _owners(text: str) -> list[str]:
    return list(dict.fromkeys(m.lastgroup for m in SECTIONS.finditer(text)))


def route(findings: list[str]) -> dict[str, list[str]]:
    """Task -> findings. A visit's own failure names its task ('design: ...'); interface-contract codes go to the
    interface task. An inspector finding ('<id>: [severity] <path>, <sections>: <defect>') goes to the owners of the
    sections its location names; without a location clause, to the owner of the first section it names (later
    mentions are evidence: "... contradicting its Interfaces table"). A finding naming no section keeps the earlier
    rule (an SWR id -> interfaces, else design). Nothing is dropped."""
    routed: dict[str, list[str]] = {}
    for f in findings:
        own = re.match(r"(interfaces|design): ", f)
        if own:
            keys = [own.group(1)]
        else:
            keys = ["interfaces"] if re.search(r"CONTRACT_|ALLOCAT|INTERFACE_NOT|PLACEHOLDER", f) else []
            body = f
            while _LABEL.match(body):
                body = _LABEL.sub("", body, count=1)
            located = _owners(body.split(": ", 1)[0]) if ": " in body else []
            keys += located or _owners(body)[:1]
            keys = keys or ["interfaces" if re.search(r"SWR-\d{3}", f) else "design"]
        for k in sorted(set(keys)):
            routed.setdefault(k, []).append(f)
    return routed


def reply(ws: Path, status: str, issues: list[str], budget: dict | None = None, artifacts: list[str] | None = None) -> dict:
    return V.reply(ws, PHASE, status, issues, budget, artifacts)


def visit(ws: Path, model: str, max_calls: int | None = None, resume: bool = False,
          time_budget_s: float | None = None) -> dict:
    """One author visit (or its continuation after a time box, `resume`)."""
    from ..layer import layer_of
    from ..registry.agents import load_agents

    ws = Path(ws)
    if layer_of(ws) != "LL":
        return reply(ws, "FAILED", ["LRTX_SWE2_LAYER_NOT_SUPPORTED_YET (structured SWE.2 covers LL work orders)"])
    role = {a.id: a for a in load_agents()[0]}["swe2-author"]
    since = V.last_finished(ws, PHASE)
    budget, findings = V.open_visit(ws, PHASE, resume, lambda: V.rework_findings(ws, PHASE, since) if since else [],
                                    V.author_call_limit(ws, PHASE, role.max_turns, max_calls), time_budget_s)
    if findings:
        V.attach_keep_fixed(ws, PHASE, budget, route)
    try:
        return _visit(ws, model, budget, findings)
    except V.Continue as c:
        return reply(ws, "CONTINUE", [f"time box used; the next node execution resumes at {c}"], budget)


def _visit(ws: Path, model: str, budget: dict, findings: list[str]) -> dict:
    from ..assurance.hardware import index

    routed = route(findings)
    idx = index(ws / "inputs/sections/RM0486")
    iface = V.run_task(ws, PHASE, "interfaces", lambda fi, pr: interfaces_packet(ws, model, fi, pr),
                       lambda d: validate_interfaces(ws, normalize_interfaces(ws, d), idx), budget,
                       routed.get("interfaces"))
    iface = {**iface, "doc": normalize_interfaces(ws, iface["doc"]) if iface.get("doc") else iface.get("doc")}
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
                               lambda d: validate_interfaces(ws, normalize_interfaces(ws, d), idx), budget, iv)
            iface = {**iface, "doc": normalize_interfaces(ws, iface["doc"]) if iface.get("doc") else iface.get("doc")}
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
