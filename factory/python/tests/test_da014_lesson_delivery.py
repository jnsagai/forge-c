"""DA-T040 / DA-FR-040: qualified lessons reach a job only through the two delivery paths (structured packet, knowledge
MCP), complete or not at all: the meaning after character 120 arrives, an unfit lesson block is omitted explicitly
(never refusing the task), inspectors, holdouts and other scopes receive nothing, and EXPOSURE is recorded separately
from APPLICATION."""
import json
import os

import pytest
from forge_factory.knowledge import experience
from forge_factory.knowledge.context import applicability
from forge_factory.knowledge.store import LessonStore
from forge_factory.lrtx import structured as S
from test_da014_learning import candidate

EXCLUSION = "EXCLUSION: does not apply to STM32H7."


def _manifest(ws, **extra):
    (ws / ".forge-run").mkdir(parents=True, exist_ok=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({
        "work_order": "WO-B", "target": {"part_number": "STM32N6"}, "layer": "LL",
        "inputs": [{"path": "inputs/rm.md", "sha256": "a" * 64}], "tool_versions": {"gcc": "14"}, **extra}))


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws = tmp_path / "ws"
    _manifest(ws)
    sv = applicability(ws)["source_version"]
    memory = LessonStore()
    lesson = candidate(memory, tmp_path, source_version=sv)
    assert memory.validate(memory.propose(lesson, phase="SWE.3")["lesson_id"])["state"] == "VALIDATED"
    return {"ws": ws, "memory": memory, "sv": sv, "tmp": tmp_path}


def _packet(ws, role="swe3-author", **kw):
    token = S.RECOVERY_WORKSPACE.set(ws)
    try:
        return S.packet(phase="SWE.3", task="map fields", role=role, instructions="register field mapping",
                        sources=[], criteria=[], output_schema={"type": "object"}, model="m", with_skill=False, **kw)
    finally:
        S.RECOVERY_WORKSPACE.reset(token)


def _lesson_sources(p):
    return [s for s in p["sources"] if s["path"].startswith(".forge-run/knowledge/")]


def test_an_author_packet_carries_the_complete_lesson_and_records_exposure_not_application(env):
    p = _packet(env["ws"])
    [src] = _lesson_sources(p)
    text = (env["ws"] / src["path"]).read_text()
    assert EXCLUSION in text and EXCLUSION in "".join(m["content"] for m in p["_messages"])  # past char 120
    rows = env["memory"].consumers(json.loads(text)["lessons"][0]["lesson_id"])
    assert rows and "lessons_omitted" not in p
    report = experience.report(env["memory"])
    assert report["exposures"] == 1 and report["applications"] == 0
    with env["memory"]._conn() as db:
        rec = [json.loads(r[0]) for r in db.execute("SELECT record FROM lesson_transfers WHERE kind='EXPOSURE'")]
    assert rec[0]["data"]["packet_input_hash"] == p["input_hash"]
    lid = json.loads(text)["lessons"][0]["lesson_id"]  # the advisory register's lessons rung reads exactly this
    assert env["memory"].exposures("WO-B", "SWE.3") == [lid] and env["memory"].exposures("WO-B", "SWE.1") == []
    assert env["memory"].exposures("WO-other") == []


@pytest.mark.parametrize("role,manifest", [
    ("swe3-inspector", {}),                                   # inspectors never receive general lessons
    ("swe3-author", {"evaluation_holdout": True}),            # the final evaluation holdout stays isolated
    ("swe3-author", {"target": {"part_number": "STM32H7"}}),  # another target
    ("swe3-author", {"tool_versions": {"gcc": "15"}}),        # another tool version
])
def test_other_roles_holdouts_targets_and_tools_receive_no_lesson(env, role, manifest):
    _manifest(env["ws"], **manifest)
    p = _packet(env["ws"], role=role)
    assert _lesson_sources(p) == [] and experience.report(env["memory"])["exposures"] == 0


def test_an_unfit_lesson_block_is_omitted_whole_and_the_task_still_runs(env, monkeypatch):
    bare = _packet(env["ws"], with_lessons=False)
    monkeypatch.setattr(S, "CONTEXT_TOKENS", bare["accounting"]["estimated_prompt_tokens"] + S.DEFAULT_OUTPUT_RESERVE + 5)
    p = _packet(env["ws"])
    assert p["lessons_omitted"] == {"count": 1, "reason": "CONTEXT_UNFIT"} and _lesson_sources(p) == []
    assert p["input_hash"] == bare["input_hash"]  # exactly the packet without lessons
    assert experience.report(env["memory"])["exposures"] == 0  # nothing delivered, nothing exposed


def test_the_knowledge_mcp_delivers_complete_lessons_or_omits_them_whole(env, monkeypatch):
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import knowledge

    big = candidate(env["memory"], env["tmp"] / "v2", version=2, source_version=env["sv"],
                    constraints=" Applies only when " + "y" * 480 + ".")
    (env["tmp"] / "v2").mkdir(exist_ok=True)
    assert env["memory"].validate(env["memory"].propose(big, phase="SWE.3")["lesson_id"])["state"] == "VALIDATED"
    monkeypatch.setenv("FORGE_MCP_TRUST", "env")
    monkeypatch.setenv("FORGE_WORKSPACE", str(env["ws"]))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(env["tmp"] / "ev"))
    monkeypatch.setenv("FORGE_ROLE", "swe3-author")
    monkeypatch.setenv("FORGE_PHASE", "SWE.3")
    op = next(x for x in knowledge.OPERATIONS if x.name == "find_lessons")
    out = sdk.invoke("forge-knowledge-mcp", op, {"query": "register field mapping"})
    delivered = json.loads(out["metrics"]["data"])["lessons"]
    assert out["metrics"]["omitted_unfit"] == 1 and len(delivered) == 1
    assert EXCLUSION in delivered[0]["remedy"] and "y" * 480 not in out["metrics"]["data"]
    prov = delivered[0]["provenance"]  # meaning inline and complete; provenance by its stored, hash-bound artifact
    assert prov["ref"] in out["artifact_refs"] and len(prov["record_sha256"]) == 64
    assert out["metrics"]["envelope_bytes"] <= 1100 and out["metrics"]["envelope_tokens_upper_bound"] > 0
    assert experience.report(env["memory"])["exposures"] == 1  # only the delivered lesson is exposed
    os.environ.pop("FORGE_ROLE", None)
