"""Feature 020 T020 (research R1, R4-R6; FR-014..FR-019, FR-022): the structured functional-level SWE.1 author.

Selected by the runner only for a work order whose manifest says `swe1_level: functional`; register-level orders keep
`swe1.py` unchanged. Module facts come from the governance inventory and the governance package (D10/SC-009).

1. Task plan (deterministic): one task per service group of the order's scope rule (in-scope groups in inventory
   order; the packet names the group's delivered functions and the use cases that exercise them - for an LL component
   this is its LL service group), one state-behaviour task over the whole in-scope API, and one HAL design-constraint
   task from the order's guideline input(s).
2. Packets (bounded, no lessons): the input section index, the RM sections the group's use cases rely on, the guideline
   for the design-constraint task, the functional-level skill reference (hash-bound, D15) and compact artifacts (task
   scope, input register). Never a chapter text and never delivered code.
3. Answer schema: contracts/functional-requirement.schema.json, built from config/factory/swe1-functional-template.yaml
   (its conditional rules are the deterministic validators below).
4. Validators (per task and at the gate): attributes, origin group of the task, group/link consistency, input ids of
   the input register with role requirement_source, no delivered code as a source, the level rule (no register, field,
   register-block member or CMSIS register symbol of the order's RM register index / device header, no hexadecimal
   value), EARS with a system name, design constraints verified by inspection, known use cases.
5. Assembly (deterministic): software_requirements.md (`**SWR-NNN**`, Source:, Verification:, then the attribute
   lines), requirement_attributes.json, requirements_to_tests.csv, the safety statement and
   .forge-run/lrtx/SWE.1/assembly.json in the shape swe1_quality reads; `replace_requirement` splices one requirement
   for the feature 018 phase 1.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import canonical_json, sha256_bytes, utc_now
from ..governance import inventory as GI
from ..governance import level as L
from ..governance import package as GP
from . import structured as S
from . import visit as V

PHASE = "SWE.1"
REQS = "workproducts/SWE.1/software_requirements.md"
ATTRS = "workproducts/SWE.1/requirement_attributes.json"
CSV = "traceability/requirements_to_tests.csv"
SAFETY = "safety/software_safety_requirements.md"
ATTR_SCHEMA = "forge-c/swe1-requirement-attributes/1"
TASK_STATE = "requirements:state_behaviour"
TASK_DESIGN = "requirements:design_constraints"
ORIGINS = {"group": ["use_case", "out_of_context", "awaiting_traceability"],
           "state": ["state_behaviour", "awaiting_traceability"],
           "design": ["hal_design_constraint"]}
LENGTHS = {"key": {"minLength": 1}, "title": {"minLength": 3, "maxLength": 80},
           "statement": {"minLength": 10, "maxLength": 600}, "precondition": {"minLength": 1}}
TOKEN = re.compile(r"(?<![A-Za-z0-9_])([A-Z][A-Z0-9_]+)(?![A-Za-z0-9_])")
REG_TITLE = re.compile(r"\(([A-Z][A-Z0-9]*_[A-Z0-9_]+)\)")
FIELD = re.compile(r"\bBits?\s+\d+(?::\d+)?\s+([A-Z][A-Z0-9_]*)(?:\[[^\]]*\])?\s*:")
SECTION_ID = re.compile(r"(?<![\d.])(\d+(?:\.\d+)*)(?![\d.])")
# D24 (T027): a guideline larger than this is partitioned into bounded design tasks (the real HAL driver guideline is
# 444 kB: one design packet of ~171k estimated tokens, against <= 31k for every other functional author packet)
DESIGN_PART_CHARS = 120_000
GUIDE_HEADING = re.compile(r"^(?:#{1,6}\s|\s*\d{1,2}(?:\.\d{1,2})?\.?\s+[A-Z])")


# ---- inputs of the author --------------------------------------------------------------------------------------------
def _manifest(ws: Path) -> dict:
    return json.loads((Path(ws) / ".forge-run/manifest.json").read_text())


def template(ws: Path) -> dict:
    return L.template(_manifest(ws))


def governance_package(ws: Path) -> dict:
    """The governance package the author builds on: generated, coverage passed and unchanged (else ValueError)."""
    st = GP.status(ws)
    p = Path(ws) / GP.OUT_JSON
    if st is None or st.get("state") != GP.PASS or not p.is_file():
        raise ValueError(f"SWE1_FUNCTIONAL_GOVERNANCE_NOT_PASSED:{(st or {}).get('state', 'NOT_GENERATED')}")
    pkg = json.loads(p.read_text())
    if pkg.get("package_version") != st.get("package_version") or GP.version(pkg) != st["package_version"]:
        raise ValueError("SWE1_FUNCTIONAL_GOVERNANCE_NOT_PASSED:GOVERNANCE_PACKAGE_CHANGED")
    return pkg


def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").lower() or "group"


def _guideline_inputs(ws: Path, inv: dict) -> list[str]:
    """Input ids of the order's guideline inputs (manifest role naming a guideline)."""
    names = {Path(i["path"]).name for i in _manifest(ws).get("inputs") or [] if "guideline" in str(i.get("role", ""))}
    return [r["input_id"] for r in inv["inputs"] if r["role"] == GI.SOURCE and r["name"] in names]


def guideline_parts(text: str, limit: int | None = None) -> list[tuple[int, int]]:
    """[start, end) line ranges that partition `text` into consecutive parts of at most `limit` characters, cut at
    heading lines (markdown or numbered sections) where possible; never truncated - every line is in exactly one part
    (a single line longer than the bound is a part of its own)."""
    limit = DESIGN_PART_CHARS if limit is None else limit
    lines = text.splitlines(keepends=True)
    cuts = [0] + [i for i, ln in enumerate(lines) if i and GUIDE_HEADING.match(ln)] + [len(lines)]
    segs: list[tuple[int, int, int]] = []
    for a, b in zip(cuts, cuts[1:]):
        start, size = a, 0
        for i in range(a, b):  # a section over the bound is split at line boundaries
            if size and size + len(lines[i]) > limit:
                segs.append((start, i, size))
                start, size = i, 0
            size += len(lines[i])
        if b > start:
            segs.append((start, b, size))
    parts: list[tuple[int, int]] = []
    size = 0
    for a, b, n in segs:
        if parts and size + n <= limit:
            parts[-1] = (parts[-1][0], b)
            size += n
        else:
            parts.append((a, b))
            size = n
    return parts or [(0, len(lines))]


def _design_tasks(ws: Path, inv: dict, gl: list[str]) -> list[dict]:
    """One design task over the guideline input(s) when each fits the bound (as before), else one per part (D24)."""
    head = {"kind": "design", "origins": ORIGINS["design"], "heading": "HAL design constraints"}
    names = {r["input_id"]: r["name"] for r in inv["inputs"]}
    paths = {Path(i["path"]).name: i["path"] for i in _manifest(Path(ws)).get("inputs") or []}
    split = []
    for g in gl:
        rel = paths.get(names[g])
        text = (Path(ws) / rel).read_text(errors="replace") if rel and (Path(ws) / rel).is_file() else ""
        split += [(g, rel, part) for part in guideline_parts(text)]
    if len(split) == len(gl):
        return [{"id": TASK_DESIGN, **head, "guideline": gl}]
    return [{"id": f"{TASK_DESIGN}_p{n}", **head, "guideline": [g],
             "part": {"path": rel, "lines": [a + 1, b], "n": n, "of": len(split)}}
            for n, (g, rel, (a, b)) in enumerate(split, 1)]


def plan(ws: Path) -> list[dict]:
    """The author's tasks (deterministic): service groups, state behaviour, HAL design constraints."""
    inv, pkg = GI.load(ws), governance_package(ws)
    groups: dict[str, list[str]] = {}
    for a in inv["api"]:
        if a["scope_class"] == "in":
            groups.setdefault(a["scope_group"], []).append(a["function"])
    out, used = [], set()
    for g, fns in groups.items():
        tid, n = f"requirements:g_{_slug(g)}", 2
        while tid in used:
            tid, n = f"requirements:g_{_slug(g)}_{n}", n + 1
        used.add(tid)
        ucs = [u for u in pkg["use_cases"] if set(u.get("functions") or []) & set(fns)]
        out.append({"id": tid, "kind": "group", "group": g, "functions": fns,
                    "use_cases": [u["use_case_id"] for u in ucs],
                    "features": list(dict.fromkeys(f for u in ucs for f in u.get("rm_features") or [])),
                    "origins": ORIGINS["group"], "heading": f"Service group: {g}"})
    out.append({"id": TASK_STATE, "kind": "state", "origins": ORIGINS["state"], "heading": "State behaviour"})
    gl = _guideline_inputs(ws, inv)
    if gl:
        out += _design_tasks(ws, inv, gl)
    return out


