"""F011-T021..T023: semantic-first SWE.1 author of the local-rtx-v2 profile (ADR-0015).

The register tasks change and nothing else does. Per register group the local model chooses, inside a JSON schema
whose enums are the group's own fields and source facts:
- finite intents (field, action, logical value, cited facts);
- a short lowercase request phrase;
- the not-covered reasons and open points.
It never writes a statement, a mask, a bit position or a page.

The pinned SafeC engine (`validate_intents`) checks the intents against the register-io domain extracted from the
work order's RM sections. Its named findings are the repair feedback. Forge-C then renders each requirement
deterministically from the accepted operation:
- the EARS statement, its verification and the register effect;
- the source page of the cited fact.

The cross-cutting task (reset/startup, failure handling, all-function rules), the consistency check, the assembly
into the existing SWE.1 work products and the self-check are the unchanged feature 010 code. So are the gates that
judge them.

Before assembly, all intents are validated together. That catches duplicates and conflicts across groups, and the
contract is materialized only if Forge-C's own derivation of every number agrees. An answer identical to one already
rejected stops its task as STUCK instead of spending more calls (T023).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import sha256_bytes, utc_now
from ..safec_bridge import client as CL
from ..safec_bridge import contract as K
from ..safec_bridge import contracts as C
from ..safec_bridge import domain as D
from . import structured as S
from . import swe1 as V1
from . import visit as V

ACTIONS = ["read_field", "set_field", "clear_field", "write_field", "write_key_sequence"]
REQUEST_RX = r"^[a-z][a-z ]{3,60}[a-z]$"
WEAK = re.compile(r"\b(should|may|will|must|can|could|might|fast|quickly|as required|appropriate|etc)\b")


class Stuck(Exception):  # noqa: N818 - control flow: an identical answer was already rejected
    def __init__(self, task: str, errors: list[str]):
        super().__init__(task)
        self.task = task
        self.errors = errors


class EngineFault(RuntimeError):
    """The engine could not judge (ERROR/STALE, refused, timeout): infrastructure, never the model's answer."""


# ---- context of one visit ------------------------------------------------------------------------------------------
class Context:
    def __init__(self, ws: Path):
        from .profile import load

        self.ws = Path(ws)
        m = V1._manifest(ws)
        prof = load((m.get("local_profile") or {}).get("id", "local-rtx-v2"))
        e = prof["safec"]["engine"]
        self.pin = CL.EnginePin(Path(e["binary"]), e["binary_sha256"], e["source_commit_sha"], e["semantic_profile"])
        self.limits = CL.Limits(timeout_s=float(prof["safec"].get("timeout_s", 60)))
        self.domain, self.domain_raw = D.build(ws)
        S.record(ws, "SWE.1/domain.json", self.domain)
        man = (self.ws / ".forge-run/manifest.json").read_bytes()
        self.binding = {"workorder_id": str(m.get("work_order") or self.ws.parent.name)[:128],
                        "workorder_sha256": sha256_bytes(man),
                        "source_manifest_sha256": sha256_bytes(self.domain_raw),
                        "policy_sha256": prof["_sha256"]}
        self.facts = _facts(self.domain)
        self.rejected: dict[str, set[str]] = {}
        self.calls = 0

    def validate(self, intents: list[dict], tag: str) -> tuple[CL.Outcome, dict, Path]:
        self.calls += 1
        req, raw = C.build_request(request_id=f"{tag}-{self.calls}"[:128], operation="validate_intents",
                                   engine=self.pin.expected(), binding=self.binding, intents=intents)
        work = self.ws / ".forge-run/safec" / f"{utc_now().replace(':', '')}-{self.calls:04d}-{tag.replace(':', '_')}"
        work.parent.mkdir(parents=True, exist_ok=True)
        out = CL.invoke(self.pin, req, raw, work, self.limits, domain=self.domain_raw)
        if out.status in ("ERROR", "STALE") or out.refused:
            checks = [f["check_id"] for f in (out.result or {}).get("findings", [])[:5]]
            raise EngineFault(f"SAFEC_{out.status}: {', '.join(out.issues[:5] + checks) or 'no detail'}")
        return out, req, work


