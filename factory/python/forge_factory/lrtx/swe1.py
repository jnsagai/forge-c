"""LRTX-T013/T015 (LRTX-FR-008/010/012/013): SWE.1 as coherent structured tasks for the local profile (LL layer).

1. Inventory (deterministic): every register field of the work order's key RM sections, with its section, page and bit
   range. Nothing may disappear silently: each field ends up named by a requirement or explicitly NOT covered with the
   scope reason the model gives.
2. Requirement groups (model, one packet per register, at most MAX_FIELDS fields): EARS requirements with source page,
   verification, verification level and register effects. Each answer is validated deterministically and repaired
   locally (only the named elements) within the visit's call budget.
3. Cross-cutting group (model): reset/startup behaviour and rules for all functions; resource requirements are
   rendered from the owner's work-order budgets (not invented).
4. Assembly (deterministic): SWR numbering, software_requirements.md, register_effects.json, requirements_to_tests.csv,
   upstream_gaps.md and the safety statement - the exact files the unchanged SWE.1 gates and inspector judge.
Validated packets are checkpointed by input hash and reused while their inputs are unchanged.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..brownfield import interface as BI
from ..common import canonical_json, sha256_bytes, utc_now
from ..inspection.ears import RESET_AFTER, STARTUP_NO_CALL
from . import structured as S
from . import visit as V

MAX_FIELDS = 5
SCOPE_COVERAGE_RULE = (
    "A REGISTER.FIELD explicitly named in the in-scope work-order text must not be listed in not_covered. "
    "A verifier limitation is an unresolved verification gap, not permission to remove a requested field."
)
# Owner change 2026-11-02 ("Build all four"; harvest of the cloud cross-inspection of local SWE.1 baselines, classes
# X5-X12): author contract rules of the SWE.1 author packets, in generic wording (no peripheral, register or vendor text).
AR_DOMAIN = (
    "AR-1 argument domain: for a function that takes a value, the requirement decides the supported argument domain. "
    "When the parameter type can hold values the field cannot, either state a caller precondition that excludes them "
    "or state the driver handling (masking, rejection or saturation) - never leave this decision, or a recommended "
    "minimum or maximum, to an open point. Its verification uses the minimum and the maximum supported value, and one "
    "out-of-domain value when the driver handles it.")
AR_ENABLING = (
    "AR-2 enabling conditions: when the source names conditions under which a field write takes no effect or is not "
    "allowed (write protection, an update still in progress, missing access rights), the statement states them as an "
    "EARS While-clause ('While <condition>, when <call>, the ... shall ...'), so they are caller preconditions of the "
    "supported domain.")
AR_DISCRIMINATING = (
    "AR-3 verification that can fail: a write case's value differs from the field's reset and initial contents (a "
    "boundary case equal to the reset value starts from other contents), the surrounding bits of the register are "
    "pre-set to non-zero values before a write or preservation check, and each function the requirement names has its "
    "own pass condition.")
AR_OBLIGATIONS = (
    "AR-4 owner obligations: an owner-approved obligation is a provided source, not invented behaviour - implement it "
    "in full and with its own scope (an obligation on accesses is not narrowed to writes).")
AR_OBLIGATION_GAPS = (
    " obligation_gaps only when an input the obligation needs is missing; the reason names that input. When the "
    "requirements implement only part of an obligation, write the remainder, or (non-critical obligations only) record "
    "the remainder in obligation_gaps with the reason.")
AR_PRESERVATION = (
    "AR-5 preservation: a rule for all functions is worded 'changes only the fields its requirement names, except the "
    "side effects the source documents' (also when a coverage rule says a write changes only the named bit), so it "
    "never contradicts a requirement that changes several fields together.")
AR_PAGE = "AR-6 source page: source_page is a page of the section the statement cites."
PROHIBITION_RULE = (
    "A requirement that prohibits an access (no read, no write, no access before the first call or in another window) "
    "is verified_by target_robot_test, never host_unit_test (the host fake register block keeps no access log): its "
    "verification passes when the target simulation's register-access log shows no such access in the prohibited "
    "window - never by final register contents alone.")
# a statement that prohibits a register access (X12); startup invariants are matched by STARTUP as before
PROHIBITION = re.compile(r"\bshall\s+(?:not|never)\s+(?:read|write|access)\b|"
                         r"\bshall\s+(?:perform|make|issue)\s+no\s+(?:\w+\s+)?(?:reads?|writes?|access(?:es)?)\b", re.I)
REGISTER_RULES = " ".join((AR_DOMAIN, AR_ENABLING, AR_DISCRIMINATING, AR_PAGE))
CROSSCUT_RULES = " ".join((AR_DISCRIMINATING, AR_PRESERVATION, AR_PAGE))
EFFECTS = "workproducts/SWE.1/register_effects.json"
REQS = "workproducts/SWE.1/software_requirements.md"
CSV = "traceability/requirements_to_tests.csv"
GAPS = "traceability/upstream_gaps.md"
SAFETY = "safety/software_safety_requirements.md"
STARTUP = re.compile(r"^\s*" + STARTUP_NO_CALL, re.I)
# CAPA-120: an input a verification calls with ("call ... with 0x00001234", "LL_X_Set(0x1234U)"), not a preset or an
# expected register word
CALL_INPUT = re.compile(r"(?:\bwith\s+(?:the\s+)?(?:value\s+|input\s+|argument\s+)?|\w\(\s*)(0x[0-9A-Fa-f]{1,8})(?![0-9A-Fa-f])")

EFFECT_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["case", "register", "field", "op", "value"],
                 "properties": {"case": {"type": "string", "pattern": "^[A-Z][A-Z0-9_]{1,47}$"},
                                "register": {"type": "string"}, "field": {"type": "string"},
                                "op": {"type": "string", "enum": ["set", "clear", "write", "no_write"]},
                                "value": {"type": "string"},
                                # CAPA-120: optional (baselines and provided documents without it stay valid)
                                "requested": {"type": "string"}}}
REQ_SCHEMA = {"type": "object", "additionalProperties": False,
              "required": ["key", "statement", "source_page", "verification", "verified_by", "effects"],
              "properties": {"key": {"type": "string", "pattern": "^[a-z][a-z0-9_]{2,40}$"},
                             "statement": {"type": "string", "minLength": 20},
                             "source_page": {"type": "integer"},
                             "verification": {"type": "string", "minLength": 10},
                             "verified_by": {"type": "string", "enum": ["host_unit_test", "target_robot_test"]},
                             "effects": {"type": "array", "items": EFFECT_SCHEMA}}}
GROUP_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["requirements", "not_covered", "open_points"],
                "properties": {"requirements": {"type": "array", "items": REQ_SCHEMA},
                               "not_covered": {"type": "array", "items": {
                                   "type": "object", "additionalProperties": False, "required": ["field", "reason"],
                                   "properties": {"field": {"type": "string"}, "reason": {"type": "string", "minLength": 5}}}},
                               "open_points": {"type": "array", "items": {"type": "string"}}}}


# ---- owner obligations (docs/designs/swe1-owner-obligation-coverage.md; opt-in per work order) --------------------
def owner_obligations(ws: Path) -> dict | None:
    from ..assurance import owner_obligations as OO

    return OO.declared(ws)


def group_schema(obl: dict | None, crosscutting: bool = False) -> dict:
    """GROUP_SCHEMA, unchanged when the work order declares no owner obligations; otherwise every requirement lists
    the ids it implements, and the cross-cutting task may record obligation gaps."""
    if obl is None:
        return GROUP_SCHEMA
    ids = [o["id"] for o in obl["obligations"]]
    req = {**REQ_SCHEMA, "required": REQ_SCHEMA["required"] + ["obligations"],
           "properties": {**REQ_SCHEMA["properties"],
                          "obligations": {"type": "array", "items": {"type": "string", "enum": ids}}}}
    out = {**GROUP_SCHEMA, "properties": {**GROUP_SCHEMA["properties"], "requirements": {"type": "array", "items": req}}}
    if crosscutting:  # only non-critical obligations may be recorded as gaps (owner 2026-10-31)
        gap_ids = [o["id"] for o in obl["obligations"] if not o.get("critical")]
        out["required"] = GROUP_SCHEMA["required"] + ["obligation_gaps"]
        out["properties"]["obligation_gaps"] = {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["id", "reason"],
            "properties": {"id": {"type": "string", "enum": gap_ids or ["(none)"]},
                           "reason": {"type": "string", "minLength": 10}}}}
        if not gap_ids:
            out["properties"]["obligation_gaps"]["maxItems"] = 0
    return out


def obligation_rule(obl: dict, crosscutting: bool) -> str:
    rule = (f" Owner obligations ({obl['_path']}, a provided source): obligations lists the ids of the owner "
            "obligations a requirement implements ([] if none). Cite an id only when the statement implements that "
            "obligation; an obligation that names register effects is implemented only by a requirement with those "
            "effects. " + AR_OBLIGATIONS)
    if crosscutting:
        critical = [o["id"] for o in obl["obligations"] if o.get("critical")]
        register = [o["id"] for o in obl["obligations"] if o.get("effects")]
        rule += (" Write the requirements for every owner obligation that no CURRENT ARTIFACT requirement implements "
                 "and that is not a single register field's behaviour (e.g. no status polling, no error code, other "
                 "fields and registers preserved). A non-critical obligation the inputs cannot support goes into "
                 "obligation_gaps with the reason; never drop an obligation silently. obligation_gaps stays empty "
                 "otherwise." + AR_OBLIGATION_GAPS)
        if critical:
            rule += (" Critical obligations always need an implementing requirement and can never be obligation gaps: "
                     + ", ".join(critical) + ".")
        if register:  # CAPA-080: those are the register tasks' requirements (CURRENT ARTIFACT), never written here
            rule += (" Obligations with register effects are implemented by the register tasks, not here: "
                     + ", ".join(register) + ".")
    return rule


# ---- inventory --------------------------------------------------------------------------------------------------------
def _manifest(ws: Path) -> dict:
    return json.loads((Path(ws) / ".forge-run/manifest.json").read_text())


def _section_files(ws: Path) -> dict[str, dict]:
    """section number -> {file, title, page} from inputs/index.md (first occurrence wins, like the builder)."""
    out: dict[str, dict] = {}
    for line in (Path(ws) / "inputs/index.md").read_text().splitlines():
        parts = [x.strip() for x in line.split(" | ")]
        if len(parts) == 4 and parts[0][:1].isdigit() and parts[0] not in out:
            page = int(parts[2][2:]) if parts[2].startswith("p.") and parts[2][2:].isdigit() else None
            out[parts[0]] = {"file": parts[3], "title": parts[1], "page": page}
    return out


def _file_pages(text: str, start: int | None) -> list[int]:
    """The RM pages of one section file: its header's start page, its page anchors and the index start page."""
    return sorted({int(p) for p in re.findall(r"p\.(\d+)", text.split("\n", 1)[0])} |
                  {int(p) for p in re.findall(r'id="p-(\d+)"', text)} | ({start} if start else set()))


