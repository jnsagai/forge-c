"""CAPA-233 (017 smoke window 20261111T093137Z-e88182): the deployer refused the window release before touching the
lane (LIVE_COMMIT_HAS_NO_ELIGIBLE_DECISION, line_touched false, stopped false); the controller still asked it to restore,
the deployer answered NO_OPEN_WINDOW and the controller left the admission hold set (RESTORE_FAILED), so every later
window and line attempt was refused ADMISSION_ALREADY_HELD. A release the deployer refused untouched needs no restore."""
import json
import sqlite3

from forge_factory.modelservice.window_adapters import OwnerLane


class Out:
    def __init__(self, out="", rc=0):
        self.stdout, self.stderr, self.returncode = out, "", rc


def _lane(tmp_path, calls, events):
    lrtx = tmp_path / "lrtx"
    db = lrtx / "state/supervisor/line-queue.sqlite3"
    db.parent.mkdir(parents=True)
    c = sqlite3.connect(db)
    c.executescript("CREATE TABLE afo_control(key, value, updated_utc, actor);"
                    "CREATE TABLE afo_operator_actions(seq INTEGER PRIMARY KEY, action, actor, reason, utc);"
                    "INSERT INTO afo_control VALUES ('paused','1','t','a');")
    c.commit()
    c.close()
    dep = tmp_path / "deployer"
    dep.mkdir()
    (dep / "log.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    return OwnerLane(lrtx=lrtx, deployer=dep, intent=tmp_path / "intent.json", work=tmp_path / "w",
                     run=lambda argv, **k: calls.append(argv) or Out(), window_id="w20261111093137")


def test_a_release_refused_untouched_needs_no_restore(tmp_path):
    calls = []
    lane = _lane(tmp_path, calls, [{"event": "window_release_failed", "window": "w20261111093137", "line_touched": False,
                                    "stopped": False, "error": "Refused: LIVE_COMMIT_HAS_NO_ELIGIBLE_DECISION"}])
    lane.restart_lane()
    assert calls == []


def test_a_release_that_touched_the_lane_is_restored(tmp_path):
    for ev in ({"event": "window_release_failed", "window": "w20261111093137", "line_touched": True, "stopped": True},
               {"event": "window_released", "window": "w20261111093137"},
               {"event": "window_release_failed", "window": "w-other", "line_touched": False, "stopped": False}):
        calls = []
        _lane(tmp_path / ev["event"] / ev["window"], calls, [ev]).restart_lane()
        assert calls and calls[0][-1] == "window-restore", ev


def test_an_open_window_is_always_restored(tmp_path):
    calls = []
    lane = _lane(tmp_path, calls, [{"event": "window_release_failed", "window": "w20261111093137",
                                    "line_touched": False, "stopped": False}])
    (tmp_path / "deployer/WINDOW.json").write_text("{}")
    lane.restart_lane()
    assert calls[0][-1] == "window-restore"
