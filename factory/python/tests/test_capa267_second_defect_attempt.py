"""CAPA-267 (owner 2026-11-16: "I'd also allow a second maintainer attempt per CAPA after a gate rejection. I WANT
OMNIVERSE AUTONOMOUS"): defect mode gave each CAPA one window - CAPA-263's only candidate (fec9274c) was rejected by
a stale pre-gate and the CAPA could never be tried again. Now: at most MAX_DEFECT_ATTEMPTS windows in which the
maintainer actually ran; a window refused before the maintainer ran does not count; an attempt still running blocks a
parallel one; each attempt has its own record key."""
import json
import subprocess
import time

from forge_factory.modelservice import maintenance as MS
from test_f022_defect_mode import WO, _ws, owner  # noqa: F401 - fixtures
from test_afo_m5_maintainer import factory  # noqa: F401

NOW = time.strftime("%Y%m%d%H%M", time.gmtime())
OLD = time.strftime("%Y%m%d%H%M", time.gmtime(time.time() - 6 * 3600))


def _plan(tmp_path, factory, attempts):  # noqa: F811
    live = subprocess.run(["git", "rev-parse", "HEAD"], cwd=factory, capture_output=True, text=True).stdout.strip()
    dep = tmp_path / "deployer"
    dep.mkdir(exist_ok=True)
    (dep / "state.json").write_text(json.dumps({"live": {"commit": live}}))
    (dep / "maintenance-attempts.json").write_text(json.dumps(attempts))
    root = tmp_path / "line"
    if not (root / "workorders" / WO).exists():
        _ws(root)
    return MS.defect_plan(deployer=dep, owner_cre=tmp_path / "owner/incidents.sqlite3", qroot=tmp_path / "q",
                          workorders=root / "workorders", git=lambda *a: live, tier_active=lambda: False)


def test_a_rejected_candidate_gets_one_more_attempt(tmp_path, owner, factory):  # noqa: F811
    rejected = {"started": OLD, "ended": OLD, "result": {"agent_exit": 0, "outcome": "REJECTED"}}
    p = _plan(tmp_path, factory, {"defect:CAPA-904": rejected})
    assert p["capa"]["capa_id"] == "CAPA-904" and p["attempt_key"] == "defect:CAPA-904#2"
    assert _plan(tmp_path, factory, {"defect:CAPA-904": rejected, "defect:CAPA-904#2": rejected}) == \
        {"skip": "ATTEMPTS_EXHAUSTED_FOR_THIS_CAPA"}


def test_a_window_refused_before_the_maintainer_ran_does_not_count(tmp_path, owner, factory):  # noqa: F811
    refused = {"started": OLD, "ended": OLD, "result": {"window": {"outcome": "REFUSED", "refusal": "LANE_NOT_READY:X"}}}
    p = _plan(tmp_path, factory, {"defect:CAPA-904": refused, "defect:CAPA-904#2": refused})
    assert p["attempt_key"] == "defect:CAPA-904#3"


def test_an_attempt_still_running_blocks_a_parallel_one(tmp_path, owner, factory):  # noqa: F811
    assert _plan(tmp_path, factory, {"defect:CAPA-904": {"started": NOW}}) == {"skip": "ATTEMPT_IN_PROGRESS"}
    # a record left unfinished for hours (crashed window) counts as one attempt, never as a lock
    p = _plan(tmp_path, factory, {"defect:CAPA-904": {"started": OLD}})
    assert p["attempt_key"] == "defect:CAPA-904#2"