def requirement_schema(tpl: dict) -> dict:
    """contracts/functional-requirement.schema.json without its conditional rules, from the template config."""
    e = tpl["enums"]
    props = {
        "key": {"type": "string", **LENGTHS["key"]}, "title": {"type": "string", **LENGTHS["title"]},
        "statement": {"type": "string", **LENGTHS["statement"]}, "type": {"enum": list(e["type"])},
        "precondition": {"type": "string", **LENGTHS["precondition"]}, "origin_group": {"enum": list(e["origin_group"])},
        "links": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["kind", "input_id", "locator"],
            "properties": {"kind": {"enum": list(e["link_kind"])},
                           "input_id": {"type": "string", "pattern": "^IN-[0-9]{2}$"},
                           "locator": {"type": "string", "minLength": 1}, "rationale": {"type": "string"}}}},
        "use_cases": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "operations": {"type": "array", "items": {"type": "string", "minLength": 1}},  # template v2 (D32)
        "verification_method": {"enum": list(e["verification_method"])}, "test_level": {"enum": list(e["test_level"])}}
    return {"type": "object", "additionalProperties": False, "required": list(tpl["attributes"]),
            "properties": {a: props[a] for a in tpl["attributes"]}}


def answer_schema(tpl: dict) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["requirements", "open_points"],
            "properties": {"requirements": {"type": "array", "minItems": 1, "items": requirement_schema(tpl)},
                           "open_points": {"type": "array", "items": {"type": "string"}}}}


# ---- the level rule ---------------------------------------------------------------------------------------------------
def _section_files(ws: Path) -> dict[str, dict]:
    from .swe1 import _section_files as sf

    return sf(ws) if (Path(ws) / "inputs/index.md").is_file() else {}


def level_terms(ws: Path) -> dict[str, str]:
    """Register-level vocabulary of the order -> where it comes from: register and field names of the RM register
    sections (RM register index) and, from the CMSIS device header, the register-block members and the _Pos/_Msk
    register symbols of the module's registers (the prefixes of its RM register names)."""
    ws = Path(ws)
    terms: dict[str, str] = {}
    for n, s in _section_files(ws).items():
        f = ws / s["file"]
        text = f.read_text(errors="replace") if f.is_file() else ""
        if not re.search(r"address\s+offset", text, re.I):
            continue
        for m in REG_TITLE.finditer(s["title"]):
            terms[m.group(1)] = f"RM register (section {n})"
        for m in FIELD.finditer(text):
            terms.setdefault(m.group(1), f"RM field (section {n})")
    prefixes = {t.split("_", 1)[0] for t in terms if "_" in t}
    for i in _manifest(ws).get("inputs") or []:
        if "cmsis" not in str(i.get("role", "")) or not (ws / i["path"]).is_file():
            continue
        text = (ws / i["path"]).read_text(errors="replace")
        for m in re.finditer(r"#\s*define\s+([A-Z][A-Z0-9_]*)_(?:Pos|Msk)\b", text):
            name = m.group(1)
            if not prefixes or name.split("_", 1)[0] in prefixes:
                terms.setdefault(name, f"CMSIS header symbol ({Path(i['path']).name})")
        for body, tname in re.findall(r"typedef\s+struct\s*\{(.*?)\}\s*([A-Za-z_]\w*)\s*;", text, re.S):
            if prefixes and tname.split("_", 1)[0] not in prefixes:
                continue
            for m in re.finditer(r"\b([A-Z][A-Z0-9_]*)\s*(?:\[[^\]]*\])?\s*;", body):
                if len(m.group(1)) >= 2 and not m.group(1).startswith("RESERVED"):
                    terms.setdefault(m.group(1), f"CMSIS register-block member ({tname})")
    return terms


def level_findings(text: str, terms: dict[str, str], allowed: set[str], patterns: list[str]) -> list[tuple[str, str]]:
    out = []
    for tok in dict.fromkeys(TOKEN.findall(text)):
        if tok in terms and tok not in allowed:
            out.append(("LEVEL_REGISTER_TERM", f"'{tok}' is register-level vocabulary ({terms[tok]}); state the "
                        "behaviour with the delivered public API instead - register detail belongs to SWE.3"))
    for p in patterns:
        for m in dict.fromkeys(re.findall(p, text)):
            out.append(("LEVEL_HEX_VALUE", f"'{m}' is an address or register value; the functional level states no "
                        "hexadecimal value"))
    return out


# ---- deterministic validation -----------------------------------------------------------------------------------------
def context(ws: Path) -> dict:
    """Everything the validators need, computed once per visit or gate run."""
    ws = Path(ws)
    tpl, inv = template(ws), GI.load(ws)
    try:
        pkg = governance_package(ws)
    except ValueError:
        pkg = None
    secs: dict[str, set[str]] = {r["input_id"]: {s["section"] for s in r.get("sections") or []} for r in inv["inputs"]}
    code = {r["name"] for r in inv["inputs"] if r["role"] == GI.UNDER_ANALYSIS}
    code |= {Path(c).name for c in code}
    names = set(json.loads((ws / "configuration/system_names.json").read_text()))
    return {"template": tpl, "schema": requirement_schema(tpl), "inputs": {r["input_id"]: r for r in inv["inputs"]},
            "sections": secs, "code": sorted(code, key=len, reverse=True), "names": names,
            "use_cases": {u["use_case_id"] for u in (pkg or {}).get("use_cases") or []},
            "terms": level_terms(ws), "allowed": {a["function"] for a in inv["api"]},
            # round 4 D41: the HAL driver guideline input of the register (requirement source named *guideline*)
            "guideline": next((r["input_id"] for r in inv["inputs"] if r["role"] != GI.UNDER_ANALYSIS
                               and "guideline" in str(r["name"]).lower()), None),
            "in_scope": {a["function"]: a["component"] for a in inv["api"] if a["scope_class"] == "in"},
            "rules": dict(tpl.get("rules") or {}),
            "patterns": list((tpl.get("level_rule") or {}).get("patterns") or [])}


NO_VALUE = re.compile(r"^(n/?a|none|tbd|-+|not applicable\b.*)$", re.I)
# Round 3 (cloud control run C04, 2026-11-13; template v2 rules references_by_key / no_author_meta_text /
# budget_verified_by_measurement): SWR ids are assigned at assembly and change between baselines, so another
# requirement is cited by its key - "[key]" or "[task/key]" - and the assembly writes the current id in front.
REF = re.compile(r"(?:\bSWR-\d{3,}\s*)?\[((?:[a-z][a-z0-9_]*/)?[a-z][a-z0-9_]*)\]")
BARE_REF = re.compile(r"\bSWR-\d{3,}\b(?!\s*\[)")
META = re.compile(r"\b(?:task owner|regenerat\w*|this answer|(?:consolidated|assembled) work ?products?|new key|"
                  r"(?:IQ|SQ|SWE1)-\d{2}\b|inspectors?\b|inspection findings?|rework\w*|the author)", re.I)
BUDGET = re.compile(r"\b\d[\d,.]*\s*(?:bytes?|KiB|kB|instructions?|cycles?|microseconds?|µs|us|milliseconds?|ms|MIPS)\b")
REFERENCE_RULE = ("References: cite another requirement only by its key in brackets, '[key]' or '[task/key]' (the "
                  "factory writes its current SWR id in front); never a bare SWR id - ids change between baselines.")
META_RULE = ("Requirements and open points describe the module and its inputs, never the authoring process (tasks, keys "
             "to assign, inspections, rework, regenerating work products).")
GRANULARITY_RULE = ("Granularity: one requirement per service behaviour of a delivered function - its normal outcome "
                    "and its error, timeout and busy-state variants together in that one requirement - not one "
                    "requirement per variant.")
