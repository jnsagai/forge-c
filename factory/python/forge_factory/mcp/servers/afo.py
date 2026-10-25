"""AFO-T038 (AFO-FR-007/041/048; AT-030/036/045/046) - forge-afo-mcp: the afo-recovery-planner's ONLY tools.

Scope: one frozen recovery case the Conductor wrote, `FORGE_AFO_CASE` = <state>/afo/cases/<bundle_id>/case.json
({bundle, workspace, requirements_sha256, budget, allowed_strategies}). Every read is bounded and limited to that
case; the requirement excerpt is served only while the requirements file still has the frozen hash. The single
write, `submit_recovery_plan`, is the deterministic broker: it schema-checks the plan, caps its size and stores it as
PROPOSED next to the case - it executes nothing; the Conductor's deterministic validator decides.
"""
from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path

from pydantic import Field, RootModel

from ...afo.contracts import CONTRACTS
from ...common import sha256_file, state_dir
from ..sdk import Operation, ToolContext, ToolDenied, ToolInput, build_server, result
from .afo_payload import payload

MAX_BYTES = 2048
PLAN_SCHEMA = json.loads((CONTRACTS / "recovery-plan.schema.json").read_text())


def _case() -> tuple[dict, Path]:
    p = Path(os.environ.get("FORGE_AFO_CASE", ""))
    root = (state_dir() / "afo/cases").resolve()
    if not p.is_file() or root not in p.resolve().parents:
        raise ToolDenied("AFO_CASE_OUT_OF_SCOPE", str(p)[:100])
    return json.loads(p.read_text()), p


def _packet(ctx, case):
    from ...afo.diagnosis_packet import load
    from ...afo.durable import Refused
    if ctx.role != 'afo-recovery-planner':
        raise ToolDenied('EVIDENCE_ROLE_DENIED')
    try:
        packet = load(case['packet_ref'])
    except (Refused, KeyError) as exc:
        raise ToolDenied('PACKET_REFERENCE_INVALID') from exc
    if ctx.phase is not None and ctx.phase != packet['binding']['phase']:
        raise ToolDenied('EVIDENCE_PHASE_DENIED')
    return packet


class NoIn(ToolInput):
    offset: int = Field(default=0, ge=0, le=1000000, description="Page offset; continue at metrics.next_offset if present.")


class ReqIn(NoIn):
    requirement_id: str | None = Field(default=None, pattern=r"^SWR-\d{3}$")
    artifact_ref: str | None = Field(default=None, max_length=200)


class SemanticProposal(RootModel[dict]):
    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        from ...afo.durable import schema
        return deepcopy(schema('semantic-proposal'))


class RecoveryPlan(RootModel[dict]):
    """Carry the authoritative nested contract through the MCP function's type annotation.

    The shared SDK exposes field annotations, not Field metadata. A nested model preserves this
    schema on the actual wire; the broker independently validates its uncoerced values below.
    """

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        return deepcopy(PLAN_SCHEMA)


class PlanIn(ToolInput):
    semantic: SemanticProposal | None = None
    plan: RecoveryPlan | None = None
    plan_json: str | None = Field(default=None, min_length=10, max_length=4000, description=(
        "Legacy encoded input; prefer the structured plan argument. "
        "Recovery-plan JSON object. material_difference_ref and rationale_code are each at most 200 characters; "
        "put longer rationale in notes (at most 500 characters). budget_estimate has exactly the nonnegative integer "
        "keys tokens_max, wall_seconds_max, turns_max. Use this case's exact order_id, attempt_id and "
        "failure_fingerprint. Read required_plan_fields through read_budget_snapshot. Rejected proposals execute nothing."))


def read_failure_bundle(ctx: ToolContext, a: NoIn) -> dict:
    case, _ = _case()
    b = case["bundle"]
    body = {k: b[k] for k in ("bundle_id", "order_id", "attempt_id", "phase", "failure_class", "fingerprint", "error_code",
                                         "requirements_refs", "redacted_summary", "untrusted_source_refs")}
    return payload(ctx, body, a.offset, refs=[f"afo-bundle:{b['bundle_id']}"], summary="Frozen failure bundle; untrusted data")


def list_gate_findings(ctx: ToolContext, a: NoIn) -> dict:
    case, _ = _case()
    if case.get('packet_ref'):
        packet = _packet(ctx, case)
        return payload(ctx, {'findings': packet['findings'], 'obligations': packet['obligations'],
            'artifacts': packet['artifacts'], 'complete': packet['complete'], 'missing': packet['missing']}, a.offset,
            summary='Complete hash-bound inventory; page until next_offset is null')
    items = [x for x in case["bundle"]["redacted_summary"].split("; ") if x]
    return payload(ctx, items, a.offset, refs=[f"afo-bundle:{case['bundle']['bundle_id']}"],
                   summary="Gate findings; untrusted data")


