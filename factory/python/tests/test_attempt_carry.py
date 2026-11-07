"""An owner-lane retry keeps its best earlier tests, as a draft that is tested again."""
import json
from pathlib import Path

import pytest
from forge_factory import attempt_carry as C
from forge_factory.afo import line_orders as LO

ORDERS = ("WO-A", "WO-B", "WO-C", "WO-D")


def attempt(root, name, *scores, suite=True):
    ws = root / name / "workspace"
    tests = ws / C.TESTS
    tests.mkdir(parents=True)
    (tests / "scn_init.c").write_text(name)
    if suite:
        (tests / "test_crc_requirements.robot").write_text(name)
    (tests / "notes.txt").write_text("not a test")
    (ws / "evidence").mkdir()
    rows = [{"op": "run_robot", "phase": "SWE.6", "result": {"summary": f"robot: {s}/24 tests passed; 1/24 requirements"}}
            for s in scores]
    (ws / C.RESULTS).write_text("not json\n" + "".join(json.dumps(r) + "\n" for r in rows))
    return ws


def test_best_earlier_attempt_wins_by_its_last_result_and_later_wins_a_tie(tmp_path):
    attempt(tmp_path, "WO-A", 20, 9)
    attempt(tmp_path, "WO-B", 15)
    attempt(tmp_path, "WO-C", 15)
    attempt(tmp_path, "WO-D", 24)
    chosen = C.select("WO-D", ORDERS, tmp_path)
    assert (chosen["source_work_order"], chosen["passed"], chosen["total"]) == ("WO-C", 15, 24)


def test_only_tests_are_copied_and_stay_a_recorded_draft(tmp_path):
    attempt(tmp_path, "WO-A", 15)
    ws = tmp_path / "new"
    ws.mkdir()
    carried = C.install(ws, "WO-B", ORDERS, tmp_path)
    assert sorted(p.name for p in (ws / C.TESTS).iterdir()) == ["scn_init.c", "test_crc_requirements.robot"]
    assert carried["source_work_order"] == "WO-A" and carried["phase"] == "SWE.6"
    assert {f["path"] for f in carried["files"]} == {f"{C.TESTS}/scn_init.c", f"{C.TESTS}/test_crc_requirements.robot"}
    assert "verdict" not in {k.lower() for k in carried}


@pytest.mark.parametrize("scores", [(), (0,)])
def test_no_result_or_no_pass_carries_nothing(tmp_path, scores):
    attempt(tmp_path, "WO-A", *scores)
    assert C.install(tmp_path / "new", "WO-B", ORDERS, tmp_path) is None


def test_attempt_without_a_suite_carries_nothing(tmp_path):
    attempt(tmp_path, "WO-A", 15, suite=False)
    assert C.select("WO-B", ORDERS, tmp_path) is None


def test_a_symlinked_test_refuses_the_source(tmp_path):
    ws = attempt(tmp_path, "WO-A", 15)
    secret = tmp_path / "secret"
    secret.write_text("x")
    (ws / C.TESTS / "scn_link.c").symlink_to(secret)
    assert C.select("WO-B", ORDERS, tmp_path) is None


def test_existing_target_refuses(tmp_path):
    attempt(tmp_path, "WO-A", 15)
    ws = tmp_path / "new"
    (ws / C.TESTS).mkdir(parents=True)
    (ws / C.TESTS / "scn_init.c").write_text("authored")
    with pytest.raises(ValueError, match="ATTEMPT_CARRY_TARGET_EXISTS"):
        C.install(ws, "WO-B", ORDERS, tmp_path)


def test_prompt_note_only_for_its_phase():
    manifest = {"attempt_carry": {"phase": "SWE.6", "passed": 15, "total": 24}}
    assert "15 of 24" in C.prompt_note(manifest, "SWE.6")[0]
    assert C.prompt_note(manifest, "SWE.5") == [] and C.prompt_note(None, "SWE.6") == []


def test_prompts_gain_the_note_only_with_a_carry():
    from forge_factory.workflow import prompts as P

    steps = ["a", "b", "c"]
    saved = P.ASSESSMENT["manifest"]
    try:
        P.ASSESSMENT["manifest"] = None
        assert P._rework_steps("SWE.6", steps) == steps
        P.ASSESSMENT["manifest"] = {"attempt_carry": {"phase": "SWE.6", "passed": 15, "total": 24}}
        assert "run_robot first" in P._rework_steps("SWE.6", steps)[2]
    finally:
        P.ASSESSMENT["manifest"] = saved


def test_owner_lane_raises_a_real_alert_once(tmp_path, monkeypatch):
    calls = []

    class Line:
        def gh(self, argv):
            calls.append(argv)
            return 0, "https://example.invalid/1"

    monkeypatch.setattr(LO, "supervisor_dir", lambda: tmp_path)
    alert = LO.Escalator(Line(), "owner/repo", dry_run=False, now=1.0)
    assert alert.raise_once("k", "t", "b")["status"] == "CREATED"
    assert LO.Escalator(Line(), "owner/repo", dry_run=False, now=2.0).raise_once("k", "t", "b")["deduplicated"]
    assert len(calls) == 1


def test_owner_lane_is_no_longer_forced_to_dry_run():
    source = Path(LO.__file__).read_text()
    assert "dry_run=not acting or self.owner_supervised_development" not in source