GUIDELINE_TRACE_RULE = ("HAL-only behaviour that no hardware input states (callbacks, MSP hooks, handle state, abort and "
                        "status services) is traced to the HAL driver guideline input, not left awaiting traceability.")
BUDGET_RULE = ("A work-order budget (memory, stack, timing) is a mandatory requirement of this release like any other: "
               "state the limit, verify it by measurement (test or analysis naming what is measured), and never "
               "qualify it as optional, non-binding or not an acceptance limit.")


def ref_index(rows: list[dict]) -> dict[str, str]:
    """'key' (when unique in the set) and 'task/key' (task = the part after 'requirements:') -> current SWR id."""
    idx, count = {}, {}
    for row in rows:
        key, task = row["key"], str(row["task"]).split(":", 1)[-1]
        idx[f"{task}/{key}"] = row["swr"]
        count[key] = count.get(key, 0) + 1
        idx.setdefault(key, row["swr"])
    for key, n in count.items():
        if n > 1:
            idx.pop(key, None)
    return idx


def resolve_refs(text: str, idx: dict[str, str]) -> tuple[str, list[str]]:
    """The text with every '[key]' reference of a known key written as '<current SWR id> [key]'; the references
    written with an id whose key is not in the set are returned (unresolved). Other brackets stay as they are."""
    missing = []

    def sub(m):
        swr = idx.get(m.group(1))
        if swr is None:
            if m.group(0).startswith("SWR-"):
                missing.append(m.group(1))
            return m.group(0)
        return f"{swr} [{m.group(1)}]"

    return REF.sub(sub, text), missing


def allocation(r: dict, ctx: dict) -> tuple[str, str]:
    """Template v2 (D32): (allocated interface, allocated operation) derived from the requirement's operations."""
    ops = list(r.get("operations") or [])
    if not ops:
        un = (ctx["template"].get("allocation") or {}).get("unallocated", "not allocated")
        return un, un
    return ", ".join(sorted({ctx["in_scope"].get(o, "?") for o in ops})), ", ".join(ops)


def design_limit(task_id: str, n: int, ctx: dict) -> str | None:
    """Template v2 (D31): the per-part cap of design-constraint requirements (None within the cap or without one)."""
    cap = ctx["rules"].get("design_constraints_per_part")
    if not cap or n <= cap:
        return None
    return (f"DESIGN_CONSTRAINT_LIMIT: {n} design constraints in {task_id}, at most {cap} per guideline part - one "
            "requirement per topic that shapes the module's API or observable behaviour; merge the rules of one topic "
            "and leave general coding, naming and layout rules to the SWE.3 guideline checklist")


def _ears(statement: str, key: str, names: set[str]) -> list[tuple[str, str]]:
    from ..inspection.ears import Requirement, check_statement

    out = []
    for f in check_statement(Requirement(key, statement, 0), names).findings:
        code = f.split(":", 1)[1] if ":" in f else f
        if not code.startswith("EARS_SYSTEM_NAME_HINT"):
            out.append((code.split(":", 1)[0], code.split(":", 1)[1] if ":" in code else
                        "EARS (The/When/While/Where/If..then), exactly one 'shall', subject 'the <system name>' "
                        f"(one of: {', '.join(sorted(names))}), ending with a period"))
    return out


def requirement_findings(r: dict, origins: list[str] | None, ctx: dict) -> list[tuple[str, str]]:
    """(rule, detail) of one requirement object; `origins` = the origin groups its task may write (None: any)."""
    out: list[tuple[str, str]] = []
    if not isinstance(r, dict):
        return [("TEMPLATE_ATTRIBUTE_INVALID", "a requirement is an object")]
    for a in ctx["schema"]["required"]:
        if a not in r:
            out.append(("TEMPLATE_ATTRIBUTE_MISSING", a))
    errs = [e for e in S.validate(r, ctx["schema"]) if not e.endswith(": required")]
    out += [("TEMPLATE_ATTRIBUTE_INVALID", e.removeprefix("$.")) for e in errs]
    if out:
        return out
    links, og = r["links"], r["origin_group"]
    if origins is not None and og not in origins:
        out.append(("ORIGIN_GROUP_NOT_OF_TASK", f"origin_group {og} is not written by this task (allowed: "
                    f"{', '.join(origins)})"))
    if og == "awaiting_traceability" and links:
        out.append(("LINKS_ON_AWAITING", "a requirement awaiting traceability has no links (or link it and choose its "
                    "origin group)"))
    if og != "awaiting_traceability" and not links:
        out.append(("LINKS_MISSING", "give a trace link to an input statement, a derive link with its rationale, or "
                    "use origin_group awaiting_traceability"))
    for ln in links:
        row = ctx["inputs"].get(ln["input_id"])
        if row is None:
            out.append(("LINK_INPUT_UNKNOWN", f"{ln['input_id']} is not in the input register"))
            continue
        if row["role"] != GI.SOURCE:
            out.append(("LINK_TO_DELIVERED_CODE", f"{ln['input_id']} ({row['name']}) is the implementation under "
                        "analysis, never a requirement source"))
            continue
        known = ctx["sections"].get(ln["input_id"]) or set()
        if known and not (set(SECTION_ID.findall(ln["locator"])) & known):
            out.append(("LINK_LOCATOR_UNKNOWN", f"locator '{ln['locator']}' names no section of {ln['input_id']} "
                        f"({row['name']}); use a section id of the input section index"))
        if ln["kind"] == "derive" and not str(ln.get("rationale") or "").strip():
            out.append(("DERIVE_WITHOUT_RATIONALE", f"the derive link to {ln['input_id']} states its rationale"))
    texts = [r["statement"], r["precondition"], *[f"{ln['locator']} {ln.get('rationale') or ''}" for ln in links]]
    for c in ctx["code"]:
        if any(c.lower() in t.lower() for t in texts):
            out.append(("CODE_AS_SOURCE", f"'{c}' is delivered code (implementation under analysis); it is never a "
                        "source or a reference of a requirement"))
            break
    if og == "use_case" and not r["use_cases"]:
        out.append(("USE_CASE_MISSING", "a use-case requirement names the use cases it serves"))
    out += [("USE_CASE_UNKNOWN", f"{u} is no use case of the governance package") for u in r["use_cases"]
            if u not in ctx["use_cases"]]
    out += level_findings(r["statement"] + "\n" + r["precondition"], ctx["terms"], ctx["allowed"], ctx["patterns"])
    out += _ears(r["statement"], r["key"], ctx["names"])
    if r["type"] == "design_constraint" and r["verification_method"] != "inspection":
        out.append(("DESIGN_CONSTRAINT_NOT_BY_INSPECTION", "a design constraint is verified by inspection"))
    if og == "hal_design_constraint" and r["type"] != "design_constraint":
        out.append(("HAL_DESIGN_CONSTRAINT_TYPE", "a HAL design-constraint requirement has type design_constraint"))
    rules = ctx.get("rules") or {}
    dc = og == "hal_design_constraint" or r["type"] == "design_constraint"
    if rules.get("functional_precondition_required") and r["type"] == "functional" and \
            NO_VALUE.match(r["precondition"].strip()):
        out.append(("PRECONDITION_MISSING", "a functional requirement states its precondition: the state the module or "
                    "its handle must be in for the behaviour ('none' only for a design constraint)"))
    if rules.get("design_constraint_no_use_cases") and dc and r["use_cases"]:
        out.append(("DESIGN_CONSTRAINT_USE_CASES", "a design constraint serves no single use case: use_cases is []"))
    if (rules.get("hal_behaviour_traces_to_guideline") and og == "awaiting_traceability" and ctx.get("guideline")
            and r.get("operations") and all(str(ctx["in_scope"].get(o, "")).upper().startswith("HAL")
                                            for o in r["operations"])):
        out.append(("HAL_GUIDELINE_TRACE", f"HAL-only behaviour (callbacks, MSP hooks, handle state, abort and "
                    f"status services of the HAL) is traced to the HAL driver guideline {ctx['guideline']}: a trace or "
                    "derive link to it and origin_group use_case (or out_of_context), not awaiting_traceability"))
    if "operations" in r:
        ops = r["operations"]
        out += [("OPERATION_UNKNOWN", f"{o} is no in-scope delivered function of the module") for o in ops
                if o not in ctx["in_scope"]]
        if rules.get("design_constraint_no_operations") and dc and ops:
            # CAPA (L51 g_ll_crc): the finding named one way out only; the author kept its operations three times and
            # the stuck repair failed the order. A statement of what named functions do is functional.
            out.append(("DESIGN_CONSTRAINT_OPERATIONS", "a design constraint is not allocated: operations is []; a "
                        "statement of what the named delivered function(s) do is type functional and keeps them in "
                        "operations"))
        if rules.get("functional_operations_required") and r["type"] == "functional" and not ops:
            out.append(("OPERATION_MISSING", "a functional requirement names the delivered function(s) it is about in "
                        "operations"))
    out += text_findings([r["title"], r["statement"], r["precondition"],
                          *[str(ln.get("rationale") or "") for ln in links]], rules)
    if rules.get("budget_verified_by_measurement") and r["type"] == "functional" and BUDGET.search(r["statement"]) \
            and r["verification_method"] == "inspection":
        out.append(("BUDGET_NOT_MEASURED", "a requirement that states a budget value is verified by measurement (test "
                    "or analysis naming what is measured), not by inspection"))
    return out