def _facts(domain: dict) -> dict[str, dict]:
    """fact id -> {register, field, pages, value?} for every field and documented value fact."""
    out = {}
    for r in domain["registers"]:
        for f in r["fields"]:
            out[f["fact_id"]] = {"register": r["register_id"], "field": f["field_id"], "pages": r["pages"],
                                 "section": r["section"]}
            for v in f["values"]:
                out[v["fact_id"]] = {"register": r["register_id"], "field": f["field_id"], "pages": v["pages"],
                                     "value": v["value"], "label": v["label"], "section": v["source_id"]}
    return out


# ---- packet ---------------------------------------------------------------------------------------------------------
def group_schema(g: dict, ctx: Context) -> dict:
    fields = [f"{g['register']}.{f}" for f in g["fields"]]
    facts = sorted(k for k, v in ctx.facts.items() if v["register"] == g["register"] and v["field"] in g["fields"])
    intent = {"type": "object", "additionalProperties": False,
              "required": ["key", "request", "field", "action", "source_fact_ids"],
              "properties": {"key": {"type": "string", "pattern": "^[a-z][a-z0-9_]{2,40}$"},
                             "request": {"type": "string", "pattern": REQUEST_RX},
                             "field": {"type": "string", "enum": fields},
                             "action": {"type": "string", "enum": ACTIONS},
                             "logical_value": {"type": "string", "pattern": "^(0|[1-9][0-9]{0,9}|0x[0-9A-Fa-f]{1,8})$"},
                             "source_fact_ids": {"type": "array", "minItems": 1, "maxItems": 3,
                                                 "items": {"type": "string", "enum": facts}}}}
    return {"type": "object", "additionalProperties": False, "required": ["intents", "not_covered", "open_points"],
            "properties": {"intents": {"type": "array", "items": intent},
                           "not_covered": V1.GROUP_SCHEMA["properties"]["not_covered"],
                           "open_points": {"type": "array", "items": {"type": "string"}}}}


def group_packet(ws: Path, g: dict, model: str, ctx: Context, findings: list[str] | None = None,
                 previous: dict | None = None) -> dict:
    m = V1._manifest(ws)
    sysname = V1.system_name(ws)
    hints = V1.scope_hints(ws, g)
    lines = []
    for f, v in g["fields"].items():
        dom = next(x for r in ctx.domain["registers"] if r["register_id"] == g["register"] for x in r["fields"]
                   if x["field_id"] == f)
        vals = "; ".join(f"{x['fact_id']} = {x['value']} ({x['label']})" for x in dom["values"])
        lines.append(f"- {g['register']}.{f}: bits {v['msb']}:{v['lsb']} ({v['msb'] - v['lsb'] + 1} bits), access "
                     f"{'/'.join(dom['access_tokens'])}, fact {dom['fact_id']}, RM: '{dom['label']}'"
                     + (f", documented values: {vals}" if vals else "") + f"; {hints[f]}")
    instr = (f"Choose the register intents of the {sysname} for register {g['register']} (RM0486 section "
             f"{g['section']}). Fields of this task:\n" + "\n".join(lines) + "\nWork-order scope: "
             + " | ".join(m["scope"]) + f". Coverage rules: {V1.coverage_guidance(ws)} Apply them ONLY to the fields "
             "of this task. You do NOT write requirement text: each intent is one driver behaviour, and the factory "
             "renders the requirement, its verification and its register effect from the validated intent. "
             "Actions: read_field (the driver reads and returns the field, e.g. a status flag query), set_field / "
             "clear_field (1-bit fields only), write_field (the field takes a logical value from the caller; give a "
             "representative logical_value for the test, e.g. 5), write_key_sequence (write one documented value; "
             "logical_value is that value and source_fact_ids MUST include its value fact). logical_value is always "
             "the FIELD value, never a register mask or a shifted value: for a 1-bit field the only values are 0 "
             "and 1; the engine computes masks and bit positions. source_fact_ids cite the field fact or the "
             "documented value fact the intent relies on. request is the caller's request in lowercase words only "
             "(e.g. 'start the watchdog', 'query the reload update flag'), no numbers, no register names, no "
             "should/may/must/can. key is a short snake_case name. For every field of this task either write the "
             "intents the scope demands or list it in not_covered with the scope reason. open_points lists "
             "ambiguities of the source (or nothing).")
    crit = ["every intent names a field of this task", "every field of the task has an intent or is in not_covered",
            "logical values are field values within the field width", "key writes cite their own value fact"]
    return S.packet(phase="SWE.1", task=f"requirements:{g['id']}", role="swe1-author", instructions=instr,
                    sources=[S.source(ws, g["file"])], criteria=crit, output_schema=group_schema(g, ctx),
                    model=model, findings=findings, previous=previous)