def read_requirement_excerpt(ctx: ToolContext, a: ReqIn) -> dict:
    case, _ = _case()
    if a.artifact_ref is not None:
        from ...afo.diagnosis_packet import evidence
        from ...afo.durable import Refused
        if a.requirement_id is not None:
            raise ToolDenied('EVIDENCE_INPUT_AMBIGUOUS')
        packet = _packet(ctx, case)
        try:
            text = evidence(packet, a.artifact_ref, role=ctx.role, phase=packet['binding']['phase'])
        except Refused as exc:
            raise ToolDenied(exc.code) from exc
        return payload(ctx, text, a.offset, refs=[a.artifact_ref], summary='Hash-verified primary evidence')
    if a.requirement_id is None:
        raise ToolDenied('EVIDENCE_REFERENCE_REQUIRED')
    req = Path(case["workspace"]) / "workproducts/SWE.1/software_requirements.md"
    if not req.is_file() or sha256_file(req) != case["requirements_sha256"]:
        raise ToolDenied("REQUIREMENTS_NOT_FROZEN", "requirements changed since the case was frozen")
    m = re.search(rf"^- \*\*{a.requirement_id}\*\*.*(?:\n  - .*)*", req.read_text(), re.M)
    return payload(ctx, m.group(0) if m else "not found", a.offset, status="PASS" if m else "BLOCKED",
                   refs=[f"requirements:{case['requirements_sha256'][:16]}"], summary=a.requirement_id)


def read_budget_snapshot(ctx: ToolContext, a: NoIn) -> dict:
    case, _ = _case()
    return payload(ctx, {"budget": case["budget"], "allowed_strategies": case["allowed_strategies"],
                         "required_plan_fields": PLAN_SCHEMA["required"],
                         "budget_estimate_fields": ["tokens_max", "wall_seconds_max", "turns_max"]},
                   a.offset, summary="Remaining budget, allowed strategies and plan contract")


def submit_recovery_plan(ctx: ToolContext, a: PlanIn) -> dict:
    from ...afo import contracts

    case, path = _case()
    if case.get('packet_ref') or a.semantic is not None:
        from ...afo.completion_receipt import Context, Receipts
        from ...afo.durable import Refused
        from ...afo.queue import Store
        _packet(ctx, case)
        if a.semantic is None or a.plan is not None or a.plan_json is not None:
            raise ToolDenied('SEMANTIC_INPUT_REQUIRED_NO_ADMINISTRATIVE_PLAN')
        store = Store()
        try:
            job = Context.from_job(store, ctx.run_id)
            if job.case_sha256 != sha256_file(path):
                raise ToolDenied('JOB_CASE_MISMATCH')
            receipt = Receipts(store).submit(job, a.semantic.root)
        except Refused as exc:
            raise ToolDenied(exc.code) from exc
        return result(ctx, 'PASS' if receipt['submission_state'] == 'STORED' else 'BLOCKED',
            'Submission receipted; admissibility and verification are independent',
            ['afo-receipt:' + receipt['receipt_id']], receipt['reason_codes'],
            {'submission_state': receipt['submission_state']}, 'forge-afo', input_obj={})
    if (a.plan is None) == (a.plan_json is None):
        raise ToolDenied("PLAN_INPUT_AMBIGUOUS_OR_MISSING", "supply exactly one plan object or legacy plan_json")
    if a.plan is not None:
        plan = a.plan.root
        if len(json.dumps(plan)) > 4000:
            raise ToolDenied("PLAN_TOO_LARGE", "structured plan exceeds the existing 4000-character bound")
    else:
        try:
            plan = json.loads(a.plan_json)
        except ValueError as exc:
            raise ToolDenied("PLAN_NOT_JSON", str(exc)[:80]) from exc
    errs = contracts.errors("recovery-plan", plan)
    if errs:
        return result(ctx, "BLOCKED", "plan rejected by schema", [], errs[:5], {}, "forge-afo", input_obj={})
    if plan.get("order_id") != case["bundle"]["order_id"] or plan.get("attempt_id") != case["bundle"]["attempt_id"]:
        raise ToolDenied("PLAN_FOR_ANOTHER_CASE", plan.get("order_id", "?"))
    out = path.parent / "proposed-plan.json"
    out.write_text(json.dumps(plan, sort_keys=True))
    return result(ctx, "PASS", "plan stored as PROPOSED (not accepted: the Conductor validates it)",
                  [f"afo-plan:{plan['plan_id']}"], [], {}, "forge-afo", input_obj={"plan_id": plan["plan_id"]})


OPERATIONS = [
    Operation("read_failure_bundle", NoIn, read_failure_bundle, "The frozen failure bundle of this recovery case."),
    Operation("list_gate_findings", NoIn, list_gate_findings, "Bounded gate/inspection findings of this case."),
    Operation("read_requirement_excerpt", ReqIn, read_requirement_excerpt, "One SWR from the frozen requirements."),
    Operation("read_budget_snapshot", NoIn, read_budget_snapshot, "Remaining budget and allowed strategies."),
    Operation("submit_recovery_plan", PlanIn, submit_recovery_plan, "Store a typed plan as PROPOSED (no execution)."),
]

if __name__ == "__main__":
    build_server("forge-afo-mcp", OPERATIONS).run("stdio")