def text_findings(texts: list[str], rules: dict) -> list[tuple[str, str]]:
    """Round 3: bare SWR id references and authoring-process text (requirements and open points)."""
    out = []
    if rules.get("references_by_key"):
        bare = next((m.group(0) for t in texts if (m := BARE_REF.search(t))), None)
        if bare:
            out.append(("REFERENCE_BY_ID", f"'{bare}' cites a requirement by id; cite it by its key in brackets, "
                        "'[key]' or '[task/key]' - SWR ids are assigned when the set is assembled"))
    if rules.get("no_author_meta_text"):
        meta = next((m.group(0) for t in texts if (m := META.search(t))), None)
        if meta:
            out.append(("AUTHOR_META_TEXT", f"'{meta}': describe the module and its inputs, never the authoring "
                        "process (tasks, keys, inspections, rework, regeneration)"))
    return out


def validate_task(ws: Path, doc: dict, task: dict, ctx: dict | None = None) -> list[str]:
    ctx = ctx or context(ws)
    out, keys = [], set()
    for r in (doc or {}).get("requirements") or []:
        k = r.get("key") if isinstance(r, dict) else None
        if k in keys:
            out.append(f"[{k}] DUPLICATE_KEY: keys are unique within the task")
        keys.add(k)
        out += [f"[{k}] {rule}: {detail}" for rule, detail in requirement_findings(r, task.get("origins"), ctx)]
    for n, op in enumerate((doc or {}).get("open_points") or [], 1):
        out += [f"[open_point {n}] {rule}: {detail}" for rule, detail in
                text_findings([str(op)], ctx.get("rules") or {})]
    if task.get("kind") == "design":
        lim = design_limit(task["id"], len((doc or {}).get("requirements") or []), ctx)
        if lim:
            out.append(f"[{task['id']}] {lim}")
    else:
        gran = granularity(task["id"], (doc or {}).get("requirements") or [], ctx)
        if gran:
            out.append(f"[{task['id']}] {gran}")
    return out


def granularity(task_id: str, reqs: list, ctx: dict) -> str | None:
    """Round 4: a delivered function that is the ONLY operation of more than N functional requirements of a task is a
    service behaviour split into variants (UART L50B: HAL_UART_Receive alone in 5, HAL_UART_Transmit in 4)."""
    cap = ctx["rules"].get("functional_requirements_per_operation")
    if not cap:
        return None
    alone: dict[str, list[str]] = {}
    for r in reqs:
        if isinstance(r, dict) and r.get("type") == "functional" and len(r.get("operations") or []) == 1:
            alone.setdefault(r["operations"][0], []).append(str(r.get("key")))
    over = {o: ks for o, ks in alone.items() if len(ks) > cap}
    if not over:
        return None
    return ("GRANULARITY: " + "; ".join(f"{o} is the only operation of {len(ks)} requirements ({', '.join(ks)})"
                                        for o, ks in sorted(over.items()))
            + f" - at most {cap} per function: one requirement per service behaviour, its error, timeout and state "
            "variants merged into it (the statement names the outcomes), keeping the keys of the merged requirements' "
            "first one")


def _norm(s: str) -> str:
    return re.sub(r"\W+", " ", s.lower()).strip()


def consistency(plan_: list[dict], recs: dict[str, dict]) -> list[tuple[str, str]]:
    """Cross-task check: a statement written twice is removed from the later task."""
    out, seen = [], {}
    for t in plan_:
        rec = recs.get(t["id"])
        for r in ((rec or {}).get("doc") or {}).get("requirements") or []:
            n = _norm(r["statement"])
            if n in seen:
                out.append((t["id"], f"[{r['key']}] DUPLICATE_STATEMENT: duplicates [{seen[n][1]}] of {seen[n][0]} - "
                                     "remove it here"))
            else:
                seen[n] = (t["id"], r["key"])
    return out


# ---- packets ---------------------------------------------------------------------------------------------------------
LEVEL_RULE = (
    "Level rule (functional level): a statement names the delivered public API (functions, states, option constants) "
    "and observable behaviour only - never a register, bit field, register address or reset value, and no "
    "hexadecimal number; register-level detail and concrete negative cases belong to SWE.3. Invalid use is specified "
    "generically: parameter validity, operation permitted in the current state, error reporting.")
LINK_RULE = (
    "Links: a trace link (kind trace) points at the input statement it restates: input_id from the INPUT REGISTER "
    "(requirement_source inputs only) and locator = the section id of the input section index (e.g. '12.3.1') or, for "
    "an input without sections, its heading number. A derive link (kind derive) also states its rationale. A "
    "requirement no input supports is origin_group awaiting_traceability with no links. The delivered code (inputs "
    "marked implementation_under_analysis and the delivered files) is never a link, a source or a reference.")


def _rules(ws: Path, task: dict, ctx: dict) -> str:
    if "operations" in ctx["template"]["attributes"]:
        return _rules_v2(task, ctx)
    names = ", ".join(f"'the {n}'" for n in sorted(ctx["names"]))
    return (f" Each requirement follows template {ctx['template']['template_id']}: key (short snake_case, unique in "
            "this task), title (3-80 characters), statement in EARS (The/When/While/Where/If..then) with exactly one "
            f"'shall', the subject being one of {names} (the component that offers the service), ending with a "
            "period; type (functional, design_constraint or architectural); precondition (the condition under which "
            "it applies, or 'none'); origin_group, one of: " + ", ".join(task["origins"]) + "; links; use_cases (the "
            "use-case ids it serves, from the TASK SCOPE); verification_method (test, analysis, inspection, "
            "demonstration; a design_constraint is verified by inspection); test_level (unit, component, "
            "integration, qualification, not_testable). " + LEVEL_RULE + " " + LINK_RULE + " Status, ASIL, CAL and "
            "the SWE.2 allocation are set by the factory, never written here. open_points lists ambiguities or gaps "
            "of the inputs (or nothing).")


def _rules_v2(task: dict, ctx: dict) -> str:
    """Template v2 rules text (D31-D33); the v1 text above stays unchanged for v1 orders."""
    names = ", ".join(f"'the {n}'" for n in sorted(ctx["names"]))
    design = task.get("kind") == "design"
    return (f" Each requirement follows template {ctx['template']['template_id']}: key (short snake_case, unique in "
            "this task), title (3-80 characters), statement in EARS (The/When/While/Where/If..then) with exactly one "
            f"'shall', the subject being one of {names} (the component that offers the service), ending with a "
            "period; type (functional, design_constraint or architectural); precondition (the state the module or its "
            "handle must be in for the behaviour, e.g. 'the handle is initialised and no transfer is ongoing'; 'none' "
            "only for a design constraint); origin_group, one of: " + ", ".join(task["origins"]) + "; links; "
            + ("use_cases [] and operations [] (a design constraint serves no single use case and is not allocated); "
               if design else
               "use_cases (the use-case ids it serves, from the TASK SCOPE, never invented); operations (the delivered "
               "public functions of the TASK SCOPE the requirement is about - at least one for a functional "
               "requirement; the factory allocates the requirement to them); ")
            + "verification_method (test, analysis, inspection, demonstration; a design_constraint is verified by "
            "inspection); test_level (unit, component, integration, qualification, not_testable). " + LEVEL_RULE + " "
            + LINK_RULE + " Status, ASIL and CAL are set by the factory, never written here. open_points lists "
            "ambiguities or gaps of the inputs (or nothing)." + _round3_rules(ctx))