# ---- rendering ------------------------------------------------------------------------------------------------------
def to_intent(it: dict) -> dict:
    reg, fld = it["field"].split(".", 1)
    out = {"intent_id": it["key"], "source_fact_ids": list(it["source_fact_ids"]), "register": reg, "field": fld,
           "action": it["action"]}
    if it.get("logical_value") not in (None, ""):
        out["logical_value"] = it["logical_value"]
    return out


def render(it: dict, op: dict, ctx: Context, sysname: str) -> dict:
    """The requirement (feature 010 shape) of one accepted operation: every number comes from the operation."""
    reg, fld = op["register"], op["field"]
    when = f"When the caller requests to {it['request']}"
    page = min(min(ctx.facts[f]["pages"]) for f in op["source_fact_ids"] if f in ctx.facts)
    case = re.sub(r"[^A-Z0-9_]", "_", it["key"].upper())[:47]
    if not re.match(r"^[A-Z]", case):
        case = f"C_{case}"[:47]
    if op["action"] == "read_field":
        if op["width"] == 1:
            st = f"{when}, the {sysname} shall return 1 if {reg}.{fld} is set and 0 if {reg}.{fld} is clear."
            ver = (f"Host unit test sets and then clears {reg}.{fld} in the register array and performs the request; "
                   "passes when the returned value is 1 and then 0 and no register is written.")
        else:
            st = f"{when}, the {sysname} shall return the value of {reg}.{fld}."
            ver = (f"Host unit test writes a value to {reg}.{fld} in the register array and performs the request; "
                   "passes when the returned value equals that field value and no register is written.")
        return {"key": it["key"], "statement": st, "source_page": page, "verification": ver,
                "verified_by": "host_unit_test", "effects": [{"case": case, "register": reg, "field": fld,
                                                              "op": "no_write", "value": ""}]}
    v = int(op["logical_value"])
    if op["action"] == "write_key_sequence":
        st = f"{when}, the {sysname} shall write the key value 0x{v:04X} to {reg}.{fld}."
    elif op["action"] == "write_field":
        st = (f"{when} with a value from 0 to {(1 << op['width']) - 1}, the {sysname} shall write that value to "
              f"{reg}.{fld}.")
    else:
        st = f"{when}, the {sysname} shall {'set' if v else 'clear'} {reg}.{fld}."
    if op["write_kind"] == "full_register_write":
        ver = (f"Host unit test performs the request on the register array; passes when {reg} equals "
               f"{op['encoded_value']}.")
    else:
        ver = (f"Host unit test performs the request on the register array; passes when the bits {op['field_mask']} "
               f"of {reg} equal {op['encoded_value']} and the bits {op['preserved_mask']} keep their previous value.")
    effect = {"case": case, "register": reg, "field": fld,
              "op": {"set_field": "set", "clear_field": "clear"}.get(op["action"], "write"),
              "value": f"0x{v:X}" if op["action"] in ("write_field", "write_key_sequence") else ""}
    return {"key": it["key"], "statement": st, "source_page": page, "verification": ver,
            "verified_by": "host_unit_test", "effects": [effect]}


def rendered(doc: dict, contract_ops: dict[str, dict], ctx: Context, sysname: str) -> dict:
    """A semantic answer as a feature 010 requirements document (the shape assemble/consistency read)."""
    return {"requirements": [render(it, contract_ops[it["key"]], ctx, sysname) for it in doc["intents"]],
            "not_covered": doc["not_covered"], "open_points": doc["open_points"]}