def section_pages(ws: Path, num: str, secs: dict[str, dict] | None = None) -> list[int]:
    """CAPA-114: the pages of RM section `num` and of its subsections (inputs/index.md and the section files); [] when
    the index has no such section."""
    secs = _section_files(ws) if secs is None else secs
    out: set[int] = set()
    for n, s in secs.items():
        if n == num or n.startswith(num + "."):
            f = Path(ws) / s["file"]
            out |= set(_file_pages(f.read_text(errors="replace"), s["page"]) if f.is_file() else
                       ([s["page"]] if s["page"] else []))
    return sorted(out)


def cited_sections(ws: Path, text: str, secs: dict[str, dict] | None = None) -> list[str]:
    """CAPA-114: the RM section ids a requirement text cites ('<RM doc> 26.4.3', 'section 26.4.3', 'sections 26.4.3 and
    26.4.4') that the work order's section index lists."""
    from ..layer import profile

    secs = _section_files(ws) if secs is None else secs
    try:
        doc = str((profile(ws).get("rm") or {}).get("doc") or "")
    except Exception:  # noqa: BLE001 - a workspace without a profile still has the generic section wording
        doc = ""
    lead = (re.escape(doc) + r"\s+(?:sections?\s+)?|" if doc else "") + r"\bsections?\s+"
    num = r"\d+(?:\.\d+)+"
    out = []
    for m in re.finditer(rf"(?:{lead})({num}(?:\s*(?:,|and|or|/)\s*{num})*)", text, re.I):
        out += [n for n in re.findall(num, m.group(1)) if n in secs and n not in out]
    return out


def cited_page_findings(ws: Path, r: dict, secs: dict[str, dict] | None = None) -> list[str]:
    """CAPA-114 (run WO-F014-SWE1-CRCL-20261102-L12, SWR-006): a requirement whose text cites an RM section must take
    its source_page from that section; otherwise the page-derived trace row names another section than the text (the
    inspector failed SWE1-01/SWE1-05 and the author never saw why). Passes when the page lies in any cited section."""
    secs = _section_files(ws) if secs is None else secs
    cited = cited_sections(ws, r["statement"], secs)
    ranges = {n: section_pages(ws, n, secs) for n in cited}
    ranges = {n: p for n, p in ranges.items() if p}
    page = r.get("source_page")
    if not ranges or not isinstance(page, int) or any(min(p) <= page <= max(p) for p in ranges.values()):
        return []
    where = "; ".join(f"section {n}: pages {min(p)}-{max(p)}" for n, p in ranges.items())
    return [f"[{r['key']}] source_page {page} is not a page of the RM section its statement cites ({where}): set "
            "source_page to the page of the cited section that states the fact, or cite the section of that page"]


def system_name(ws: Path) -> str:
    from ..layer import layer_of, profile

    names = json.loads((Path(ws) / "configuration/system_names.json").read_text())
    want = profile(ws).get("system_name") or "RCC LL driver"
    if layer_of(ws) != "LL":
        want = want.replace(" LL", "")
    return want if want in names else names[0]


def inventory(ws: Path) -> dict:
    from ..assurance.hardware import parse_section
    from ..layer import profile, register_prefix

    ws = Path(ws)
    prof, pfx, secs = profile(ws), register_prefix(ws), _section_files(ws)
    manifest = _manifest(ws)
    local = manifest.get("local_profile") or {}
    structured = {}
    if local.get("id"):
        from .profile import load

        structured = load(local["id"]).get("structured") or {}
    selected = list(prof["rm"]["key_sections"])
    if structured.get("complete_scope_sections") is True:
        from .obligations import scope_sections

        selected = scope_sections(manifest["scope"], prof["rm"]["doc"], selected)
    regs, missing = [], []
    for num in selected:
        s = secs.get(num)
        if s is None:
            missing.append(num)
            continue
        text = (ws / s["file"]).read_text(errors="replace")
        r = parse_section(text, pfx)
        if r is None:
            missing.append(num)
            continue
        pages = _file_pages(text, s["page"])
        desc = {m.group(3): " ".join(m.group(4).split())[:120] for m in re.finditer(
            r"^\s*Bits?\s+(\d+)(?::(\d+))?\s+([A-Z][A-Z0-9_]*)(?:\[[^\]]*\])?\s*:\s*(.+)$", text, re.M)}
        regs.append({"section": num, "file": s["file"], "register": r["name"], "offset": r["offset"],
                     "pages": pages, "fields": {k: {"msb": v["msb"], "lsb": v["lsb"], "access": v.get("access", []),
                                                    "description": desc.get(k, "")}
                                                for k, v in r["fields"].items()}})
    items = [f"{r['register']}.{f}" for r in regs for f in r["fields"]]
    inv = {"schema": "forge-c/lrtx-swe1-inventory/1", "registers": regs, "items": items, "missing_sections": missing,
           "generated_at": utc_now()}
    if structured.get("complete_scope_sections") is True:
        inv["scope_sections"] = {"document": prof["rm"]["doc"], "catalog_seeds": prof["rm"]["key_sections"],
                                 "required_sections": selected, "basis": "LITERAL_OWNER_REFERENCES_AND_CATALOG"}
    if structured.get("coherent_scope_groups") is True:
        from .obligations import scope_field_sets

        inv["coherent_field_sets"] = scope_field_sets(manifest["scope"])
    return inv


def groups(inv: dict) -> list[dict]:
    """One packet per register, split at MAX_FIELDS fields (field order of the RM section kept)."""
    from .obligations import partition

    out = []
    for r in inv["registers"]:
        names = list(r["fields"])
        parts = partition(r["register"], names, inv.get("coherent_field_sets", []), MAX_FIELDS)
        for i, part in enumerate(parts):
            gid = f"{r['register']}" + (f"_{i + 1}" if len(parts) > 1 else "")
            out.append({"id": gid, "register": r["register"], "section": r["section"], "file": r["file"],
                        "pages": r["pages"], "fields": {f: r["fields"][f] for f in part}})
    return out