def _round3_rules(ctx: dict) -> str:
    """Round 3 guidance, only where the template switches the rule on (orders without the switch keep their text)."""
    rules = ctx.get("rules") or {}
    return "".join(" " + t for k, t in (("references_by_key", REFERENCE_RULE), ("no_author_meta_text", META_RULE),
                                         ("budget_verified_by_measurement", BUDGET_RULE),
                                         ("functional_requirements_per_operation", GRANULARITY_RULE),
                                         ("hal_behaviour_traces_to_guideline", GUIDELINE_TRACE_RULE)) if rules.get(k))


def input_register_text(inv: dict) -> str:
    return "\n".join(f"{r['input_id']} | {r['name']} | {r.get('revision', '-')} | {r['role']}"
                     + (" | sections: see inputs/index.md" if r.get("sections") else "") for r in inv["inputs"])


def _artifact(path: str, value) -> dict:
    text = value if isinstance(value, str) else json.dumps(value, indent=1, sort_keys=True)
    return {"path": path, "text": text, "sha256": sha256_bytes(text.encode())}


def task_sources(ws: Path, task: dict, inv: dict | None = None) -> list[dict]:
    """The bounded input excerpts of a task (author and phase-1 inspector)."""
    ws = Path(ws)
    inv = inv or GI.load(ws)
    out = [S.source(ws, "inputs/index.md")] if (ws / "inputs/index.md").is_file() else []
    if task["kind"] == "group":
        secs = _section_files(ws)
        out += [S.source(ws, secs[f]["file"]) for f in task["features"] if f in secs and (ws / secs[f]["file"]).is_file()]
    elif task["kind"] == "design" and task.get("part"):  # D24: only this part of the guideline
        pt = task["part"]
        lines = (ws / pt["path"]).read_text(errors="replace").splitlines(keepends=True)
        text = "".join(lines[pt["lines"][0] - 1:pt["lines"][1]])
        out.append({"path": f"{pt['path']}#lines-{pt['lines'][0]}-{pt['lines'][1]}",
                    "sha256": sha256_bytes(text.encode()), "text": text})
    elif task["kind"] == "design":
        names = {r["input_id"]: r["name"] for r in inv["inputs"]}
        for i in _manifest(ws).get("inputs") or []:
            if Path(i["path"]).name in {names[g] for g in task["guideline"]}:
                out.append(S.source(ws, i["path"]))
    return out


def task_scope(ws: Path, task: dict, inv: dict, pkg: dict) -> dict:
    comp = {a["function"]: a["component"] for a in inv["api"]}
    ucs = pkg["use_cases"]
    if task["kind"] == "group":
        ucs = [u for u in ucs if u["use_case_id"] in task["use_cases"]]
        fns = set(task["functions"])
        return {"module": inv["module"], "service_group": task["group"],
                "functions": [{"function": f, "component": comp[f]} for f in task["functions"]],
                "use_cases": ucs, "actors": pkg["actors"], "assumptions": pkg["assumptions"],
                "open_points": [o for o in pkg["open_points"] if set(o.get("concerns") or []) & fns]}
    in_scope = [a for a in inv["api"] if a["scope_class"] == "in"]
    base = {"module": inv["module"], "components": sorted({a["component"] for a in inv["api"]})}
    if task["kind"] == "state":
        return {**base, "functions": [{"function": a["function"], "component": a["component"],
                                       "service_group": a["scope_group"]} for a in in_scope],
                "use_cases": [{k: u[k] for k in ("use_case_id", "title", "functions")} for u in ucs],
                "assumptions": pkg["assumptions"], "open_points": pkg["open_points"]}
    return {**base, "guideline_inputs": task["guideline"]}


LEAD = {
    "group": ("Write the functional-level software requirements of service group '{group}' of module {module}: what "
              "each delivered function of the TASK SCOPE does for the use cases that exercise it (inputs, outputs, "
              "results, callbacks), at the level of the public API. Every function of the group is covered by a "
              "requirement or named in open_points. Use origin_group use_case for behaviour a use case needs (list its "
              "use cases), out_of_context for behaviour of the peripheral the inputs state without a use case."),
    "state": ("Write the state-behaviour requirements of module {module}: the driver states and their transitions as "
              "the public API exposes them, which operations each state permits, and the generic invalid-use and "
              "error-reporting behaviour (parameter validity, operation not permitted in the current state, error "
              "reporting) - not the per-function behaviour, which the service-group tasks write."),
    "design": ("Write the design-constraint requirements that the HAL driver guideline (the provided guideline "
               "input) imposes on module {module}: one requirement per applicable rule, type design_constraint, "
               "origin_group hal_design_constraint, verification_method inspection, linked to the guideline rule."),
}


# Template v2 (D31): design constraints per topic, bounded per guideline part. Both pilot models wrote ~40% of their
# requirements as one design constraint per guideline rule (benchmark: 5 of 56); general coding rules are already checked
# at SWE.3 by the guideline checklist.
LEAD_DESIGN_V2 = (
    "Write the design-constraint requirements that the HAL driver guideline (the provided guideline input) imposes on "
    "module {module}, one requirement per topic and at most {cap} for this task: only rules that shape the module's "
    "public API or its observable behaviour (for example the service signature and handle convention, the status and "
    "error reporting convention, callback registration, blocking and timeout policy, reentrancy). Merge the rules of "
    "one topic into one requirement. General coding, naming, formatting and file-layout rules are not SWE.1 "
    "requirements: the SWE.3 guideline checklist checks them. Each requirement: type design_constraint, origin_group "
    "hal_design_constraint, verification_method inspection, linked to the guideline rule(s) it states.")


def task_packet(ws: Path, task: dict, model: str, findings: list[str] | None = None, previous: dict | None = None,
                ctx: dict | None = None) -> dict:
    ws = Path(ws)
    ctx = ctx or context(ws)
    inv, pkg = GI.load(ws), governance_package(ws)
    cap = ctx["rules"].get("design_constraints_per_part")
    lead = LEAD_DESIGN_V2.format(module=inv["module"], cap=cap) if task["kind"] == "design" and cap else \
        LEAD[task["kind"]].format(group=task.get("group", ""), module=inv["module"])
    instr = lead + _rules(ws, task, ctx)
    if task.get("part"):  # D24
        pt = task["part"]
        instr += (f" This task covers part {pt['n']} of {pt['of']} of the guideline (its lines {pt['lines'][0]}-"
                  f"{pt['lines'][1]}, the guideline source below); the other parts are separate tasks, so write the "
                  "design constraints that this part states and nothing from the other parts; when this part states "
                  "no rule that applies to the module, write the one constraint it supports best or name the gap in "
                  "open_points.")
    art = [_artifact("lrtx:task_scope", task_scope(ws, task, inv, pkg)),
           _artifact("lrtx:input_register", input_register_text(inv))]
    crit = ["every statement is EARS with one 'shall' and a system-name subject", "no register-level vocabulary",
            "every link names a requirement_source input of the register and a locator; derive links state a rationale",
            "origin groups of this task only; awaiting_traceability has no links"]
    if task["kind"] == "group":
        crit.append("every function of the service group is covered or named in open_points")
    return S.packet(phase=PHASE, task=task["id"], role="swe1-author", instructions=instr,
                    sources=task_sources(ws, task, inv) + [GP.skill_reference()], artifacts=art, criteria=crit,
                    output_schema=answer_schema(ctx["template"]), model=model, findings=findings, previous=previous)


# ---- assembly --------------------------------------------------------------------------------------------------------
def _source_line(r: dict, inputs: dict) -> str:
    if not r["links"]:
        return "awaiting traceability (no input states it yet)"
    return "; ".join(f"{ln['input_id']} {inputs[ln['input_id']]['name']} {ln['locator']}" if ln["input_id"] in inputs
                     else f"{ln['input_id']} {ln['locator']}" for ln in r["links"])