# ---- deterministic checks of one answer ------------------------------------------------------------------------------
def local_checks(ws: Path, doc: dict, g: dict) -> list[str]:
    out, keys = [], set()
    excl = V1.out_of_scope_named(ws)
    for it in doc["intents"]:
        if it["key"] in keys:
            out.append(f"[{it['key']}] duplicate key")
        keys.add(it["key"])
        if WEAK.search(it["request"]):
            out.append(f"[{it['key']}] request '{it['request']}' uses a weak or vague word: name the request plainly")
        if it["field"] in excl or it["field"].split(".")[0] in excl:
            out.append(f"[{it['key']}] acts on {it['field']}, which the work-order scope lists as out of scope: list "
                       "it in not_covered")
    covered = {it["field"] for it in doc["intents"]}
    excluded = {x["field"] if "." in x["field"] else f"{g['register']}.{x['field']}" for x in doc["not_covered"]}
    for f in g["fields"]:
        full = f"{g['register']}.{f}"
        if full not in covered and full not in excluded:
            out.append(f"field {full} has no intent and is not listed in not_covered")
        if full in covered and full in excluded:
            out.append(f"field {full} has intents and is also listed in not_covered")
    out += [f"not_covered {x['field']} is not a field of this task" for x in doc["not_covered"]
            if x["field"].split(".")[-1] not in g["fields"]]
    return out


def findings_text(out: CL.Outcome) -> list[str]:
    res = []
    for f in out.result["findings"]:
        s = f"[{f['target_id']}] {f['check_id']}: {f['message']}"
        if f.get("expected"):
            s += f" (expected {f['expected']})"
        if f.get("suggested_repair"):
            s += f" Repair: {f['suggested_repair']}"
        res.append(s)
    return res


def check_group(ws: Path, doc: dict, g: dict, ctx: Context, sysname: str) -> list[str]:
    from ..inspection.ears import Requirement, check_statement

    task = f"requirements:{g['id']}"
    errs = local_checks(ws, doc, g)
    if not errs and doc["intents"]:
        out, _req, _w = ctx.validate([to_intent(it) for it in doc["intents"]], task)
        if out.status != "PASS" or not out.admissible:
            errs = findings_text(out) or [f"SAFEC_{out.status}"]
        else:
            ops = _ops_of(out, _w)
            for r in rendered(doc, ops, ctx, sysname)["requirements"]:
                for f in check_statement(Requirement(r["key"], r["statement"], 0), {sysname}).findings:
                    code = f.split(":", 1)[1] if ":" in f else f
                    if not code.startswith("EARS_SYSTEM_NAME_HINT"):
                        errs.append(f"[{r['key']}] rendered statement {code}: change the request phrase")
    if errs:
        h = sha256_bytes(C.canonical_bytes(doc))
        seen = ctx.rejected.setdefault(task, set())
        if h in seen:  # T023: the same rejected answer again - stop this task instead of spending more calls
            raise Stuck(task, ["STUCK: the same intents were already rejected"] + errs[:8])
        seen.add(h)
    return errs


def _ops_of(out: CL.Outcome, work: Path) -> dict[str, dict]:
    art = next(a for a in out.result["output_artifacts"] if a["kind"] == "validated_contract")
    doc = json.loads((work / "evidence/artifacts" / art["artifact_id"]).read_bytes())
    return {o["intent_id"]: o for o in doc["operations"]}


# ---- the visit ------------------------------------------------------------------------------------------------------
def visit(ws: Path, model: str, max_calls: int | None = None, resume: bool = False,
          time_budget_s: float | None = None) -> dict:
    from ..layer import layer_of
    from ..registry.agents import load_agents

    ws = Path(ws)
    if layer_of(ws) != "LL":
        return V1.reply(ws, "FAILED", ["LRTX_SWE1_LAYER_NOT_SUPPORTED_YET (semantic SWE.1 covers LL work orders)"])
    role = {a.id: a for a in load_agents()[0]}["swe1-author"]
    since = V.last_finished(ws, "SWE.1")
    amap_p = ws / ".forge-run/lrtx/SWE.1/assembly.json"
    amap = json.loads(amap_p.read_text()) if amap_p.is_file() else None
    budget, findings = V.open_visit(ws, "SWE.1", resume, lambda: V1.rework_findings(ws, since) if since else [],
                                    max_calls or role.max_turns, time_budget_s)
    try:
        return _visit(ws, model, budget, V1.route_findings(findings, amap) if findings else {})
    except V.Continue as c:
        return V1.reply(ws, "CONTINUE", [f"time box used; the next node execution resumes at {c}"], budget)
    except EngineFault as exc:
        return V1.reply(ws, "FAILED", [f"LRTX_SEMANTIC_ENGINE_FAULT: {exc}"], budget)


def _run_group(ws, g, model, ctx, sysname, budget, findings):
    task = f"requirements:{g['id']}"
    try:
        return V1.run_task(ws, task, lambda fi, pr, g=g: group_packet(ws, g, model, ctx, fi, pr),
                           lambda d, g=g: check_group(ws, d, g, ctx, sysname), budget, findings)
    except Stuck as s:
        return {"task": task, "status": "INVALID", "doc": None, "errors": s.errors, "stuck": True}


