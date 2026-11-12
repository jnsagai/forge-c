"""An owner-lane retry keeps its best earlier tests, as a draft that is tested again."""
import json
from pathlib import Path

import pytest
from forge_factory import attempt_carry as C
from forge_factory.afo import line_orders as LO

ORDERS = ("WO-A", "WO-B", "WO-C", "WO-D")


def attempt(root, name, *runs, suite=True, skew=0.0):
    """runs: (passed, verified) per robot run, each with its own file versions."""
    import hashlib
    ws = root / name / "workspace"
    (ws / C.SNAPSHOTS).mkdir(parents=True)
    (ws / "evidence").mkdir()
    (ws / C.TESTS).mkdir(parents=True)
    results, integrity = ["not json"], []
    for i, (passed, verified) in enumerate(runs):
        files = {}
        for leaf in ["scn_init.c"] + (["test_crc_requirements.robot"] if suite else []):
            data = f"{name}:{i}:{leaf}".encode()
            sha = hashlib.sha256(data).hexdigest()
            (ws / C.SNAPSHOTS / sha).write_bytes(data)
            files[f"{C.TESTS}/{leaf}"] = sha
            (ws / C.TESTS / leaf).write_bytes(data)
        files["software/tests/target/test_x.c"] = "0" * 64
        t = f"2026-11-07T10:{i:02d}:00Z"
        results.append(json.dumps({"op": "run_robot", "phase": "SWE.6", "ts_utc": t, "result": {
            "summary": f"robot: {passed}/24 tests passed; {verified}/24 requirements verified (Renode)"}}))
        integrity.append(json.dumps({"op": "run_robot", "phase": "SWE.6", "files": files,
                                     "ts_utc": f"2026-11-07T10:{i:02d}:{int(skew):02d}Z"}))
    (ws / C.RESULTS).write_text("\n".join(results) + "\n")
    (ws / C.INTEGRITY).write_text("\n".join(integrity) + "\n")
    return ws


def test_best_run_wins_even_when_its_attempt_ended_worse(tmp_path):
    attempt(tmp_path, "WO-A", (15, 13), (15, 13))
    attempt(tmp_path, "WO-B", (15, 13), (24, 22), (18, 18))
    chosen = C.select("WO-C", ORDERS, tmp_path)
    assert (chosen["source_work_order"], chosen["passed"], chosen["verified"]) == ("WO-B", 24, 22)
    ws = tmp_path / "new"
    ws.mkdir()
    carried = C.install(ws, "WO-C", ORDERS, tmp_path)
    assert (ws / C.TESTS / "scn_init.c").read_text() == "WO-B:1:scn_init.c"
    assert sorted(f["path"].rsplit("/", 1)[1] for f in carried["files"]) == ["scn_init.c", "test_crc_requirements.robot"]
    assert not (ws / "software/tests/target").exists() and "verdict" not in carried


def test_requirements_break_a_tie_in_tests_and_later_wins_a_full_tie(tmp_path):
    attempt(tmp_path, "WO-A", (24, 20))
    attempt(tmp_path, "WO-B", (24, 22))
    attempt(tmp_path, "WO-C", (24, 22))
    assert C.select("WO-D", ORDERS, tmp_path)["source_work_order"] == "WO-C"
    assert C.select("WO-C", ORDERS, tmp_path)["source_work_order"] == "WO-B"


@pytest.mark.parametrize("runs", [(), ((0, 0),)])
def test_no_run_or_no_pass_carries_nothing(tmp_path, runs):
    attempt(tmp_path, "WO-A", *runs)
    assert C.install(tmp_path / "new", "WO-B", ORDERS, tmp_path) is None


def test_run_without_a_suite_carries_nothing(tmp_path):
    attempt(tmp_path, "WO-A", (15, 13), suite=False)
    assert C.select("WO-B", ORDERS, tmp_path) is None


def test_changed_snapshot_or_unaligned_logs_refuse_the_run(tmp_path):
    ws = attempt(tmp_path, "WO-A", (15, 13))
    snap = next((ws / C.SNAPSHOTS).iterdir())
    snap.write_bytes(b"tampered")
    assert C.select("WO-B", ORDERS, tmp_path) is None
    attempt(tmp_path, "WO-C", (15, 13), skew=30)
    assert C.runs(tmp_path / "WO-C" / "workspace") == []


def test_a_symlinked_snapshot_refuses_the_run(tmp_path):
    ws = attempt(tmp_path, "WO-A", (15, 13))
    snap = next(p for p in (ws / C.SNAPSHOTS).iterdir())
    target = tmp_path / "elsewhere"
    target.write_bytes(snap.read_bytes())
    snap.unlink()
    snap.symlink_to(target)
    assert C.select("WO-B", ORDERS, tmp_path) is None


def test_existing_target_refuses(tmp_path):
    attempt(tmp_path, "WO-A", (15, 13))
    ws = tmp_path / "new"
    (ws / C.TESTS).mkdir(parents=True)
    (ws / C.TESTS / "scn_init.c").write_text("authored")
    with pytest.raises(ValueError, match="ATTEMPT_CARRY_TARGET_EXISTS"):
        C.install(ws, "WO-B", ORDERS, tmp_path)


def test_prompt_note_only_for_its_phase():
    manifest = {"attempt_carry": {"phase": "SWE.6", "passed": 24, "verified": 22, "total": 24}}
    note = C.prompt_note(manifest, "SWE.6")[0]
    assert "24 of 24 tests" in note and "22 of 24 requirements" in note
    assert C.prompt_note(manifest, "SWE.5") == [] and C.prompt_note(None, "SWE.6") == []


def test_prompts_gain_the_note_only_with_a_carry():
    from forge_factory.workflow import prompts as P

    steps = ["a", "b", "c"]
    saved = P.ASSESSMENT["manifest"]
    try:
        P.ASSESSMENT["manifest"] = None
        assert P._rework_steps("SWE.6", steps) == steps
        P.ASSESSMENT["manifest"] = {"attempt_carry": {"phase": "SWE.6", "passed": 15, "verified": 13, "total": 24}}
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


def test_campaign_retry_carries_only_its_own_lineage_and_phase(tmp_path):
    from forge_factory.afo import owner_supervised_development as D

    gpio = D.carry_orders("WO-F014-SWE6-GPIOL-20261107-L40C")
    attempt(tmp_path, gpio[0], (10, 8))
    attempt(tmp_path, gpio[1], (12, 9))
    attempt(tmp_path, "WO-F014-SWE6-SPIL-20261107-L41", (24, 24))  # another lineage
    attempt(tmp_path, "WO-F014-SWE5-GPIOL-20261107-L40", (24, 24))  # another phase
    chosen = C.select(gpio[2], gpio, tmp_path)
    assert (chosen["source_work_order"], chosen["passed"]) == (gpio[1], 12)
    assert len(gpio) == 64 and all(wo.startswith("WO-F014-SWE6-GPIOL-20261107-L40") for wo in gpio)


def test_workorder_carry_hook_asks_the_lane_for_the_lineage_phase_orders():
    from forge_factory import workorder

    source = Path(workorder.__file__).read_text()
    assert 'stop_after == "SWE.6"' in source and "carry_orders(wo)" in source and "CARRY_ORDERS" not in source