def _links_line(r: dict) -> str:
    if not r["links"]:
        return "none"
    return "; ".join(f"{ln['kind']} {ln['input_id']} {ln['locator']}" + (
        f" (rationale: {ln['rationale'].strip()})" if ln["kind"] == "derive" and ln.get("rationale") else "")
        for ln in r["links"])


def _verification(r: dict) -> str:
    m, lvl = r["verification_method"], r["test_level"]
    crit = {"test": "the test observes the behaviour the statement specifies under its precondition",
            "demonstration": "the demonstration shows the behaviour the statement specifies under its precondition",
            "inspection": "an inspection of the work products confirms the statement",
            "analysis": "the analysis shows that the statement holds under its precondition"}[m]
    return f"{m} ({lvl}); passes when {crit}"


def _test_row(swr: str, r: dict, module: str) -> str:
    if r["verification_method"] not in ("test", "demonstration"):
        return f"{swr},,{r['verification_method']}"
    m = module.lower()
    f = {"qualification": f"software/tests/software/test_{m}_requirements.robot",
         "integration": f"software/tests/integration/test_{m}.c"}.get(r["test_level"], f"software/tests/unit/test_{m}.c")
    return f"{swr},{swr},{f}"


def assemble(ws: Path, plan_: list[dict], recs: dict[str, dict]) -> dict:
    """Writes the SWE.1 work products from VALID task records; returns the assembly map."""
    from .swe1 import safety_text

    ws = Path(ws)
    m, inv, pkg, tpl = _manifest(ws), GI.load(ws), governance_package(ws), template(ws)
    fixed = dict(tpl["fixed"])
    inputs = {r["input_id"]: r for r in inv["inputs"]}
    rows = [{"task": t["id"], "heading": t["heading"], "obj": r} for t in plan_ for r in recs[t["id"]]["doc"]
            ["requirements"]]
    for n, row in enumerate(rows, 1):
        row["swr"] = f"SWR-{n:03d}"
    rules = dict(tpl.get("rules") or {})
    unresolved: dict[str, list[str]] = {}
    if rules.get("references_by_key"):  # round 3: the current id is written in front of every '[key]' reference
        idx = ref_index([{"key": row["obj"]["key"], "task": row["task"], "swr": row["swr"]} for row in rows])
        for row in rows:
            r = json.loads(json.dumps(row["obj"]))  # the task record itself stays as the author wrote it
            miss = []
            for f in ("statement", "precondition"):
                r[f], m_ = resolve_refs(r[f], idx)
                miss += m_
            for ln in r["links"]:
                if ln.get("rationale"):
                    ln["rationale"], m_ = resolve_refs(ln["rationale"], idx)
                    miss += m_
            row["obj"] = r
            if miss:
                unresolved[row["swr"]] = sorted(set(miss))
    waiting = sum(r["obj"]["origin_group"] == "awaiting_traceability" for r in rows)
    out_fns = [a["function"] for a in inv["api"] if a["scope_class"] == "out"]
    budgets = m.get("budgets") if rules.get("budget_verified_by_measurement") else None
    md = ["# Software requirements", "",
          f"Functional-level software requirements of module {inv['module']} (template {tpl['template_id']}). Scope: "
          + " ".join(m["scope"]), "",
          f"Governance package: {GP.OUT_JSON} (version `{pkg['package_version']}`); input register and use cases "
          "there.", "",
          f"Release scope: work order {m['work_order']} (a single release; every requirement below belongs to it). "
          "Priority: mandatory - every requirement is required for this release; none is optional or deferred."
          + (" Work-order budgets (" + ", ".join(sorted(k for k in budgets if k != "status")) + ") are development "
             "targets set by the work-order owner: the requirements that state them are mandatory like every other "
             "and verified by measurement; a measured exceedance is a failed verification, reported for the owner's "
             "disposition." if budgets else ""), "",
          "Organization: one section per service group of the module's scope rule, then state behaviour, then the "
          "design constraints of the HAL driver guideline. SWR identifiers are stable within this baseline.", "",
          f"Awaiting traceability: {waiting} of {len(rows)} requirements ({100.0 * waiting / max(len(rows), 1):.1f}%).",
          ""]
    v2 = "operations" in tpl["attributes"]
    actx = {"template": tpl, "in_scope": {a["function"]: a["component"] for a in inv["api"] if a["scope_class"] == "in"}}
    for row in rows:  # D32 (template v2): the allocation is derived from the operations; v1 keeps the fixed values
        row["alloc"] = allocation(row["obj"], actx) if v2 else (fixed["allocated_interface"],
                                                                fixed["allocated_operation"])
    heading = None
    for row in rows:
        r, swr = row["obj"], row["swr"]
        if row["heading"] != heading:
            heading = row["heading"]
            md += ([""] if md[-1] != "" else []) + [f"## {heading}", ""]
        md += [f"- **{swr}** {r['statement'].strip()}", f"  - Source: {_source_line(r, inputs)}",
               f"  - Verification: {_verification(r)}", f"  - Title: {r['title']}", f"  - Type: {r['type']}",
               f"  - Status: {fixed['status']}", f"  - ASIL: {fixed['asil']}", f"  - CAL: {fixed['cal']}",
               f"  - Precondition: {r['precondition']}", f"  - Origin group: {r['origin_group']}",
               f"  - Links: {_links_line(r)}", f"  - Use cases: {', '.join(r['use_cases']) or 'none'}",
               *([f"  - Operations: {', '.join(r['operations']) or 'none'}"] if v2 else []),
               f"  - Verification method: {r['verification_method']}", f"  - Test level: {r['test_level']}",
               f"  - Allocated interface: {row['alloc'][0]}",
               f"  - Allocated operation: {row['alloc'][1]}"]
    opens, open_points = [], {}
    for t in plan_:
        rec = recs[t["id"]]
        for raw in rec["doc"]["open_points"]:
            text = raw.strip()
            if not text:
                continue
            ident = "OP-" + sha256_bytes((rec["task"] + "\0" + text).encode())[:16]
            if ident in open_points:
                continue
            open_points[ident] = {"task": rec["task"], "text": text, "text_sha256": sha256_bytes(text.encode()),
                                  "packet_input_hash": rec.get("base_hash"), "record_sha256": sha256_bytes(
                                      canonical_json(rec))}
            shown = resolve_refs(text, idx)[0] if rules.get("references_by_key") else text  # id stays stable (raw)
            opens.append(f"**{ident}** ({t['heading']}): {shown}")
    opens += [f"**{o['open_point_id']}** (governance package): {o['text']}" for o in pkg["open_points"]]
    md += ["", "## Open points", ""] + ([f"- {o}" for o in opens] or ["- none"])
    md += ["", "## Delivered, out of scope", "", ", ".join(out_fns) or "none", "", "## Not delivered", ""]
    md += [f"- {n.get('capability')}: {n.get('note', '')}" for n in inv["not_delivered"]] or ["- none"]
    md.append("")
    attrs = {"schema": ATTR_SCHEMA, "template": tpl["template_id"], "work_order": m["work_order"],
             "package_version": pkg["package_version"],
             "requirements": [{"id": row["swr"], "task": row["task"], **row["obj"], **fixed,
                               **({"allocated_interface": row["alloc"][0], "allocated_operation": row["alloc"][1]}
                                  if v2 else {})} for row in rows]}
    csv = ["requirement_id,test_id,test_file"] + [_test_row(row["swr"], row["obj"], inv["module"]) for row in rows]
    files = {REQS: "\n".join(md), ATTRS: json.dumps(attrs, indent=1) + "\n", CSV: "\n".join(csv) + "\n"}
    st = safety_text(ws)
    if st is not None:
        files[SAFETY] = st
    V.write_scoped(ws, files, "swe1_author")
    amap = {"schema": "forge-c/lrtx-swe1-assembly/1", "at": utc_now(), "level": L.FUNCTIONAL,
            "template": tpl["template_id"], "package_version": pkg["package_version"],
            "swr": {row["swr"]: {"task": row["task"], "key": row["obj"]["key"]} for row in rows}, "case": {},
            "files": sorted(files), "open_points": open_points, "unresolved_references": unresolved}
    S.record(ws, "SWE.1/assembly.json", amap)
    return amap


