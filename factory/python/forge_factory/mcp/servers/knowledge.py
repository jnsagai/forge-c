"""T017 — forge-knowledge-mcp: lesson lookup and proposal. Validation/publication is NOT an agent op:
`propose_lesson` only stores a PROPOSED candidate and runs the deterministic curator, which may quarantine
it; `retract_lesson` exists for the deterministic policy controller and has no AI role grant.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from ...knowledge.store import LessonStore
from ...supervisor.store import IncidentStore
from ..sdk import Operation, ToolContext, ToolDenied, ToolInput, build_server, result


class FindIn(ToolInput):
    query: str = Field(min_length=3, max_length=200)
    tool: str = Field(default="", max_length=60)
    k: int = Field(default=3, ge=1, le=3)


class TestRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(max_length=100)
    status: str = Field(pattern=r"^(PASS|FAIL|NOT_RUN)$")
    evidence_ref: str = Field(max_length=512)


class ProposeIn(ToolInput):
    source_incident_id: str | None = Field(default=None, pattern=r"^inc-[0-9a-f]{12}$")
    source_attempt_id: str | None = Field(default=None, max_length=100)
    contract_version: str | None = Field(default=None, pattern=r'^2\.0$')
    source_kind: str | None = Field(default=None, pattern=r'^(REPAIR_PROMOTED|ORDINARY_OUTCOME|NEGATIVE_OBSERVATION)$')
    version: int | None = Field(default=None, ge=1)
    supersedes: str | None = None
    experience_ref: str | None = Field(default=None, pattern=r'^experience-[a-f0-9]{24}$')
    qualification_ref: str | None = Field(default=None, max_length=200)
    applicability: dict | None = None
    symptoms: str = Field(min_length=1, max_length=600)
    root_cause: str = Field(min_length=1, max_length=700)
    remedy: str = Field(min_length=1, max_length=850)
    constraints: str = Field(default="", max_length=1200)
    evidence_refs: list[str] = Field(min_length=1, max_length=10)
    tool_versions: dict[str, str] = Field(default_factory=dict)
    validation_tests: list[TestRef] = Field(min_length=1, max_length=10)


class RetractIn(ToolInput):
    lesson_id: str = Field(pattern=r"^lesson-[0-9a-f]{12}$")
    reason: str = Field(min_length=3, max_length=200)


def find_lessons(ctx: ToolContext, a: FindIn) -> dict:
    out = LessonStore().find(a.query, ctx.run_id, a.tool or None, ctx.phase, a.k, role=ctx.role, record_usage=False)
    import json

    # Deliver complete meaning/constraints/provenance or explicitly omit the whole lesson; never a 120-char remedy.
    delivered = {'lessons': [], 'note': out['note']}
    for lesson in out['lessons']:
        candidate = {**delivered, 'lessons': [*delivered['lessons'], lesson]}
        if len(json.dumps(candidate).encode()) <= 1100:
            delivered = candidate
    from ...knowledge.experience import transfer
    for lesson in delivered['lessons']:
        transfer(LessonStore(), lesson['lesson_id'], ctx.run_id, 'EXPOSURE')
    omitted = len(out['lessons']) - len(delivered['lessons'])
    return result(ctx, 'PASS', f"{len(delivered['lessons'])} complete validated lessons; {omitted} omitted for envelope",
        [ctx.store(json.dumps(out).encode(), 'json')], [],
        {'reference_data': delivered, 'omitted_unfit': omitted, 'tokens_estimated': out['tokens_estimated']},
        'forge-knowledge', input_obj=a.model_dump())


def propose_lesson(ctx: ToolContext, a: ProposeIn) -> dict:
    store = LessonStore(incidents=IncidentStore())
    rec = store.propose({**a.model_dump(exclude_none=True), "validation_tests": [t.model_dump() for t in a.validation_tests]})
    rec = store.validate(rec["lesson_id"])
    return result(ctx, "PASS" if rec["state"] == "VALIDATED" else "BLOCKED",
                  f"{rec['lesson_id']} {rec['state']}", [f"lesson:{rec['lesson_id']}"], rec.get("_reasons", []),
                  {"state": rec["state"]}, "forge-knowledge", input_obj={"source": a.source_attempt_id})


def retract_lesson(ctx: ToolContext, a: RetractIn) -> dict:
    raise ToolDenied("POLICY_CONTROLLER_ONLY", "retract_lesson")


OPERATIONS = [
    Operation("find_lessons", FindIn, find_lessons, "Top-K (<=3) validated lessons with provenance."),
    Operation("propose_lesson", ProposeIn, propose_lesson, "Propose a lesson from a promoted repair (auto-curated)."),
    Operation("retract_lesson", RetractIn, retract_lesson, "Deterministic policy controller only (no AI grant)."),
]

if __name__ == "__main__":
    build_server("forge-knowledge-mcp", OPERATIONS).run("stdio")