def _visit(ws: Path, model: str, budget: dict, routed: dict[str, list[str]]) -> dict:
    from ..assurance.hardware import index

    inv = V1.inventory(ws)
    S.record(ws, "SWE.1/inventory.json", inv)
    if inv["missing_sections"]:
        return V1.reply(ws, "FAILED", [f"LRTX_INVENTORY_SECTION_MISSING:{x}" for x in inv["missing_sections"]], budget)
    ctx = Context(ws)
    idx = index(ws / "inputs/sections/RM0486")
    sysname = V1.system_name(ws)
    sem = [(g, _run_group(ws, g, model, ctx, sysname, budget, routed.get(f"requirements:{g['id']}")))
           for g in V1.groups(inv)]
    issues = [f"{rec['task']}: {e}" for _g, rec in sem if rec["status"] != "VALID" for e in rec["errors"][:5]]
    if issues:
        return V1.reply(ws, "FAILED", issues, budget)
    # all intents together: duplicates and conflicts across groups, and the contract with both engines agreeing
    intents = [to_intent(it) for _g, rec in sem for it in rec["doc"]["intents"]]
    task_of = {it["key"]: rec["task"] for _g, rec in sem for it in rec["doc"]["intents"]}
    out, req, work = ctx.validate(intents, "swe1-all")
    if out.status != "PASS" or not out.admissible:
        per: dict[str, list[str]] = {}
        for f in findings_text(out):
            m = re.match(r"^\[([^\]]+)\]", f)
            for key in m.group(1).split(",") if m else []:
                per.setdefault(task_of.get(key, "requirements:crosscutting"), []).append(f)
        return V1.reply(ws, "FAILED", [f"{t}: {f}" for t, fs in per.items() for f in fs[:5]] or findings_text(out),
                        budget)
    try:
        vc = K.materialize(out, req, ctx.domain_raw, work, ctx.pin)
    except K.ContractRejected as exc:
        return V1.reply(ws, "FAILED", [f"LRTX_SEMANTIC_CONTRACT_REJECTED: {i}" for i in exc.issues[:10]], budget)
    ops = vc.by_intent()
    results = [(g, {**rec, "doc": rendered(rec["doc"], ops, ctx, sysname)}) for g, rec in sem]
    if results:  # the contract's unresolved obligations become open points of the requirements document
        first = results[0][1]
        first["doc"] = {**first["doc"], "open_points": list(dict.fromkeys(
            first["doc"]["open_points"] + [f"SafeC register-io: {o}" for o in vc.unresolved_obligations]))}
    functional = [r for _g, rec in results for r in rec["doc"]["requirements"]]
    cross = V1.run_task(ws, "requirements:crosscutting",
                        lambda fi, pr: V1.crosscut_packet(ws, functional, model, fi, pr),
                        lambda d: V1.validate_group(ws, d, None, sysname, idx), budget,
                        routed.get("requirements:crosscutting"))
    if cross["status"] != "VALID":
        return V1.reply(ws, "FAILED", [f"requirements:crosscutting: {e}" for e in cross["errors"][:5]], budget)
    if V1.safety_text(ws) is None:
        return V1.reply(ws, "FAILED", ["LRTX_SWE1_ALLOCATED_SAFETY_REQUIREMENTS_NOT_SUPPORTED (an approved software "
                                       "safety allocation needs the upstream SSR task)"], budget)
    found = V1.consistency(results, cross)
    if found:
        return V1.reply(ws, "FAILED", [f"{t}: {f}" for t, f in found], budget)
    amap = V1.assemble(ws, inv, results, cross)
    S.record(ws, "SWE.1/semantic.json", {"schema": "forge-c/lrtx-swe1-semantic/1", "at": utc_now(),
                                         "contract_semantic_digest": vc.semantic_digest,
                                         "domain_sha256": vc.domain_sha256, "engine": ctx.pin.expected(),
                                         "engine_calls": ctx.calls, "evidence": str(work.relative_to(ws))})
    checks = V1.self_check(ws)
    if checks:
        return V1.reply(ws, "FAILED", checks[:20], budget)
    return V1.reply(ws, "PASS", [], budget, artifacts=amap["files"])
