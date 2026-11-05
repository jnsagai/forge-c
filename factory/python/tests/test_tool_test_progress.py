"""Owner 2026-11-01: "I want to know how many tests to run, and from those how many already ran, in the form of a
progress bar" - the test tools write a display-only progress record while they run and the floor's Tool station shows
it as a done/total bar."""
import json
import sys
from pathlib import Path

from forge_factory.common import REPO_ROOT
from forge_factory.lrtx import floor_api as F
from forge_factory.mcp.servers import tests
from test_factory_floor import NOW, _order, _tools  # noqa: F401
from test_m2_mcp import call, ws  # noqa: F401 - fixture


def test_run_unit_records_how_many_tests_ran_of_how_many(ws):  # noqa: F811
    out = call(tests, "forge-tests-mcp", "run_unit", {}, "swe4-author", "SWE.4")
    rec = json.loads(tests.progress_path(ws, "SWE.4", "run_unit").read_text())
    assert out["status"] == "PASS" and rec["total"] >= 1 and rec["done"] == rec["total"] and rec["running"] is False
    assert rec["passed"] == rec["total"] and rec["failed"] == 0 and rec["unit"] == "tests"


def test_the_robot_listener_counts_tests_as_they_end(tmp_path):
    sys.path.insert(0, str(REPO_ROOT / "factory/sim/stm32n6"))
    from forge_robot_progress import Progress

    p = tmp_path / "SWE.6-run_robot.json"
    p.write_text(json.dumps({"op": "run_robot", "phase": "SWE.6", "unit": "tests"}))
    lst = Progress(str(p))

    class D:  # robot data/result stand-ins
        def __init__(self, **k):
            self.__dict__.update(k)

    lst.start_suite(D(longname="Suite", test_count=3), D())
    lst.start_suite(D(longname="Suite.Child", test_count=1), D())  # a child suite does not reset the total
    lst.end_test(D(), D(status="PASS"))
    lst.end_test(D(), D(status="FAIL"))
    rec = json.loads(p.read_text())
    assert (rec["total"], rec["done"], rec["passed"], rec["failed"], rec["running"]) == (3, 2, 1, 1, True)
    assert rec["op"] == "run_robot"


def test_the_tool_station_shows_the_running_tool_tests_bar(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    ws_ = _order(tmp_path, "WO-TP", [{"phase": "SWE.5", "step": "inspect", "gate": {"decision": "PASS"}}], package=False,
                 stop_after="SWE.6", visit="SWE.6", packets=[("SWE.6", "scenario:startup", "VALID", 1)])
    d = ws_ / ".forge-run/tool-progress"
    d.mkdir(parents=True)
    (d / "SWE.6-run_robot.json").write_text(json.dumps({"op": "run_robot", "phase": "SWE.6", "unit": "tests", "total": 10,
                                                         "done": 7, "passed": 6, "failed": 1, "running": True,
                                                         "updated": NOW - 5}))
    hall = next(h for h in F.floor(now=NOW, since=NOW - 86400)["halls"] if h["id"] == "SWE.6")
    t = next(c for c in hall["cells"] if c["id"] == "tools")["bar"]["tests"]
    assert (t["label"], t["done"], t["total"], t["passed"], t["failed"], t["running"]) == \
        ("target tests (Renode)", 7, 10, 6, 1, True)
