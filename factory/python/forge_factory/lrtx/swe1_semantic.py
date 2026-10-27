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

The cross-cutting requirements are a closed catalogue too: the reset/startup invariant is always rendered, and the
model chooses the further rules the scope demands (status queries without waiting, writes changing only the named
field). The consistency check, the assembly into the existing SWE.1 work products and the self-check are the
unchanged feature 010 code, and so are the gates that judge them.

Before assembly, all intents are validated together. That catches duplicates and conflicts across groups, and the
contract is materialized only if Forge-C's own derivation of every number agrees. An answer identical to one already
rejected stops its task as STUCK instead of spending more calls (T023).

F011-T034: when the pinned engine supports `derive_tests`, the frozen SWE.1 also carries the register-image test
oracle of that contract (workproducts/SWE.1/register_oracle.json), accepted only when Forge-C re-derives every case.
Later phases take expected register values from it, never from an implementation or a model.
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
from ..safec_bridge import obligations as OB
from ..safec_bridge import oracle as O
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
        self.manifest_raw = (self.ws / ".forge-run/manifest.json").read_bytes()
        m = json.loads(self.manifest_raw)
        local = m.get("local_profile") or {}
        if not isinstance(local, dict):
            raise EngineFault("PROFILE_BINDING_INVALID")
        prof = load(local.get("id", "local-rtx-v2"))
        e = prof["safec"]["engine"]
        if (e["semantic_profile"] == "register-io-0.2" or "semantic_profile" in local) and (
                local.get("id") != prof["id"]
                or local.get("semantic_profile") != e["semantic_profile"]
                or type(local.get("version")) is not int or local["version"] != prof["version"]
                or local.get("config") != prof["_path"]
                or local.get("config_sha256") != prof["_sha256"]):
            raise EngineFault("PROFILE_BINDING_CHANGED_OR_MISSING")
        self.pin = CL.EnginePin(Path(e["binary"]), e["binary_sha256"], e["source_commit_sha"], e["semantic_profile"])
        self.limits = CL.Limits(timeout_s=float(prof["safec"].get("timeout_s", 60)))
        self.domain, self.domain_raw = D.build(ws, semantic_profile=self.pin.semantic_profile)
        S.record(ws, "SWE.1/domain.json", self.domain)
        if self.pin.semantic_profile == "register-io-0.2" and (
                self.ws / ".forge-run/manifest.json").read_bytes() != self.manifest_raw:
            raise EngineFault("WORKORDER_BINDING_CHANGED")
        self.binding = {"workorder_id": str(m.get("work_order") or self.ws.parent.name)[:128],
                        "workorder_sha256": sha256_bytes(self.manifest_raw),
                        "source_manifest_sha256": sha256_bytes(self.domain_raw),
                        "policy_sha256": prof["_sha256"]}
        self.facts = _facts(self.domain)
        self.rejected: dict[str, set[str]] = {}
        self.calls = 0

    def validate(self, intents: list[dict], tag: str, operation: str = "validate_intents") -> \
            tuple[CL.Outcome, dict, Path]:
        if self.pin.semantic_profile == "register-io-0.2" and (
                self.ws / ".forge-run/manifest.json").read_bytes() != self.manifest_raw:
            raise EngineFault("WORKORDER_BINDING_CHANGED")
        self.calls += 1
        req, raw = C.build_request(request_id=f"{tag}-{self.calls}"[:128], operation=operation,
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


def preflight_required(ctx, required: list[dict], *, maximum_seconds: float = 60) -> dict:
    """Ask the actual pinned engine about frozen mandatory operations before inference.

    This is a scoped capability observation, not a substitute for the author's
    complete requirements or the later independent gates. No model is called.
    """
    import math
    import time
    from dataclasses import replace

    if (not isinstance(required, list) or not 1 <= len(required) <= 32
            or type(maximum_seconds) not in (float, int) or not math.isfinite(maximum_seconds)
            or not 0 < maximum_seconds <= 60):
        raise EngineFault("REQUIRED_OPERATION_CONFIGURATION_INVALID")
    started = time.monotonic()
    result = {"schema": "forge-c/required-operation-preflight/1", "engine": ctx.pin.expected(),
              "domain_sha256": sha256_bytes(ctx.domain_raw), "configuration_sha256": sha256_bytes(C.canonical_bytes(required)),
              "model_calls": 0, "operations": [], "status": "PASS_REQUIRED_FORMS_ONLY"}
    limits = ctx.limits
    try:
        for i, row in enumerate(required):
            remaining = maximum_seconds - (time.monotonic() - started)
            if remaining <= 0:
                result["status"] = "INCOMPLETE_PREFLIGHT_DEADLINE"
                break
            ctx.limits = replace(limits, timeout_s=min(limits.timeout_s, remaining),
                                 cpu_s=min(limits.cpu_s, max(1, math.ceil(remaining))))
            if (not isinstance(row, dict) or not {"register", "field", "action"} <= set(row)
                    or set(row) - {"register", "field", "action", "logical_value"}
                    or row["action"] not in ("read_field", "set_field", "clear_field", "write_field")):
                raise EngineFault("REQUIRED_OPERATION_CONFIGURATION_INVALID")
            matches = [f for r in ctx.domain["registers"] if r["register_id"] == row["register"]
                       for f in r["fields"] if f["field_id"] == row["field"]]
            if len(matches) != 1:
                raise EngineFault("REQUIRED_OPERATION_SOURCE_UNKNOWN")
            it = {**row, "intent_id": f"mandatory-{i}", "source_fact_ids": [matches[0]["fact_id"]]}
            outcome, _request, work = ctx.validate([it], f"mandatory-{i}")
            result["operations"].append({"index": i, "status": outcome.status,
                "admissible": outcome.admissible, "evidence": str(work.relative_to(ctx.ws)),
                "check_ids": [f["check_id"] for f in (outcome.result or {}).get("findings", [])]})
    except EngineFault as exc:
        result.update(status="ENGINE_FAULT", error=str(exc)[:500])
    finally:
        ctx.limits = limits
    result["elapsed_seconds"] = time.monotonic() - started
    result["expected_operations"] = len(required)
    if result["status"] == "PASS_REQUIRED_FORMS_ONLY":
        if any(row["status"] not in ("PASS", "UNSUPPORTED") or
               (row["status"] == "PASS" and row["admissible"] is not True) for row in result["operations"]):
            result["status"] = "REQUIRED_OPERATION_INVALID"
        elif any(row["status"] == "UNSUPPORTED" for row in result["operations"]):
            result["status"] = "CAPABILITY_LIMIT"
    return result


# ---- packet ---------------------------------------------------------------------------------------------------------
def group_schema(g: dict, ctx: Context) -> dict:
    fields = [f"{g['register']}.{f}" for f in g["fields"]]
    facts = sorted(k for k, v in ctx.facts.items() if v["register"] == g["register"] and v["field"] in g["fields"])
    from .swe2 import _ident

    fn = re.escape(_ident(ctx.ws)["fn"])
    intent = {"type": "object", "additionalProperties": False,
              "required": ["key", "function", "request", "field", "action", "source_fact_ids"],
              "properties": {"key": {"type": "string", "pattern": "^[a-z][a-z0-9_]{2,40}$"},
                             # F011-T031: the LL API function the requirement names; SWE.2 must define exactly it
                             "function": {"type": "string", "pattern": f"^{fn}[A-Z][A-Za-z0-9_]{{1,48}}$"},
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
             "representative logical_value for the test, e.g. 5), write_key_sequence (write one documented value: "
             "cite exactly that value's fact in source_fact_ids; logical_value may be omitted, the engine takes the "
             "key from the cited fact). logical_value is always "
             "the FIELD value, never a register mask or a shifted value: for a 1-bit field the only values are 0 "
             "and 1; the engine computes masks and bit positions. source_fact_ids cite the field fact or the "
             "documented value fact the intent relies on. request is the caller's request in lowercase words only "
             "(e.g. 'start the watchdog', 'query the reload update flag'), no numbers, no register names, no "
             "should/may/must/can. function is the LL API function that implements the intent, named with the "
             "driver's prefix (e.g. LL_IWDG_Enable, LL_IWDG_IsActiveFlag_PVU, LL_RCC_HSI_Enable); the later "
             "architecture must define exactly this name. key is a short snake_case name. For every field of this "
             "task either write the "
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
    when = f"When {it['function']} is called to {it['request']}"
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


# ---- the cross-cutting requirements: a closed catalogue, rendered -----------------------------------------------------
# M3 trial 2026-10-22 (RCC-LL n=1): every register task was valid at the first call, but the free-text cross-cutting
# task kept non-EARS statements ('it shall', 'The caller shall') through its repairs. Its content was right; only
# the wording failed. The model now chooses rules from this catalogue; the factory renders statement and verification.
CROSS_RULES = {
    "status_query_no_wait": {
        "when": "the work-order scope states that the caller bounds its polling (no waiting in the driver)",
        "statement": "When the caller queries a status flag, the {sys} shall return the value read from the status "
                     "register without waiting for the flag to change.",
        "verification": "Host unit test holds each status flag at its inactive value in the register array and "
                        "performs each status query once; passes when every query returns 0 after one read.",
        "verified_by": "host_unit_test"},
    "write_only_named_field": {
        "when": "the coverage rules require that every write changes only the named bits",
        # trial batch 2 (2026-10-22): 'When the {sys} sets, clears or writes ..., the {sys} shall ...' is not EARS-
        # conformant for the unchanged checker (the trigger's comma); the ubiquitous form is
        "statement": "The {sys} shall change only the bits of the named field when it sets, clears or writes a "
                     "register field.",
        "verification": "Host unit test fills the register array with 0xFFFFFFFF and then 0x00000000 and performs each "
                        "set, clear and write request; passes when only the bits of the named field change.",
        "verified_by": "host_unit_test"},
}
STARTUP_RULE = {
    "statement": "While no {layer} function has been called after reset, the {sys} shall not write any {pfx} register.",
    "verification": "Target test reads every {pfx} register after reset before any driver function is called; passes "
                    "when each register holds its RM0486 reset value.",
    "verified_by": "target_robot_test"}
CROSS_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["rules", "open_points"],
                "properties": {"rules": {"type": "array", "uniqueItems": True,
                                         "items": {"type": "string", "enum": sorted(CROSS_RULES)}},
                               "open_points": {"type": "array", "items": {"type": "string"}}}}


def crosscut_packet(ws: Path, functional: list[dict], model: str, findings: list[str] | None = None,
                    previous: dict | None = None) -> dict:
    m = V1._manifest(ws)
    sysname = V1.system_name(ws)
    listing = "\n".join(f"- [{r['key']}] {r['statement']}" for r in functional)
    cat = "\n".join(f"- {k}: applies when {v['when']}; renders: \"{v['statement'].format(sys=sysname)}\""
                     for k, v in sorted(CROSS_RULES.items()))
    instr = (f"The register-level requirements of the {sysname} are rendered (CURRENT ARTIFACT below). The reset/"
             "startup invariant is always added by the factory. Choose which further cross-cutting rules of this "
             "catalogue the work-order scope and coverage rules demand (choose none that does not apply):\n" + cat +
             "\nWork-order scope: " + " | ".join(m["scope"]) + f". Coverage rules: {V1.coverage_guidance(ws)} "
             "Do not write requirement text: the factory renders each chosen rule. open_points lists ambiguities of "
             "the source (or nothing).")
    art = {"path": "lrtx:functional_requirements", "text": listing, "sha256": sha256_bytes(listing.encode())}
    return S.packet(phase="SWE.1", task="requirements:crosscutting", role="swe1-author", instructions=instr,
                    sources=[], artifacts=[art], criteria=["only rules the scope or coverage rules demand"],
                    output_schema=CROSS_SCHEMA, model=model, findings=findings, previous=previous)


def crosscut_rendered(ws: Path, doc: dict, inv: dict, sysname: str) -> dict:
    from ..layer import layer_of, register_prefix

    pfx, layer = register_prefix(ws), layer_of(ws)
    page = min(inv["registers"][0]["pages"]) if inv["registers"] else 1
    reqs = [{"key": "startup_no_write", "source_page": page, "effects": [],
             **{k: v.format(sys=sysname, layer=layer, pfx=pfx) for k, v in STARTUP_RULE.items()}}]
    for k in doc["rules"]:
        r = CROSS_RULES[k]
        reqs.append({"key": k, "source_page": page, "effects": [], "statement": r["statement"].format(sys=sysname),
                     "verification": r["verification"], "verified_by": r["verified_by"]})
    return {"requirements": reqs, "not_covered": [], "open_points": doc["open_points"]}


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


def _joint(sem: list[tuple[dict, dict]]) -> list[dict]:
    """Every group's intents, each id qualified by its group (group:key)."""
    return [{**to_intent(it), "intent_id": f"{g['id']}:{it['key']}"} for g, rec in sem for it in rec["doc"]["intents"]]


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
    manifest = V1._manifest(ws)
    from ..layer import profile as peripheral_profile

    peripheral = peripheral_profile(ws)
    if "semantic_required_operations" in manifest or "semantic_required_operations" in peripheral:
        if (manifest.get("peripheral_profile_sha256") != peripheral["sha256"]
                or manifest.get("semantic_required_operations") != peripheral.get("semantic_required_operations")):
            raise EngineFault("REQUIRED_OPERATION_SCOPE_CHANGED")
        preflight = preflight_required(ctx, manifest["semantic_required_operations"])
        S.record(ws, "SWE.1/required-operation-preflight.json", preflight)
        if preflight["status"] != "PASS_REQUIRED_FORMS_ONLY":
            return V1.reply(ws, "FAILED", ["LRTX_SEMANTIC_" + preflight["status"] +
                            ": mandatory source-bound operation preflight; no model request made"], budget)
    idx = index(ws / "inputs/sections/RM0486")
    sysname = V1.system_name(ws)
    sem = [(g, _run_group(ws, g, model, ctx, sysname, budget, routed.get(f"requirements:{g['id']}")))
           for g in V1.groups(inv)]
    issues = [f"{rec['task']}: {e}" for _g, rec in sem if rec["status"] != "VALID" for e in rec["errors"][:5]]
    if issues:
        return V1.reply(ws, "FAILED", issues, budget)
    # all intents together: duplicates and conflicts across groups, and the contract with both engines agreeing.
    # Intent keys are unique within a group only (as requirement keys are per task): the joint id is group:key.
    for _ in range(2):
        out, req, work = ctx.validate(_joint(sem), "swe1-all")
        if out.status == "PASS" and out.admissible:
            break
        per: dict[str, list[str]] = {}
        for f in findings_text(out):
            m = re.match(r"^\[([^\]]+)\]", f)
            for jid in m.group(1).split(",") if m else []:
                gid, _, key = jid.partition(":")
                per.setdefault(f"requirements:{gid}", []).append(f.replace(jid, key, 1) if key else f)
        if not per or budget["calls"] >= budget["max_calls"]:
            return V1.reply(ws, "FAILED", findings_text(out)[:20], budget)
        # T023: localized repair of the groups the joint check names, then the joint check again
        sem = [(g, _run_group(ws, g, model, ctx, sysname, budget, per[rec["task"]]) if rec["task"] in per else rec)
               for g, rec in sem]
        bad = [f"{rec['task']}: {e}" for _g, rec in sem if rec["status"] != "VALID" for e in rec["errors"][:5]]
        if bad:
            return V1.reply(ws, "FAILED", bad, budget)
    else:
        return V1.reply(ws, "FAILED", findings_text(out)[:20], budget)
    try:
        vc = K.materialize(out, req, ctx.domain_raw, work, ctx.pin)
    except K.ContractRejected as exc:
        return V1.reply(ws, "FAILED", [f"LRTX_SEMANTIC_CONTRACT_REJECTED: {i}" for i in exc.issues[:10]], budget)
    ops = vc.by_intent()
    results = [(g, {**rec, "doc": rendered(rec["doc"], {it["key"]: ops[f"{g['id']}:{it['key']}"]
                                                        for it in rec["doc"]["intents"]}, ctx, sysname)})
               for g, rec in sem]
    if results:  # the contract's unresolved obligations become open points of the requirements document
        first = results[0][1]
        first["doc"] = {**first["doc"], "open_points": list(dict.fromkeys(
            first["doc"]["open_points"] + [f"SafeC register-io: {o}" for o in vc.unresolved_obligations]))}
    functional = [r for _g, rec in results for r in rec["doc"]["requirements"]]
    cross = V1.run_task(ws, "requirements:crosscutting", lambda fi, pr: crosscut_packet(ws, functional, model, fi, pr),
                        lambda d: V1.validate_group(ws, crosscut_rendered(ws, d, inv, sysname), None, sysname, idx),
                        budget, routed.get("requirements:crosscutting"))
    if cross["status"] != "VALID":
        return V1.reply(ws, "FAILED", [f"requirements:crosscutting: {e}" for e in cross["errors"][:5]], budget)
    cross = {**cross, "doc": crosscut_rendered(ws, cross["doc"], inv, sysname)}
    if V1.safety_text(ws) is None:
        return V1.reply(ws, "FAILED", ["LRTX_SWE1_ALLOCATED_SAFETY_REQUIREMENTS_NOT_SUPPORTED (an approved software "
                                       "safety allocation needs the upstream SSR task)"], budget)
    found = V1.consistency(results, cross)
    if found:
        return V1.reply(ws, "FAILED", [f"{t}: {f}" for t, f in found], budget)
    amap = V1.assemble(ws, inv, results, cross)
    try:
        oracle_file = record_oracle(ws, ctx, _joint(sem), vc, results, amap)
    except (O.OracleRejected, K.ContractRejected) as exc:
        return V1.reply(ws, "FAILED", [f"LRTX_SEMANTIC_ORACLE_REJECTED: {i}" for i in exc.issues[:10]], budget)
    decisions_file = record_owner_decisions(ws, ctx, vc, sem)
    try:
        obligations_file = record_obligations(ws, ctx, _joint(sem), vc)
    except (OB.ObligationsRejected, K.ContractRejected) as exc:
        return V1.reply(ws, "FAILED", [f"LRTX_SEMANTIC_OBLIGATIONS_REJECTED: {i}" for i in exc.issues[:10]], budget)
    S.record(ws, "SWE.1/semantic.json", {"schema": "forge-c/lrtx-swe1-semantic/1", "at": utc_now(),
                                         "contract_semantic_digest": vc.semantic_digest,
                                         "domain_sha256": vc.domain_sha256, "engine": ctx.pin.expected(),
                                         "engine_calls": ctx.calls, "evidence": str(work.relative_to(ws))})
    checks = V1.self_check(ws)
    if checks:
        return V1.reply(ws, "FAILED", checks[:20], budget)
    return V1.reply(ws, "PASS", [], budget, artifacts=sorted(amap["files"] + [f for f in (oracle_file, obligations_file,
                                                                                         decisions_file) if f]))


# ---- F011-T034: the register-image test oracle of the frozen contract ------------------------------------------------
ORACLE_FILE = "workproducts/SWE.1/register_oracle.json"


def record_oracle(ws: Path, ctx: Context, intents: list[dict], vc: K.ValidatedContract, results: list, amap: dict) \
        -> str | None:
    """derive_tests on the same intents; the oracle is kept only if it is bound to the contract just validated and
    Forge-C re-derives every case. An engine without derive_tests leaves SWE.1 as before (no oracle file)."""
    out, req, work = ctx.validate(intents, "swe1-oracle", operation="derive_tests")
    if out.status == "UNSUPPORTED":
        S.record(ws, "SWE.1/oracle.json", {"status": "NOT_DERIVED", "reason": "engine does not support derive_tests"})
        return None
    again = K.materialize(out, req, ctx.domain_raw, work, ctx.pin)
    if again.semantic_digest != vc.semantic_digest:
        raise O.OracleRejected([f"ORACLE_CONTRACT_DRIFT: {again.semantic_digest} != {vc.semantic_digest}"])
    doc = O.materialize(out, vc, ctx.domain_raw, work)
    case_of = {f"{g['id']}:{r['key']}": r["effects"][0]["case"] for g, rec in results
               for r in rec["doc"]["requirements"] if r.get("effects")}
    missing = sorted(i for i, c in case_of.items() if c not in amap["case"])
    if missing or sorted(case_of) != sorted(o["intent_id"] for o in vc.operations):
        raise O.OracleRejected([f"ORACLE_CASE_MAP: unmapped {missing[:5]}"])
    V1.write_scoped(ws, {ORACLE_FILE: json.dumps({
        "schema": "forge-c/lrtx-register-oracle/1", "contract_semantic_digest": vc.semantic_digest,
        "domain_sha256": vc.domain_sha256, "engine": ctx.pin.expected(), "operations": list(vc.operations),
        "case_of_intent": case_of, "oracle": doc}, indent=1, sort_keys=True) + "\n"})
    return ORACLE_FILE


# ---- F011-T033: the C11/ACSL obligations of the frozen contract --------------------------------------------------------
OBLIGATIONS_FILE = "workproducts/SWE.1/register_obligations.json"


def record_obligations(ws: Path, ctx: Context, intents: list[dict], vc: K.ValidatedContract) -> str | None:
    """derive_contracts on the same intents; the obligations are kept only if they are bound to the contract just
    validated and Forge-C re-derives every one (safec_bridge.obligations). An engine without derive_contracts
    leaves SWE.1 as before (no obligations file)."""
    out, req, work = ctx.validate(intents, "swe1-obligations", operation="derive_contracts")
    if out.status == "UNSUPPORTED":
        S.record(ws, "SWE.1/obligations.json", {"status": "NOT_DERIVED",
                                                "reason": "engine does not support derive_contracts"})
        return None
    again = K.materialize(out, req, ctx.domain_raw, work, ctx.pin)
    if again.semantic_digest != vc.semantic_digest:
        raise OB.ObligationsRejected([f"OBLIGATIONS_CONTRACT_DRIFT: {again.semantic_digest} != {vc.semantic_digest}"])
    doc = OB.materialize(out, vc, ctx.domain_raw, work)
    V1.write_scoped(ws, {OBLIGATIONS_FILE: json.dumps({
        "schema": "forge-c/lrtx-register-obligations/1", "contract_semantic_digest": vc.semantic_digest,
        "domain_sha256": vc.domain_sha256, "engine": ctx.pin.expected(), "obligations": doc},
        indent=1, sort_keys=True) + "\n"})
    return OBLIGATIONS_FILE


# ---- F011-T017: uncovered fields and missing owner decisions as source-linked findings ---------------------------------
DECISIONS_FILE = "workproducts/SWE.1/owner_decisions.json"


def owner_decisions(ctx: Context, vc: K.ValidatedContract, sem: list) -> list[dict]:
    """Every in-scope field the contract leaves without an intent, every obligation SafeC leaves unresolved and every
    open point of the author becomes one finding for the owner, linked to its source facts (fact id, RM section and
    pages) where one exists. Derived from the validated contract and the domain, never from model text alone."""
    reasons = {}
    for g, rec in sem:
        for x in rec["doc"].get("not_covered") or []:
            full = x["field"] if "." in x["field"] else f"{g['register']}.{x['field']}"
            reasons[full] = x.get("reason", "")
    by_field = {(v["register"], v["field"]): (k, v) for k, v in ctx.facts.items() if "value" not in v}
    out = []
    for c in vc.coverage:
        if c["intent_ids"]:
            continue
        fid, fact = by_field.get((c["register"], c["field"]), (None, {}))
        full = f"{c['register']}.{c['field']}"
        out.append({"id": f"OD-{len(out) + 1:03d}", "kind": "UNCOVERED_FIELD", "subject": full,
                    "decision": "confirm that this field is outside the scope, or extend the scope",
                    "author_reason": reasons.get(full) or None, "source_fact_ids": [fid] if fid else [],
                    "section": fact.get("section"), "pages": fact.get("pages") or [],
                    "source_linked": bool(fid)})
    for u in vc.unresolved_obligations:
        cited = sorted(set(re.findall(r"F-[A-Za-z0-9_.:-]+", u)) & set(ctx.facts))
        kind = u.split(":", 1)[0]
        out.append({"id": f"OD-{len(out) + 1:03d}", "kind": kind, "subject": u[:300],
                    "decision": {"ERRATA_NOT_BASELINED": "provide the errata sheet, or accept that errata effects "
                                                         "are not checked",
                                 "PRECONDITION_NOT_VERIFIED": "confirm how the cited precondition is ensured"}.get(
                                     kind, "decide how this obligation is discharged"),
                    "author_reason": None, "source_fact_ids": cited,
                    "section": ctx.facts[cited[0]]["section"] if cited else None,
                    "pages": sorted({p for c in cited for p in ctx.facts[c]["pages"]}),
                    "source_linked": bool(cited)})
    for g, rec in sem:
        for o in rec["doc"].get("open_points") or []:
            if o.strip():
                out.append({"id": f"OD-{len(out) + 1:03d}", "kind": "AUTHOR_OPEN_POINT", "subject": o.strip()[:300],
                            "decision": "resolve the open point", "author_reason": None,
                            "source_fact_ids": [], "section": None, "pages": [], "source_linked": False,
                            "group": g["id"]})
    return out


def record_owner_decisions(ws: Path, ctx: Context, vc: K.ValidatedContract, sem: list) -> str:
    items = owner_decisions(ctx, vc, sem)
    V1.write_scoped(ws, {DECISIONS_FILE: json.dumps({
        "schema": "forge-c/lrtx-owner-decisions/1", "contract_semantic_digest": vc.semantic_digest,
        "domain_sha256": vc.domain_sha256, "status": "OPEN" if items else "NONE", "findings": items,
        "note": "findings for the owner; none is decided by the factory"}, indent=1, sort_keys=True) + "\n"})
    return DECISIONS_FILE