def self_check(ws: Path) -> list[str]:
    """The deterministic functional checks the author gate applies (T021), run before replying."""
    from ..assurance import swe1_functional_checks as FC

    return FC.findings(ws)


# ---- the author visit -------------------------------------------------------------------------------------------------
def reply(ws: Path, status: str, issues: list[str], budget: dict | None = None,
          artifacts: list[str] | None = None) -> dict:
    return V.reply(ws, PHASE, status, issues, budget, artifacts)


def _run(ws, task, model, budget, ctx, findings=None) -> dict:
    from . import swe1_carry as C

    def build(fi, pr):
        return task_packet(ws, task, model, fi, pr, ctx)

    if C.wanted(ws):  # D36 owner rule: validated requirements of a predecessor run are kept
        if findings is None:
            C.seed_task(ws, task, build(None, None)["input_hash"], ctx)
        else:
            C.release(ws, task["id"], findings)
    rec = V.run_task(ws, PHASE, task["id"], build, lambda d: validate_task(ws, d, task, ctx), budget, findings)
    return C.merge_kept(ws, task, rec, ctx) if C.wanted(ws) else rec


def visit(ws: Path, model: str, max_calls: int | None = None, resume: bool = False,
          time_budget_s: float | None = None) -> dict:
    from ..registry.agents import load_agents
    from .swe1 import safety_text

    ws = Path(ws)
    if L.of_workspace(ws) != L.FUNCTIONAL:
        return reply(ws, "FAILED", ["SWE1_FUNCTIONAL_NOT_A_FUNCTIONAL_ORDER"])
    try:
        plan_ = plan(ws)
    except ValueError as exc:
        return reply(ws, "FAILED", [str(exc)])
    if safety_text(ws) is None:
        return reply(ws, "FAILED", ["SWE1_FUNCTIONAL_SAFETY_ALLOCATION_NOT_SUPPORTED (the functional template fixes "
                                    "ASIL QM; an allocated software safety requirement needs the upstream SSR task)"])
    role = {a.id: a for a in load_agents()[0]}["swe1-author"]
    since = V.last_finished(ws, PHASE)
    amap_p = ws / ".forge-run/lrtx/SWE.1/assembly.json"
    amap = json.loads(amap_p.read_text()) if amap_p.is_file() else None
    budget, findings = V.open_visit(ws, PHASE, resume, lambda: V.rework_findings(ws, PHASE, since) if since else [],
                                    V.author_call_limit(ws, PHASE, role.max_turns, max_calls), time_budget_s)
    routed = {}
    if findings:  # findings name their SWR ids (assembly map) or task ids; the rest go to the state-behaviour task
        routed, report = V.attribute_findings(findings, amap, TASK_STATE)
        S.record(ws, "SWE.1/rework-routing.json", {"schema": "forge-c/lrtx-rework-routing/1", "at": utc_now(),
                                                   "assembly_at": (amap or {}).get("at"), "findings": report,
                                                   "tasks": sorted(routed),
                                                   "unattributed": sum(r["unattributed"] for r in report)})
    try:
        return _visit(ws, model, budget, routed, plan_)
    except V.Continue as c:
        return reply(ws, "CONTINUE", [f"time box used; the next node execution resumes at {c}"], budget)


def _visit(ws: Path, model: str, budget: dict, routed: dict[str, list[str]], plan_: list[dict]) -> dict:
    ctx = context(ws)
    by = {t["id"]: t for t in plan_}
    recs = {t["id"]: _run(ws, t, model, budget, ctx, routed.get(t["id"])) for t in plan_}
    issues = [f"{tid}: {e}" for tid, rec in recs.items() if rec["status"] != "VALID" for e in rec["errors"][:5]]
    if issues:  # missing content stays missing: nothing partial is assembled or frozen
        return reply(ws, "FAILED", issues, budget)
    found = consistency(plan_, recs)
    if found and budget["calls"] < budget["max_calls"]:
        per: dict[str, list[str]] = {}
        for tid, f in found:
            per.setdefault(tid, []).append(f)
        for tid, fs in per.items():
            recs[tid] = _run(ws, by[tid], model, budget, ctx, fs)
        bad = [f"{tid}: {e}" for tid, rec in recs.items() if rec["status"] != "VALID" for e in rec["errors"][:5]]
        if bad:
            return reply(ws, "FAILED", [f"{t}: {f}" for t, f in found] + bad, budget)
        found = consistency(plan_, recs)
    if found:
        return reply(ws, "FAILED", [f"{t}: {f}" for t, f in found], budget)
    amap = assemble(ws, plan_, recs)
    checks = self_check(ws)
    if checks and budget["calls"] < budget["max_calls"]:  # one localized repair round on the gate's own findings
        for tid, fs in V.route_findings(checks, amap, TASK_STATE).items():
            if tid in by:
                recs[tid] = _run(ws, by[tid], model, budget, ctx, fs)
        bad = [f"{tid}: {e}" for tid, rec in recs.items() if rec["status"] != "VALID" for e in rec["errors"][:5]]
        if bad:
            return reply(ws, "FAILED", bad, budget)
        amap = assemble(ws, plan_, recs)
        checks = self_check(ws)
    if checks:
        return reply(ws, "FAILED", checks[:20], budget)
    return reply(ws, "PASS", [], budget, artifacts=amap["files"])


# ---- feature 018 phase 1: one requirement replaced on its own --------------------------------------------------------
def checkpoint_set(ws: Path) -> tuple[list[dict], dict[str, dict]]:
    plan_ = plan(ws)
    recs = {}
    for t in plan_:
        p = V._ckpt(ws, PHASE, t["id"])
        rec = json.loads(p.read_text()) if p.is_file() else None
        if rec is None or rec.get("status") != "VALID" or rec.get("doc") is None:
            raise ValueError("PHASE1_SET_NOT_ASSEMBLED")
        recs[t["id"]] = rec
    return plan_, recs


def requirement_hashes(recs: dict[str, dict]) -> dict[tuple[str, str], str]:
    return {(tid, r["key"]): sha256_bytes(canonical_json(r)) for tid, rec in recs.items()
            for r in rec["doc"]["requirements"]}


def splice(ws: Path, task: str, key: str, new: dict) -> tuple[list[str], tuple | None]:
    """The findings of the set with requirement `key` of `task` replaced by `new` (nothing written): the task's
    functional validators, the cross-task consistency and the key identity. Returns (errors, (plan, records))."""
    ws = Path(ws)
    if not isinstance(new, dict) or new.get("key") != key:
        return [f"[{(new or {}).get('key') if isinstance(new, dict) else None}] the requirement keeps its key "
                f"'{key}'"], None
    plan_, recs = checkpoint_set(ws)
    t = next((x for x in plan_ if x["id"] == task), None)
    if t is None:
        return [f"PHASE1_TASK_NOT_AUTHORED:{task}"], None
    reqs = recs[task]["doc"]["requirements"]
    if sum(r["key"] == key for r in reqs) != 1:
        raise ValueError(f"PHASE1_KEY_NOT_UNIQUE:{task}:{key}")
    recs = {**recs, task: {**recs[task], "doc": {**recs[task]["doc"],
                                                 "requirements": [new if r["key"] == key else r for r in reqs]}}}
    errs = validate_task(ws, recs[task]["doc"], t) + [f"{x}: {f}" for x, f in consistency(plan_, recs)]
    return errs, (plan_, recs)