# ---- packet texts -----------------------------------------------------------------------------------------------------
def coverage_guidance(ws: Path) -> str:
    """The work order's coverage rules, from the same texts the agent prompts use (no new requirements policy)."""
    from ..layer import layer_of, profile
    from ..workflow import prompts

    prof = profile(ws)
    cover = ((prof.get("prompt") or {}).get("swe1_cover"))
    if cover:
        return " ".join(cover.split())
    step = (prompts.LL_AUTHOR_STEPS if layer_of(ws) == "LL" else prompts.AUTHOR_STEPS)["SWE.1"][1]
    m = re.search(r"(Cover:.*?)(?:Add three measurable|$)", step, re.S)
    return " ".join((m.group(1) if m else step).split())


def effect_rule(ws: Path) -> str:
    from ..layer import profile

    rule = (profile(ws).get("prompt") or {}).get("swe1_effect_rule")
    base = ("effects: one entry per bit and per function the requirement sets or clears (op set|clear), writes a value "
            "to (op write, value \"0x...\") or only reads (op no_write with register and field); value is \"\" unless "
            "op is write. register/field are the RM names the statement itself uses (write them as REGISTER.FIELD in "
            "the statement). case ids are unique UPPER_CASE names. A write whose requirement passes an input that does "
            "not fit the field and keeps only its low bits (e.g. 'write only bits 11:0 of the requested value', "
            "verified with 0x1234) also gives requested, the input the call passes (\"0x1234\"), while value is the "
            "field result (\"0x234\"); omit requested otherwise.")
    return base + (" " + " ".join(rule.split()) if rule else "")


STOP = {"with", "from", "into", "only", "their", "this", "that", "work", "order", "api", "the", "and", "for"}


