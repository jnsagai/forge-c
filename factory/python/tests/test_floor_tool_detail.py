"""Owner 2026-11-02 ("I would like to see how many tasks ran, like unit test, coverage etc"): the Tool station lists
every tool the phase author ran - runs, not-passed runs, the last status and the tool's own one-line summary, plus the
live test counts; inspector tools and other phases are not counted."""
import json

from forge_factory.lrtx import floor_api as F


def _row(phase, role, op, status, summary, metrics=None):
    return {"phase": phase, "role": role, "server": "s", "op": op, "ts_utc": "2026-11-02T08:00:00Z",
            "result": {"status": status, "summary": summary, "metrics": metrics or {}}}


def test_tool_detail_lists_every_author_tool_of_the_phase(tmp_path):
    (tmp_path / "evidence").mkdir()
    rows = [_row("SWE.4", "swe4-author", "run_unit", "FAIL", "unit: 0 passed, 1 failed (HOST)"),
            _row("SWE.4", "swe4-author", "run_unit", "PASS", "unit: 1 passed, 0 failed (HOST)"),
            _row("SWE.4", "swe4-author", "llvm_coverage", "PASS", "line 97.96% branch 100.0%"),
            _row("SWE.4", "swe4-author", "validate_trace", "PASS", "17/17 requirements traced"),
            _row("SWE.4", "swe4-inspector", "check_inspection", "PASS", "INS PASS"),
            _row("SWE.3", "swe3-author", "compile", "PASS", "2/2 units", {"relocatable_elf": True})]
    (tmp_path / "evidence/tool-results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    (tmp_path / ".forge-run/tool-progress").mkdir(parents=True)
    (tmp_path / ".forge-run/tool-progress/SWE.4-run_unit.json").write_text(json.dumps(
        {"op": "run_unit", "phase": "SWE.4", "unit": "tests", "total": 18, "done": 18, "passed": 18, "failed": 0}))
    d = F.tool_detail(tmp_path, "SWE.4")
    assert [x["tool"] for x in d] == ["unit tests", "coverage", "trace check"]
    assert d[0]["runs"] == 2 and d[0]["failed"] == 1 and d[0]["status"] == "PASS" and d[0]["tests"]["total"] == 18
    assert d[1]["summary"] == "line 97.96% branch 100.0%" and "tests" not in d[1]
    assert [x["tool"] for x in F.tool_detail(tmp_path, "SWE.3")] == ["target build"]
    assert F.tool_detail(tmp_path, "SWE.5") == []


def test_the_station_says_why_it_has_no_tool_run_yet():
    run = {"tools": {"SWE.4": []}, "progress": {"SWE.4": {}}, "tool_detail": {"SWE.4": []}, "newest_task": 0}
    cell = F._tool_cell("SWE.4", run, [run], {"done": 3, "total": 7, "unit": "tasks"})
    assert cell["detail"] == [] and "no SWE.4 tool run yet" in cell["why"] and "(3 of 7 tasks done)" in cell["why"]
    assert cell["counters"] == [["tool runs", 0], ["failed", 0], ["tools", 0]]