def replace_requirement(ws: Path, task: str, key: str, new: dict) -> dict:
    """Feature 018 phase 1 for a functional order: write `new` in place of requirement `key` of `task` and re-assemble
    from the checkpoints; every other requirement stays byte-identical and the gate checks must not get worse."""
    ws = Path(ws)
    errs, state = splice(ws, task, key, new)
    if errs:
        raise ValueError("PHASE1_SPLICE_INVALID:" + errs[0][:300])
    from . import swe1_carry as C

    C.release(ws, task, [f"[{key}] reworked by the per-requirement inspection"])  # D36: an inspection finding wins
    plan_, recs = state
    _p, recs0 = checkpoint_set(ws)
    before = requirement_hashes(recs0)
    checks_before = set(self_check(ws))
    ck = V._ckpt(ws, PHASE, task)
    old_raw = ck.read_text()
    old_obj = next(r for r in json.loads(old_raw)["doc"]["requirements"] if r["key"] == key)
    rec = {**recs[task], "phase1_rework": [*(recs[task].get("phase1_rework") or []),
                                          {"key": key, "at": utc_now(), "before": sha256_bytes(canonical_json(old_obj)),
                                           "after": sha256_bytes(canonical_json(new))}]}
    ck.write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    recs = {**recs, task: rec}
    amap = assemble(ws, plan_, recs)
    after = requirement_hashes(recs)
    others = [k for k in before if k != (task, key) and before[k] != after.get(k)]
    worse = sorted(set(self_check(ws)) - checks_before)
    if others or set(after) != set(before) or worse:
        ck.write_text(old_raw)
        assemble(ws, plan_, {**recs, task: json.loads(old_raw)})
        raise ValueError("PHASE1_REFUSED_OTHER_CHANGED" if others or set(after) != set(before)
                         else "PHASE1_SELF_CHECK_WORSE:" + worse[0][:200])
    return amap


# ---- feature 018 packets of a functional order (swe1_quality is level-aware, T023) ---------------------------------
SEVERITY = (
    "Report a finding only for a real defect of this requirement: quality_id, severity (BLOCKING: unsupported or "
    "invented behaviour, contradiction, unverifiable mandatory behaviour, missing critical source; CORRECTABLE: "
    "resolvable from the provided inputs, e.g. imprecision, combined obligations, ambiguous term; EDITORIAL: no "
    "technical change; N/A: the property does not apply, give the reason), evidence quoting the requirement or the "
    "source, required_action, and input_uncertainty true when the defect is a missing or contradictory input rather "
    "than the author's. A requirement without defects has an empty findings list.")


def contexts(ws: Path) -> dict[str, list[dict]]:
    """task -> the bounded sources of its requirements (phase-1 inspector and rework)."""
    try:
        inv = GI.load(ws)
        return {t["id"]: task_sources(ws, t, inv) for t in plan(ws)}
    except (ValueError, OSError, KeyError):
        return {}


def _names(ws: Path) -> str:
    return ", ".join(f"'the {n}'" for n in json.loads((Path(ws) / "configuration/system_names.json").read_text()))


def _scope_text(ws: Path) -> str:
    return " | ".join(_manifest(ws).get("scope") or [])


def iq_instructions(ws: Path, ref: dict) -> str:
    tpl = template(ws)
    return (f"Judge ONE functional-level software requirement of module {GI.load(ws)['module']} on its own against the "
            "individual quality criteria IQ-01..IQ-12 (Forge-C SWE.1 requirements quality guideline). The requirement "
            f"is the CURRENT ARTIFACT 'requirement' ({ref['swr']}, template {tpl['template_id']}); the CURRENT "
            "ARTIFACT 'task_requirements' lists the other requirements of the same author task as read-only context "
            "for IQ-09 consistency - never judge them. Judge the statement, its type and precondition, its links "
            "(input_id of the input register and locator; a derive link states its rationale; awaiting_traceability "
            "has none), its use cases, verification method and test level against the provided sources and the "
            "work-order scope. " + SEVERITY + " Project conventions (not defects): EARS with exactly one 'shall' and "
            f"a subject of {_names(ws)}; the functional level names the delivered public API and behaviour, never "
            "registers, bit fields, addresses or reset values (register detail belongs to SWE.3); invalid use is "
            "specified generically (parameter validity, operation permitted in the current state, error reporting); "
            "status draft, ASIL QM, CAL 0 and the allocation 'not applicable until SWE.2' are fixed by the lane. "
            "Work-order scope: " + _scope_text(ws))


def rework_schema(ws: Path) -> dict:
    return {"type": "object", "additionalProperties": False, "required": ["requirement"],
            "properties": {"requirement": requirement_schema(template(ws))}}


def rework_instructions(ws: Path, ref: dict, fixes: list[str]) -> str:
    t = next((x for x in plan(ws) if x["id"] == ref["task"]), {"origins": ORIGINS["group"]})
    return (f"Rework ONE functional-level software requirement: the CURRENT ARTIFACT 'requirement' (key '{ref['key']}', "
            f"task {ref['task']}). Resolve exactly the inspection findings below and nothing else; keep the key "
            f"'{ref['key']}'. Answer only this requirement as `requirement`; the other requirements of the task "
            "(CURRENT ARTIFACT 'task_requirements', read-only) stay as they are and are not part of your answer, so "
            "never move their content into this one. Each statement uses EARS (The/When/While/Where/If..then), "
            f"exactly one 'shall', a subject of {_names(ws)}, and ends with a period; origin_group is one of "
            + ", ".join(t["origins"]) + ". " + LEVEL_RULE + " " + LINK_RULE + " INSPECTION FINDINGS TO RESOLVE: "
            + " | ".join(fixes) + " Work-order scope: " + _scope_text(ws))


# ---- feature 018 phase 2 (the SET inspection) of a functional order (T023b) -------------------------------------------
SET_NOTE = (
    "This is a functional-level SWE.1 requirement set (template {template}): every requirement states title, "
    "statement (EARS, exactly one 'shall', subject {names}), type (functional, design_constraint, architectural), "
    "precondition, origin group (use_case, out_of_context, hal_design_constraint, state_behaviour or "
    "awaiting_traceability), links, use cases (ids of the governance package), verification method and test level; "
    "status draft, ASIL QM, CAL 0 and the allocation 'not applicable until SWE.2' are fixed by the lane. Traceability "
    "at this level: a trace link names an input of the governance input register (IN-nn, requirement_source inputs "
    "only) and the section it restates, a derive link also states its rationale, and a requirement no input supports "
    "is in awaiting_traceability with no links (its share is reported); the delivered code is the implementation "
    "under analysis and never a source. Level rule: the functional level names the delivered public API and "
    "observable behaviour, never registers, bit fields, register addresses or reset values, and no hexadecimal value - "
    "register-level detail and concrete negative cases belong to SWE.3; invalid use is specified generically "
    "(parameter validity, operation permitted in the current state, error reporting). Never ask for register-level "
    "content, reference-manual pages or register effects at this level. The governance package (input register, "
    "actors, use cases, scope lists, assumptions, open points) is a source.")
OUT_OF_CONTEXT_NOTE = (
    "SWE1-01/SWE1-05: .forge-run/manifest.json upstream.status OUT_OF_CONTEXT records the owner decision that this "
    "driver is developed out of context: no upstream system requirement and no allocated software safety requirement "
    "exist. The upstream baseline is the governance package (its input register: reference manual, datasheet, "
    "guideline, device description; its use cases) plus the work-order scope and budgets. SWE1-01 is met when that "
    "baseline is stated; SWE1-05 is met when every requirement has a trace link to an input of the register, a derive "
    "link with its rationale, or sits in awaiting traceability, and every in-scope use case and service group is "
    "covered by requirements (both directions). The absence of upstream system requirements, of an approved upstream "
    "template or of a safety allocation is not a finding.")


def inspector_notes(ws: Path, item: str) -> list[str]:
    """The SWE.1 inspector notes of a functional order (set-quality and gate-item packets); the register-level notes of
    `review._notes` stay unchanged for every other order."""
    from ..workflow import prompts
    from . import review as R
    from .c_language_context import for_workspace

    out = [prompts.OWNER_SCOPE_NOTE]
    if item in ("SWE1-01", "SWE1-05") and R.out_of_context(ws):
        out.append(OUT_OF_CONTEXT_NOTE)
    if note := for_workspace(ws):
        out.append(note)
    if item == "SWE1-03" and R.safe_state_outside_scope(ws):
        out.append(R.SAFE_STATE_NOTE)
    out.append(SET_NOTE.format(template=template(ws)["template_id"], names=_names(ws)))
    return out


def set_sources(ws: Path) -> list[str]:
    """Extra sources of the SWE.1 set inspection: the governance package the links and use cases refer to."""
    return [p for p in (GP.OUT_MD,) if (Path(ws) / p).is_file()]