def scope_hints(ws: Path, g: dict) -> dict[str, str]:
    """Per field: whether the work-order scope names it, and which out-of-scope terms its RM description matches.
    Hints for the author; only a field or register the out-of-scope text names explicitly is a hard rule."""
    m = _manifest(ws)
    out_txt = " ".join(x for x in m["scope"] if x.lower().startswith("out of scope")).lower()
    in_txt = " ".join(x for x in m["scope"] if not x.lower().startswith("out of scope"))
    words = {w for w in re.findall(r"[a-z]{4,}", out_txt.replace("-", " ")) if w not in STOP}
    every = [v.get("description", "").lower() for r in inventory(ws)["registers"] for v in r["fields"].values()]
    common = {w for w in words if sum(w in d for d in every) > max(1, len(every) // 2)}  # e.g. 'watchdog'
    out = {}
    for f, v in g["fields"].items():
        named = bool(re.search(rf"\b{re.escape(f)}\b", in_txt))
        hits = sorted(w for w in words - common if w in v.get("description", "").lower().replace("-", " "))
        out[f] = ("named in the work-order scope" if named else "not named in the in-scope text") + (
            f"; its description matches out-of-scope term(s) {', '.join(hits)}" if hits else "")
    return out


def out_of_scope_named(ws: Path) -> set[str]:
    """Registers and REG.FIELD names the out-of-scope text names explicitly (a hard rule)."""
    from ..layer import register_prefix

    m = _manifest(ws)
    out_txt = " ".join(x for x in m["scope"] if x.lower().startswith("out of scope"))
    return set(re.findall(rf"\b{register_prefix(ws)}_[A-Z0-9]+(?:\.[A-Z0-9_]+)?\b", out_txt))


def required_scope_exclusions(ws: Path, doc: dict, g: dict) -> list[str]:
    """Enforce explicit owner scope only; unmentioned hardware fields acquire no new requirement."""
    text = " ".join(x for x in _manifest(ws)["scope"] if not x.lower().startswith("out of scope"))
    excluded = {x["field"] if "." in x["field"] else f"{g['register']}.{x['field']}"
                for x in doc["not_covered"]}
    required = []
    for field in g["fields"]:
        full = f"{g['register']}.{field}"
        if full in excluded and re.search(rf"(?<![\w.]){re.escape(full)}(?![\w.])", text):
            required.append(full)
    return [f"REQUIRED_SCOPE_FIELD_EXCLUDED:{full}: keep the requested scope and report the verification gap"
            for full in sorted(required)]


def delivered_interface(ws: Path) -> str | None:
    """CAPA-112 (runs WO-F014-CMP-SWE1-CRCL-20261102-05/-06): the declared delivered-interface input of a brownfield
    work order (the scoped functions' argument/return constants and values), else None."""
    rel = BI.declared(_manifest(ws))
    return rel if rel and (Path(ws) / rel).is_file() else None


def group_packet(ws: Path, g: dict, model: str, findings: list[str] | None = None, previous: dict | None = None) -> dict:
    from .c_language_context import for_workspace

    m = _manifest(ws)
    sysname = system_name(ws)
    hints = scope_hints(ws, g)
    fields = "; ".join(f"{g['register']}.{f} (bits {v['msb']}:{v['lsb']}, access {'/'.join(v['access']) or '?'}, "
                       f"RM: '{v.get('description', '')}'; {hints[f]})" for f, v in g["fields"].items())
    instr = (f"Write the software requirements of the {sysname} for register {g['register']} (RM0486 section "
             f"{g['section']}). Fields of this task: {fields}. Work-order scope: " + " | ".join(m["scope"]) +
             f". Coverage rules of this work order: {coverage_guidance(ws)} Apply them ONLY to the fields of this task; "
             "other registers are separate tasks, and reset/startup behaviour and rules for all functions belong to a "
             "separate cross-cutting task - never write them here. Every requirement of this task names a field of this "
             "task as REGISTER.FIELD. For every field of this task either write the requirements the scope "
             "demands for it or list it in not_covered with the scope reason. " + SCOPE_COVERAGE_RULE +
             " Each statement uses EARS "
             f"(The/When/While/Where/If..then), exactly one 'shall', the subject 'the {sysname}', and ends with a period; "
             "name the field as REGISTER.FIELD. verification states the test and its pass criterion ('... passes "
             "when ...'), checking register bits and return values on the register array. " + PROHIBITION_RULE +
             " verified_by is host_unit_test, except startup/reset behaviour ('While no ... after reset') and access "
             f"prohibitions, which are target_robot_test. source_page is the RM0486 page of the cited fact ({', '.join(map(str, g['pages']))}). "
             + effect_rule(ws) + " key is a short snake_case name of the requirement. open_points lists ambiguities of "
             "the source (or nothing). Author rules: " + REGISTER_RULES)
    crit = [f"every requirement's subject is exactly 'the {sysname}'", "every field of the task is covered or listed "
            "in not_covered", "every effect names a field of this task that its statement names",
            "a statement that sets, clears or writes a field has an effect for it"]
    srcs = [S.source(ws, g["file"])]
    if api := delivered_interface(ws):  # CAPA-112: a FROZEN API's argument constants (brownfield)
        instr += BI.AUTHOR_NOTE
        srcs.append(S.source(ws, api))
    obl = owner_obligations(ws)
    if obl is not None:
        instr += obligation_rule(obl, False)
        srcs.append(S.source(ws, obl["_path"]))
        crit.append("every cited obligation is implemented by its requirement")
    if note := for_workspace(ws):
        instr += " " + note
    return S.packet(phase="SWE.1", task=f"requirements:{g['id']}", role="swe1-author", instructions=instr,
                    sources=srcs, criteria=crit, output_schema=group_schema(obl), model=model,
                    findings=findings, previous=previous)


def crosscut_packet(ws: Path, functional: list[dict], model: str, findings: list[str] | None = None,
                    previous: dict | None = None) -> dict:
    from .c_language_context import for_workspace

    m = _manifest(ws)
    sysname = system_name(ws)
    obl = owner_obligations(ws)
    if obl is None:
        listing = "\n".join(f"- [{r['key']}] {r['statement']}" for r in functional)
    else:  # CAPA-082: the answer schema's own field names, so obligation ids are never mistaken for statement text
        listing = "\n".join(json.dumps({"key": r["key"], "statement": r["statement"],
                                        "obligations": r.get("obligations") or []}) for r in functional)
    instr = (f"The register-level requirements of the {sysname} are already written (listed below as CURRENT "
             "ARTIFACT). Write only the requirements that do not belong to one register field: the reset/startup "
             f"behaviour (e.g. 'While no LL function has been called after reset, the {sysname} shall not write any "
             "register.'), the failure handling the work-order scope states (e.g. that the driver never waits on a "
             "status flag because the caller bounds its polling; SWE1-03 requires failure handling, reset/startup "
             "behaviour and safe states to be specified) and any rule the coverage rules state for all functions "
             "(e.g. that a function changes only the fields its requirement names, except the side effects the source "
             "documents). Work-order scope: " + " | ".join(m["scope"]) +
             f". Coverage rules: {coverage_guidance(ws)} "
             "Do NOT write flash/RAM/stack budget requirements: the factory adds them from the owner's work-order "
             "budgets. Every statement uses EARS (The/When/While/Where/If..then), exactly one 'shall', "
             f"the subject 'the {sysname}', and ends with a period. "
             "verification states the test and its explicit pass criterion ('... passes when ...'). " + PROHIBITION_RULE +
             " source_page is the RM0486 page supporting the requirement, from the provided sources. "
             "Reset/startup requirements are target_robot_test. effects stay empty unless a statement sets, clears or writes a "
             "named field. not_covered stays empty. Author rules: " + CROSSCUT_RULES)
    art = {"path": "lrtx:functional_requirements", "text": listing, "sha256": sha256_bytes(listing.encode())}
    secs = _section_files(ws)
    from ..layer import profile

    chapter = str(profile(ws)["rm"]["chapter"])
    func = [n for n, s in secs.items() if n.startswith(chapter + ".") and "functional" in s["title"].lower()]
    srcs = [S.source(ws, secs[n]["file"], max_chars=20_000) for n in func[:1]]
    crit = [f"subject exactly 'the {sysname}'", "no budget requirements"]
    if obl is not None:
        instr += obligation_rule(obl, True)
        srcs.append(S.source(ws, obl["_path"]))
        crit.append("every owner obligation is implemented by a requirement or listed in obligation_gaps")
    if note := for_workspace(ws):
        instr += " " + note
    return S.packet(phase="SWE.1", task="requirements:crosscutting", role="swe1-author", instructions=instr,
                    sources=srcs, artifacts=[art], criteria=crit,
                    output_schema=group_schema(obl, crosscutting=True), model=model, findings=findings,
                    previous=previous)


# ---- deterministic validation of one answer -------------------------------------------------------------------------
def _value(v: str) -> int | None:
    try:
        return int(v, 0) if isinstance(v, str) else None
    except ValueError:
        return None


def ears_hint(code: str, sysname: str) -> str:
    """What to change, for each EARS finding of the deterministic checker (the agent prompt states the same rules)."""
    m = re.match(r"EARS_NOT_ATOMIC_(\d+)_SHALL", code)
    if m:
        return f"the statement has {m.group(1)} 'shall': split it into {m.group(1)} requirements with one 'shall' each"
    return {"EARS_NO_SHALL": "the statement needs exactly one 'shall'",
            "EARS_PATTERN_NONCONFORMANT": f"start with The/When/While/Where/If..then and use 'the {sysname} shall'",
            "EARS_MISSING_TERMINATOR": "end the statement with a period",
            "EARS_UNKNOWN_SYSTEM_NAME": f"the subject must be exactly 'the {sysname}'"}.get(
        code.split(":", 1)[0], "remove weak modal or vague wording (should/may/will/must/can, fast, as required)")


def validate_group(ws: Path, doc: dict, g: dict | None, sysname: str, idx: dict) -> list[str]:
    from ..assurance import register_contract as RC
    from ..assurance.register_contract import _needs_contract
    from ..inspection.ears import Requirement, check_statement
    from ..layer import register_prefix

    pfx = register_prefix(ws)
    secs = _section_files(ws) if (Path(ws) / "inputs/index.md").is_file() else {}  # no index: no citable section
    out, keys, named = [], set(), set()
    for r in doc["requirements"]:
        k = r["key"]
        if k in keys:
            out.append(f"[{k}] duplicate key")
        keys.add(k)
        st = r["statement"]
        tagged = re.search(r"\(\s*obligations?\s*:[^)]*\)|\bOBL-[a-z0-9][a-z0-9-]*", st, re.I)
        if tagged:  # CAPA-082 (run -06): ten repairs answered only "end the statement with a period"
            out.append(f"[{k}] the statement contains owner-obligation ids ('{tagged.group(0)}'): remove them from the "
                       "statement text and list them only in the obligations field")
        if g is not None and (STARTUP.match(st) or re.search(RESET_AFTER + r"|\breset (?:value|state)\b", st,
                                                             re.I)):
            # lrtx6 (2026-10-21): a reset-state requirement with effects stayed in a register task over 3 repairs
            out.append(f"[{k}] is a reset/startup requirement: those belong to the cross-cutting task - remove "
                       f"requirement [{k}] from this task")
            continue
        for f in check_statement(Requirement(k, st, 0), {sysname}).findings:
            code = f.split(":", 1)[1] if ":" in f else f
            if code.startswith("EARS_SYSTEM_NAME_HINT"):
                continue
            out.append(f"[{k}] {code}: {ears_hint(code, sysname)}")
        if "pass" not in r["verification"].lower():
            out.append(f"[{k}] verification has no pass criterion ('passes when ...')")
        if STARTUP.match(st) and r["verified_by"] != "target_robot_test":
            out.append(f"[{k}] a startup/reset invariant is verified by target_robot_test, not a host unit test")
        elif PROHIBITION.search(st) and r["verified_by"] != "target_robot_test":
            # owner 2026-11-02 (X12, "Allow access logging"): only the target simulation logs register accesses
            out.append(f"[{k}] prohibits a register access: verified_by is target_robot_test - only the target "
                       "simulation's register-access log can show that no such access happens (the host fake keeps no "
                       "access log); state the pass condition on that log")
        if g is not None and g["pages"] and not (min(g["pages"]) <= r["source_page"] <= max(g["pages"]) + 2):
            out.append(f"[{k}] source_page {r['source_page']} is outside the section pages {g['pages']}")
        out += cited_page_findings(ws, r, secs)
        for f in re.findall(rf"\b({pfx}_[A-Z0-9]+)\.([A-Z0-9_]+)", st):
            named.add(f"{f[0]}.{f[1]}")
            if f[0] not in idx or f[1] not in idx[f[0]]["fields"]:
                out.append(f"[{k}] {f[0]}.{f[1]} is not a field of the RM0486 register index")
        for e in r["effects"]:
            reg, fld, op = e["register"], e["field"], e["op"]
            if g is not None and (reg != g["register"] or fld not in g["fields"]):
                owner = f"the {reg} task" if reg != g["register"] else "another task of this register"
                out.append(f"[{k}] acts on {reg}.{fld}, which {owner} covers: remove requirement [{k}] from this task")
                continue
            if reg not in idx or fld not in idx[reg]["fields"]:
                out.append(f"[{k}] effect {e['case']} names {reg}.{fld}, not in the RM0486 register index")
                continue
            if f"{reg}.{fld}" not in st and not (reg in st and fld in st):
                out.append(f"[{k}] effect {e['case']}: the statement must name {reg}.{fld}")
            acc = set(idx[reg]["fields"][fld].get("access") or [])
            if op in ("write", "set", "clear") and acc and acc <= {"r", "rc_r"}:
                # lrtx7 (2026-10-21): "shall set IWDG_SR.WVU" - a hardware status flag software can only read
                out.append(f"[{k}] effect {e['case']}: {reg}.{fld} is read-only in RM0486 (access "
                           f"{'/'.join(sorted(acc))}); software cannot {op} it - specify what the driver reads or "
                           f"returns, or remove requirement [{k}]")
            if op == "write":
                width = idx[reg]["fields"][fld]["msb"] - idx[reg]["fields"][fld]["lsb"] + 1
                v = _value(e["value"])
                if v is None or not 0 <= v < (1 << width):
                    out.append(f"[{k}] effect {e['case']}: value {e['value']!r} must be a number that fits "
                               f"{reg}.{fld} ({width} bits)")
                elif RC.requested_problem(e, width):
                    out.append(f"[{k}] effect {e['case']}: {RC.requested_problem(e, width)}")
                elif e.get("requested") in (None, ""):
                    # CAPA-120: the verification calls with an input above the field that truncates to this value,
                    # but the case records only the value - SWE.2 would then have to pass the truncated value
                    big = [n for n in CALL_INPUT.findall(r["verification"])
                           if int(n, 16) >= (1 << width) and int(n, 16) & ((1 << width) - 1) == v]
                    if big:
                        out.append(f"[{k}] effect {e['case']}: the verification calls with {big[0]}, which does not "
                                   f"fit {reg}.{fld} ({width} bits) and leaves {e['value']}: give requested "
                                   f"\"{big[0]}\" (the input the call passes) and keep value {e['value']}")
            elif e["value"] not in ("", None):
                out.append(f"[{k}] effect {e['case']}: value must be \"\" for op {op}")
            if op != "write" and RC.requested_problem(e, None):
                out.append(f"[{k}] effect {e['case']}: {RC.requested_problem(e, None)}")
        if g is not None and not r["effects"] and not any(f"{g['register']}.{f}" in st or
                                                          (g["register"] in st and f in st) for f in g["fields"]):
            out.append(f"[{k}] names no field of this task: reset/startup and all-function rules belong to the "
                       "cross-cutting task - remove this requirement here")
        excl = out_of_scope_named(ws)
        for nm in sorted(n for n in {f"{e['register']}.{e['field']}" for e in r["effects"]} |
                         {e["register"] for e in r["effects"]} if n in excl):
            out.append(f"[{k}] acts on {nm}, which the work-order scope lists as out of scope: list it in not_covered")
        if _needs_contract(st, pfx) and not r["effects"]:  # the gate's rule (CONTRACT_SWR_NOT_COVERED)
            out.append(f"[{k}] the statement names a field it sets or clears but has no effect entry")
    if g is not None:
        out += required_scope_exclusions(ws, doc, g)
        covered = named | {f"{e['register']}.{e['field']}" for r in doc["requirements"] for e in r["effects"]}
        excluded = {x["field"] if "." in x["field"] else f"{g['register']}.{x['field']}" for x in doc["not_covered"]}
        for f in g["fields"]:
            full = f"{g['register']}.{f}"
            if full not in covered and full not in excluded:
                out.append(f"field {full} is neither named by a requirement nor listed in not_covered")
            if full in covered and full in excluded:
                out.append(f"field {full} is both covered and listed in not_covered")
        out += [f"not_covered {x['field']} is not a field of this task" for x in doc["not_covered"]
                if (x["field"].split(".")[-1]) not in g["fields"]]
    elif doc["not_covered"]:
        out.append("not_covered must be empty for the cross-cutting task")
    if g is None:  # lrtx6 (2026-10-21): the cross-cutting task wrote status-flag queries that a register task covers
        tasked = {x.split(".")[0] for x in inventory(ws)["items"]}
        # CAPA-080 (run -04): only obligations WITHOUT register effects are the cross-cutting task's to keep
        obl = owner_obligations(ws)
        with_effects = {o["id"] for o in (obl or {}).get("obligations", []) if o.get("effects")}

        def keepable(r: dict) -> bool:
            return bool(r.get("obligations")) and not set(r["obligations"]) & with_effects
        for r in doc["requirements"]:
            # lrtx9 (2026-10-21): it rewrote the IWDG_KR/PR/RLR writes with effects, duplicating the register tasks
            for reg in sorted({e["register"] for e in r["effects"]} & tasked):
                if keepable(r):  # CAPA-079: never tell the author to delete what an effect-free obligation needs
                    out.append(f"[{r['key']}] acts on {reg}, which the {reg} task covers: keep [{r['key']}] for owner "
                               f"obligation(s) {', '.join(r['obligations'])}, but remove its effects on {reg} and state "
                               f"it for all scoped functions without naming {reg}")
                    continue
                effect_ids = sorted(set(r.get("obligations") or []) & with_effects)
                out.append(f"[{r['key']}] acts on {reg}, which the {reg} task covers - remove requirement "
                           f"[{r['key']}] from the cross-cutting task" + (
                               f" (owner obligation(s) {', '.join(effect_ids)} have register effects: the {reg} task "
                               "implements them)" if effect_ids else ""))
        if not any(STARTUP.match(r["statement"]) for r in doc["requirements"]):
            # lrtx9: a repair dropped the startup invariant the packet asks for (SWE1-03 then failed for real)
            out.append(f"the cross-cutting task must state the reset/startup behaviour, e.g. 'While no LL function has "
                       f"been called after reset, the {sysname} shall not write any {pfx} register.' "
                       "(verified_by target_robot_test)")
        for r in doc["requirements"]:
            regs = sorted({f[0] for f in re.findall(rf"\b({pfx}_[A-Z0-9]+)\.([A-Z0-9_]+)", r["statement"])
                           if f[0] in idx} - {e["register"] for e in r["effects"]})
            if regs and not STARTUP.match(r["statement"]) and not r["effects"] and keepable(r):
                # CAPA-079 (run -03): "remove requirement" made the author delete the requirement an owner obligation
                # needed; the rule stays (no register requirement here), the instruction says how to keep it
                out.append(f"[{r['key']}] names {', '.join(regs)}, which its register task covers: keep [{r['key']}] for "
                           f"owner obligation(s) {', '.join(r['obligations'])}, but state it for all scoped functions "
                           f"without naming {', '.join(regs)} (e.g. 'the {sysname} shall leave every other register "
                           f"and every other {pfx} instance unchanged')")
            elif regs and not STARTUP.match(r["statement"]) and not r["effects"]:
                effect_ids = sorted(set(r.get("obligations") or []) & with_effects)
                out.append(f"[{r['key']}] is a requirement on {', '.join(regs)}, which its register task covers - remove "
                           f"requirement [{r['key']}] from the cross-cutting task" + (
                               f" (owner obligation(s) {', '.join(effect_ids)} have register effects: the register "
                               "task implements them)" if effect_ids else ""))
    return out


def crosscut_obligation_findings(ws: Path, doc: dict, functional: list[dict]) -> list[str]:
    """CAPA-079: the cross-cutting task (the last one, which sees every functional requirement) is checked for the
    declared owner obligations without register effects, so their repair shares the task's own repair pass instead of
    waiting for the post-assembly coverage check. Obligations with register effects belong to the register tasks."""
    obl = owner_obligations(ws)
    if obl is None:
        return []
    cited = {i for r in functional + doc["requirements"] for i in r.get("obligations") or []}
    gaps = {g["id"] for g in doc.get("obligation_gaps") or []}
    out = []
    for o in obl["obligations"]:
        if o.get("effects") or o["id"] in cited or (o["id"] in gaps and not o.get("critical")):
            continue
        kind = "critical owner obligation" if o.get("critical") else "owner obligation"
        out.append(f"{kind} {o['id']} has no implementing requirement: write it here as a rule for all scoped "
                   f"functions (owner: {o['statement'][:160]})" + ("" if o.get("critical") else
                                                                     " or list it in obligation_gaps with the reason"))
    return out


# ---- assembly (deterministic rendering of the existing SWE.1 work products) -------------------------------------------
def _page_section(ws: Path, page: int | None, fallback: str) -> str:
    """The RM0486 section whose page range holds `page` (key sections first), else the task's own section."""
    if page is None:
        return fallback
    secs = _section_files(ws)
    starts = sorted(((s["page"], n) for n, s in secs.items() if s["page"]), key=lambda x: (x[0], -len(x[1])))
    best = None
    for start, n in starts:
        if start <= page:
            best = n if best is None or start >= secs[best]["page"] else best
    return best or fallback


def _task_section(ws: Path, page: int | None, g: dict) -> str:
    """CAPA-107: a register task's requirement traces to the task's own section when its page is one of that section's
    pages. Several RM0486 register sections can start on one page (IWDG_KR 59.7.1 and IWDG_PR 59.7.2 both on p.2989);
    the page alone would trace every requirement on that page to the last of them."""
    pages = g.get("pages") or []
    if page is not None and pages and min(pages) <= page <= max(pages):
        return g["section"]
    return _page_section(ws, page, g["section"])


def budget_requirements(ws: Path, sysname: str) -> list[dict]:
    b = _manifest(ws)["budgets"]
    src = "work-order budget (owner development target)"
    robot = "SWE.6 Robot suite checks the target linker map, size-tool and stack-usage evidence of the driver image; "
    requirements = [{"key": "budget_flash", "statement": f"The {sysname} shall occupy at most {b['flash_bytes']} bytes of flash.",
             "source": src, "verification": robot + f"passes when the driver flash usage is at most {b['flash_bytes']} "
             "bytes.", "verified_by": "target_robot_test", "effects": [], "upstream": "WO-BUDGET"},
            {"key": "budget_static_ram", "statement": f"The {sysname} shall use at most {b['static_ram_bytes']} bytes "
             "of static RAM.", "source": src, "verification": robot + "passes when the driver-owned data and BSS total "
             f"at most {b['static_ram_bytes']} bytes, excluding the externally provided register array.",
             "verified_by": "target_robot_test", "effects": [], "upstream": "WO-BUDGET"},
            {"key": "budget_stack", "statement": f"The {sysname} shall use at most {b['stack_bytes']} bytes of stack "
             "for any public API call.", "source": src, "verification": robot + "passes when the worst-case stack usage "
             f"of every public API call chain is at most {b['stack_bytes']} bytes.", "verified_by": "target_robot_test",
             "effects": [], "upstream": "WO-BUDGET"}]
    from ..simulation_performance import selected

    performance = selected(ws)
    if performance:
        from ..mcp.servers.sim import measurement_profile

        where = measurement_profile(ws)  # CAPA-110: name the one measurement configuration, not "the pinned profile"
        source = "work-order simulation-only performance allocation; not a reference-manual or silicon timing claim"
        for key, limit, units in (("cpu", performance["instructions_per_call"], "executed target instructions"),
                                  ("time", performance["microseconds_per_call"], "microseconds of virtual time")):
            requirements.append({"key": "budget_simulation_" + key,
                                 "statement": f"When a scoped API is measured in the factory's pinned Renode simulation at "
                                 f"{performance['performance_mips']} MIPS without injected interrupts or bus stalls, "
                                 f"the {sysname} shall complete each measured call within {limit} {units}.",
                                 "source": source, "verification": f"Measurement configuration: {where}. "
                                 "SWE.6 Robot checks the independent Renode entry/return "
                                 "instruction and virtual-time records for every scoped function; missing, incomplete or "
                                 "over-budget measurements fail. Run Target Scenario on the declared test, then "
                                 "Simulation Performance Should Meet Budget; no hardware WCET is established.",
                                 "verified_by": "target_robot_test", "effects": [], "upstream": "WO-SIMULATION-PERFORMANCE"})
    return requirements


def _scope_ids(alloc: str) -> tuple[str, str]:
    asil = re.search(r"\b(ASIL [A-D]|QM)\b", alloc)
    sid = re.search(r"\((SC-[^,)\s]+)", alloc)
    return (asil.group(1) if asil else "UNSPECIFIED"), (sid.group(1) if sid else "no scope id")


def safety_text(ws: Path) -> str | None:
    """The SWE.1 safety statement exactly as the SWE.1 author instructions prescribe it; None when an allocation exists
    (then the safety-relevant SWRs must come from an upstream SSR task - not implemented here: the visit fails)."""
    from ..release import qm
    if qm.workspace_record(ws):
        return "# Quality management scope\n\n" + qm.STATEMENT + "\n"
    from ..release.aspice import STATEMENT, workspace_record

    if workspace_record(ws):
        return "# Assurance scope\n\n" + STATEMENT + "\n"
    alloc = _manifest(ws)["target"].get("safety_allocation", "")
    if "OUT_OF_SCOPE" in alloc:
        return ("# Software safety requirements\n\nQM development scope: no software safety requirements are allocated "
                "(work-order owner decision).\n")
    if "PENDING owner allocation review" in alloc:
        asil, sid = _scope_ids(alloc)
        return (f"# Software safety requirements\n\nTarget {asil} ({sid}): software safety allocation PENDING owner "
                "allocation review - no software safety requirement is allocated yet; this is an open gap, not a QM "
                f"claim.\n\nSafety context recorded in the work-order manifest: {alloc}. No safety items are listed "
                "until the owner's allocation review allocates software safety requirements.\n")
    return None


def assemble(ws: Path, inv: dict, results: list[tuple[dict, dict]], cross: dict) -> dict:
    """results: [(group, VALID task record)]. Writes the SWE.1 work products; returns the SWR map."""
    from ..layer import profile

    from ..assurance import owner_obligations as OO
    from . import review as R

    ws = Path(ws)
    m = _manifest(ws)
    sysname, pid = system_name(ws), profile(ws)["id"]
    rows: list[dict] = []
    for g, rec in results:
        for r in rec["doc"]["requirements"]:
            rows.append({**r, "task": rec["task"], "source": f"RM0486 p.{r['source_page']}",
                         "upstream": f"RM0486-{_task_section(ws, r['source_page'], g)}"})
    first = inv["registers"][0]["section"] if inv["registers"] else "?"
    for r in cross["doc"]["requirements"]:
        rows.append({**r, "task": cross["task"], "source": f"RM0486 p.{r['source_page']}",
                     "upstream": f"RM0486-{_page_section(ws, r['source_page'], first)}"})
    rows += [{**r, "task": "budgets"} for r in budget_requirements(ws, sysname)]
    for n, r in enumerate(rows, 1):
        r["swr"] = f"SWR-{n:03d}"
    opens, open_points = [], {}
    for group, rec in results + [(None, cross)]:
        for raw in rec["doc"]["open_points"]:
            text = raw.strip()
            if not text:
                continue
            ident = "OP-" + sha256_bytes((rec["task"] + "\0" + text).encode())[:16]
            origin = {"task": rec["task"], "text": text, "text_sha256": sha256_bytes(text.encode()),
                      "packet_input_hash": rec.get("base_hash"), "record_sha256": sha256_bytes(canonical_json(rec))}
            # Reviewed provided requirements have a materialized record, not a model packet.
            if m.get("provided_requirements"):
                origin["provided_input_sha256"] = m["provided_requirements"]["sha256"]
            if group is not None:
                origin.update(register=group["register"], source_section=group["section"], source_file=group["file"])
                scope = f"{group['register']}; source section {group['section']}"
            else:
                scope = "cross-cutting requirements"
            if ident in open_points:
                if open_points[ident] != origin:
                    raise ValueError("OPEN_POINT_ID_COLLISION")
                continue
            open_points[ident] = origin
            opens.append(f"**{ident}** (input scope: {scope}): {text}")
    up = m.get("upstream", {}).get("status", "NOT_PROVIDED")
    opens += [f"Upstream inputs (HSI contract, safety allocation, budgets): {up}.",
              f"Safety allocation as stated in the manifest: {m['target'].get('safety_allocation', 'UNSPECIFIED')}.",
              *(["Safe state: no software safe state is allocated; the allocated safety safe state is outside this "
                 "ASPICE-only work order's owner scope (inspection-assessment-context)."]
                if R.safe_state_outside_scope(ws) else []),
              f"Target silicon revision: {m['target'].get('silicon_revision', 'UNSPECIFIED')}.",
              f"Flash, static RAM and stack limits: {m['budgets'].get('status', 'work-order budgets')}."]
    md = ["# Software requirements", "",
          f"Software requirements of the {sysname} for this work order. Scope: " + " ".join(m["scope"]), ""]
    for r in rows:
        md += [f"- **{r['swr']}** {r['statement'].strip()}", f"  - Source: {r['source']}",
               f"  - Verification: {r['verification'].strip()}"] + OO.render_lines(r.get("obligations") or [])
    md += ["", "## Open points", ""] + [f"- {o}" for o in opens]
    obl_gaps = cross["doc"].get("obligation_gaps") or []
    md += OO.render_gaps(obl_gaps) + [""]
    effects, seen = [], set()
    for r in rows:
        for e in r["effects"]:
            case = e["case"]
            k = 2
            while case in seen:
                case = f"{e['case']}_{k}"
                k += 1
            seen.add(case)
            item = {"case": case, "swr": r["swr"], "register": e["register"], "field": e["field"], "op": e["op"]}
            if e["op"] == "write":
                item["value"] = e["value"]
                if e.get("requested"):  # CAPA-120: the input of a truncating write
                    item["requested"] = e["requested"]
            effects.append(item)
    csv, ut = ["requirement_id,test_id,test_file"], 0
    for r in rows:
        if r["verified_by"] == "host_unit_test":
            ut += 1
            csv.append(f"{r['swr']},UT-{ut:03d},software/tests/unit/test_{pid}.c")
        else:
            csv.append(f"{r['swr']},{r['swr']},software/tests/software/test_{pid}_requirements.robot")
    by_up: dict[str, list[str]] = {}
    for r in rows:
        by_up.setdefault(r["upstream"], []).append(r["swr"])
    t = m["target"]
    budget_origins = ("WO-BUDGET", "WO-SIMULATION-PERFORMANCE")
    reg_swr = [r["swr"] for r in rows if r["upstream"] not in budget_origins]
    bud_swr = [r["swr"] for r in rows if r["upstream"] in budget_origins]
    gaps = ["# Upstream coverage", "", "| Input | Status as stated in the manifest | Affected SWR IDs |",
            "| --- | --- | --- |",
            f"| HSI contract | {t.get('hsi_contract', 'NOT_PROVIDED')}; upstream.status: {up} | {', '.join(reg_swr)} |",
            f"| Safety allocation | {t.get('safety_allocation', 'NOT_PROVIDED')} | "
            f"{rows[0]['swr']} through {rows[-1]['swr']}: no software safety requirement is allocated |",
            f"| Budgets | {m['budgets'].get('status', '')}; flash_bytes: {m['budgets']['flash_bytes']}; static_ram_bytes: "
            f"{m['budgets']['static_ram_bytes']}; stack_bytes: {m['budgets']['stack_bytes']}; upstream.status: {up} | "
            f"{', '.join(bud_swr)} |", "",
            "No allocation is invented: missing approved upstream inputs remain open gaps.", "",
            "## Upstream to software requirements", "", "| Upstream ID | SWR IDs |", "| --- | --- |"]
    gaps += [f"| {u} | {', '.join(s)} |" for u, s in by_up.items()]
    gaps += ["", "## Software requirements to upstream", "", "| SWR ID | Upstream ID |", "| --- | --- |"]
    gaps += [f"| {r['swr']} | {r['upstream']} |" for r in rows] + [""]
    files = {REQS: "\n".join(md), EFFECTS: json.dumps({"schema": "forge-c/register-effects/1", "effects": effects},
                                                      indent=2) + "\n",
             CSV: "\n".join(csv) + "\n", GAPS: "\n".join(gaps)}
    obl = owner_obligations(ws)
    if obl is not None:
        files[OO.CSV] = OO.trace_csv(rows, obl_gaps)
    st = safety_text(ws)
    if st is not None:
        files[SAFETY] = st
    write_scoped(ws, files)
    amap = {"schema": "forge-c/lrtx-swe1-assembly/1", "at": utc_now(),
            "swr": {r["swr"]: {"task": r["task"], "key": r["key"]} for r in rows},
            "case": {e["case"]: e["swr"] for e in effects}, "files": sorted(files), "open_points": open_points,
            "owner_obligations": OO.status(ws)}
    S.record(ws, "SWE.1/assembly.json", amap)
    return amap


# ---- consistency and self-checks ------------------------------------------------------------------------------------
def consistency(results: list[tuple[dict, dict]], cross: dict) -> list[tuple[str, str]]:
    """LRTX-FR-010 global check across tasks: duplicate statements, contradictory effects on one field. Returns
    (task, finding) so the finding is repaired where it belongs: a requirement duplicated in a register task and the
    cross-cutting task is removed from the register task; between two register tasks, from the later one."""
    out, seen, ops, writes = [], {}, {}, {}
    for rec in [cross] + [rec for _g, rec in results]:  # the cross-cutting task owns shared requirements
        for r in rec["doc"]["requirements"]:
            norm = re.sub(r"\W+", " ", r["statement"].lower()).strip()
            if norm in seen:
                first_task, first_key = seen[norm]
                out.append((rec["task"], f"[{r['key']}] duplicates [{first_key}] of {first_task}: remove it here"))
            else:
                seen[norm] = (rec["task"], r["key"])
            for e in r["effects"]:
                ops.setdefault((e["case"], e["register"], e["field"]), []).append((rec["task"], e["op"]))
                if e["op"] == "write" and _value(e["value"]) is not None:  # lrtx9: same write, other words
                    w = (e["register"], e["field"], _value(e["value"]))
                    if w in writes and writes[w][1] != r["key"]:
                        first_task, first_key = writes[w]
                        if first_task == cross["task"]:  # a field write belongs to its register task
                            out.append((first_task, f"[{first_key}] duplicates [{r['key']}] of {rec['task']}: both "
                                                    f"write {e['value']} to {e['register']}.{e['field']} - remove it "
                                                    "here"))
                        else:
                            out.append((rec["task"], f"[{r['key']}] duplicates [{first_key}] of {first_task}: both "
                                                     f"write {e['value']} to {e['register']}.{e['field']} - remove "
                                                     "it here"))
                    writes.setdefault(w, (rec["task"], r["key"]))
    for (c, reg, f), lst in ops.items():
        if {"set", "clear"} <= {o for _t, o in lst}:
            out.append((lst[-1][0], f"case {c} has contradictory ops set and clear on {reg}.{f}"))
    return out


def self_check(ws: Path) -> list[str]:
    """The deterministic SWE.1 checks the author gate will apply, run before replying (no new criteria)."""
    from ..assurance import register_contract as RC
    from ..assurance.scope import workspace_scope_findings
    from ..inspection.ears import check_document
    from ..inspection.test_mapping import startup_on_host

    ws = Path(ws)
    names = set(json.loads((ws / "configuration/system_names.json").read_text()))
    ears = check_document((ws / REQS).read_text(), names)
    out = [f for f in ears.get("findings", []) if not f.split(":", 1)[-1].startswith("EARS_SYSTEM_NAME_HINT")]
    out += RC.check_effects(ws, "LL")
    out += startup_on_host(ws)
    out += workspace_scope_findings(ws, "SWE.1")
    out += obligation_findings(ws)
    return out


def obligation_findings(ws: Path) -> list[str]:
    """The owner-obligation coverage findings, each naming the task that repairs it: an uncovered obligation with
    register effects goes to that register's task, any other uncovered obligation to the cross-cutting task."""
    from ..assurance import owner_obligations as OO

    found = OO.coverage_findings(ws)
    if not found:
        return []
    try:
        obl = owner_obligations(ws)
        by_field = {(g["register"], f): f"requirements:{g['id']}" for g in groups(inventory(ws)) for f in g["fields"]}
    except Exception:  # an invalid declaration is already a finding; inventory refusals fail the visit elsewhere
        return found
    effects = {o["id"]: {(e["register"], e["field"]) for e in o.get("effects") or []}
               for o in (obl or {}).get("obligations", [])}
    out = []
    for f in found:
        m = re.match(r"SWE1_OBLIGATION_(?:UNCOVERED|CRITICAL_GAP):(OBL-[a-z0-9-]+)", f)
        tasks = sorted({by_field[k] for k in effects.get(m.group(1), set()) if k in by_field}) if m else []
        out.append(f + "".join(f" (task {t})" for t in tasks))
    return out


# ---- rework inputs -----------------------------------------------------------------------------------------------------


# ---- phase bindings of the shared visit machinery --------------------------------------------------------------------
def _ckpt(ws: Path, task: str) -> Path:
    return V._ckpt(ws, "SWE.1", task)


def run_task(ws: Path, task: str, build, check, budget: dict, findings: list[str] | None = None,
             max_repairs: int = 2) -> dict:
    return V.run_task(ws, "SWE.1", task, build, check, budget, findings, max_repairs)


def write_scoped(ws: Path, files: dict[str, str], node: str = "swe1_author") -> None:
    V.write_scoped(ws, files, node)


def rework_findings(ws: Path, since: str) -> list[str]:
    return V.rework_findings(ws, "SWE.1", since)


def task_index(obligations: list[dict]) -> dict[str, dict]:
    """Register task -> what it covers (register, RM section, fields): the names a finding is attributed by."""
    return {f"requirements:{g['id']}": {"register": g["register"], "section": g["section"], "fields": list(g["fields"])}
            for g in obligations}


def route_findings(findings: list[str], amap: dict | None, tasks: dict[str, dict] | None = None,
                   ws: Path | None = None) -> dict[str, list[str]]:
    """CAPA-108: each finding goes to the tasks it names; with `ws` the attribution is recorded (rework-routing.json),
    including every finding that named no author task and kept the earlier fan-out."""
    routed, report = V.attribute_findings(findings, amap, "requirements:crosscutting", tasks)
    if ws is not None:
        S.record(ws, "SWE.1/rework-routing.json", {"schema": "forge-c/lrtx-rework-routing/1", "at": utc_now(),
                                                   "assembly_at": (amap or {}).get("at"), "findings": report,
                                                   "tasks": sorted(routed),
                                                   "unattributed": sum(r["unattributed"] for r in report)})
    return routed


def reply(ws: Path, status: str, issues: list[str], budget: dict | None = None, artifacts: list[str] | None = None) -> dict:
    return V.reply(ws, "SWE.1", status, issues, budget, artifacts)


# ---- the author visit (one Fabro node execution) ----------------------------------------------------------------------
def visit(ws: Path, model: str, max_calls: int | None = None, resume: bool = False,
          time_budget_s: float | None = None) -> dict:
    """One author visit (or its continuation after a time box, `resume`)."""
    from ..layer import layer_of
    from ..registry.agents import load_agents

    ws = Path(ws)
    if layer_of(ws) != "LL":
        return reply(ws, "FAILED", ["LRTX_SWE1_LAYER_NOT_SUPPORTED_YET (structured SWE.1 covers LL work orders; HAL "
                                    "uses the agent author)"])
    role = {a.id: a for a in load_agents()[0]}["swe1-author"]
    since = V.last_finished(ws, "SWE.1")
    amap_p = ws / ".forge-run/lrtx/SWE.1/assembly.json"
    amap = json.loads(amap_p.read_text()) if amap_p.is_file() else None
    budget, findings = V.open_visit(ws, "SWE.1", resume, lambda: rework_findings(ws, since) if since else [],
                                    V.author_call_limit(ws, "SWE.1", role.max_turns, max_calls), time_budget_s)
    routed = {}
    if findings:  # CAPA-108: attributed with this inventory's register tasks, so only the named tasks re-author
        from .obligations import CoherentScopeRefused

        try:
            tasks = task_index(groups(inventory(ws)))
        except CoherentScopeRefused:
            tasks = None  # the visit itself reports the refused scope
        routed = route_findings(findings, amap, tasks, ws)
        V.attach_keep_fixed(ws, "SWE.1", budget,
                            lambda fs: V.attribute_findings(fs, amap, "requirements:crosscutting", tasks)[0])
    try:
        return _visit(ws, model, budget, routed)
    except V.Continue as c:
        return reply(ws, "CONTINUE", [f"time box used; the next node execution resumes at {c}"], budget)


def _repair_rounds(ws: Path, model: str, results: list[tuple[dict, dict]], budget: dict, sysname: str, idx: dict,
                   rounds: int = 2) -> list[tuple[dict, dict]]:
    """lrtx3 (2026-10-21): a task still INVALID after its repairs gets further repair rounds in the SAME visit - while
    the shared call budget lasts and the total number of findings keeps falling - instead of ending the visit."""
    for _ in range(rounds):
        bad = [(g, r) for g, r in results if r["status"] != "VALID" and r.get("doc") is not None]
        before = sum(len(r["errors"]) for _g, r in bad)
        if not bad or budget["calls"] >= budget["max_calls"]:
            break
        fixed = {}
        for g, r in bad:
            fixed[g["id"]] = run_task(ws, r["task"], lambda fi, pr, g=g: group_packet(ws, g, model, fi, pr),
                                      lambda d, g=g: validate_group(ws, d, g, sysname, idx), budget,
                                      [e for e in r["errors"] if e != "VISIT_CALL_BUDGET_EXHAUSTED"] or None)
        results = [(g, fixed.get(g["id"], r)) for g, r in results]
        after = sum(len(r["errors"]) for g, r in results if g["id"] in fixed and r["status"] != "VALID")
        if after >= before:
            break
    return results


def _visit(ws: Path, model: str, budget: dict, routed: dict[str, list[str]]) -> dict:
    from ..assurance.hardware import index
    from .obligations import CoherentScopeRefused

    try:
        inv = inventory(ws)
    except CoherentScopeRefused as exc:
        return reply(ws, "FAILED", ["CAPABILITY_LIMIT:" + str(exc)], budget)
    S.record(ws, "SWE.1/inventory.json", inv)
    if inv["missing_sections"]:
        return reply(ws, "FAILED", [f"LRTX_INVENTORY_SECTION_MISSING:{x}" for x in inv["missing_sections"]], budget)
    try:
        obligations = groups(inv)
    except CoherentScopeRefused as exc:
        return reply(ws, "FAILED", ["CAPABILITY_LIMIT:" + str(exc)], budget)
    idx = index(ws / "inputs/sections/RM0486")
    sysname = system_name(ws)
    tasks = task_index(obligations)
    results = []

    def cross_check(d: dict) -> list[str]:
        return validate_group(ws, d, None, sysname, idx) + crosscut_obligation_findings(
            ws, d, [r for _g, rec in results if rec["doc"] for r in rec["doc"]["requirements"]])
    for g in obligations:
        task = f"requirements:{g['id']}"
        rec = run_task(ws, task, lambda fi, pr, g=g: group_packet(ws, g, model, fi, pr),
                       lambda d, g=g: validate_group(ws, d, g, sysname, idx), budget, routed.get(task))
        results.append((g, rec))
    results = _repair_rounds(ws, model, results, budget, sysname, idx)
    issues = [f"{rec['task']}: {e}" for _g, rec in results if rec["status"] != "VALID" for e in rec["errors"][:5]]
    functional = [r for _g, rec in results if rec["doc"] for r in rec["doc"]["requirements"]]
    cross = run_task(ws, "requirements:crosscutting", lambda fi, pr: crosscut_packet(ws, functional, model, fi, pr),
                     cross_check, budget, routed.get("requirements:crosscutting"))
    if cross["status"] != "VALID":
        issues += [f"requirements:crosscutting: {e}" for e in cross["errors"][:5]]
    if safety_text(ws) is None:
        issues.append("LRTX_SWE1_ALLOCATED_SAFETY_REQUIREMENTS_NOT_SUPPORTED (an approved software safety allocation "
                      "needs the upstream SSR task)")
    if issues:  # missing semantic content stays missing: nothing partial is assembled or frozen
        return reply(ws, "FAILED", issues, budget)
    found = consistency(results, cross)
    if found and budget["calls"] < budget["max_calls"]:  # repair the offending tasks in this visit, then re-check
        per: dict[str, list[str]] = {}
        for task, f in found:
            per.setdefault(task, []).append(f)
        for task, fs in per.items():
            g = next((g for g, _r in results if f"requirements:{g['id']}" == task), None)
            if g is not None:
                rec = run_task(ws, task, lambda fi, pr, g=g: group_packet(ws, g, model, fi, pr),
                               lambda d, g=g: validate_group(ws, d, g, sysname, idx), budget, fs)
                results = [(gg, rec if gg is g else rr) for gg, rr in results]
            else:
                cross = run_task(ws, task, lambda fi, pr: crosscut_packet(ws, functional, model, fi, pr),
                                 cross_check, budget, fs)
        bad = [rec for _g, rec in results + [(None, cross)] if rec["status"] != "VALID"]
        if bad:
            return reply(ws, "FAILED", [f"{r['task']}: {e}" for r in bad for e in r["errors"][:5]], budget)
        found = consistency(results, cross)
    if found:
        return reply(ws, "FAILED", [f"{t}: {f}" for t, f in found], budget)
    amap = assemble(ws, inv, results, cross)
    checks = self_check(ws)
    if checks and budget["calls"] < budget["max_calls"]:  # one localized repair round on the gate's own findings
        for task, fs in route_findings(checks, amap, tasks).items():
            g = next((g for g, _r in results if f"requirements:{g['id']}" == task), None)
            if g is not None:
                rec = run_task(ws, task, lambda fi, pr, g=g: group_packet(ws, g, model, fi, pr),
                               lambda d, g=g: validate_group(ws, d, g, sysname, idx), budget, fs)
                results = [(gg, rec if gg is g else rr) for gg, rr in results]
            else:
                cross = run_task(ws, "requirements:crosscutting",
                                 lambda fi, pr: crosscut_packet(ws, functional, model, fi, pr),
                                 cross_check, budget, fs)
        bad = [rec for _g, rec in results + [(None, cross)] if rec["status"] != "VALID"]
        if bad:
            return reply(ws, "FAILED", [f"{r['task']}: {e}" for r in bad for e in r["errors"][:5]], budget)
        amap = assemble(ws, inv, results, cross)
        checks = self_check(ws)
    if checks:
        return reply(ws, "FAILED", checks[:20], budget)
    return reply(ws, "PASS", [], budget, artifacts=amap["files"])


