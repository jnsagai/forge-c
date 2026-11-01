"""CAPA-099 (run WO-F014-SWE6-OBL-20261101-L5): SWE.5/SWE.6 test and code declarations quote the cited requirement's own
text (the model's reason was refused: REQUIREMENT_QUOTE_REQUIRED), and a failing scenario re-authored by a rework visit
is declared TEST before it runs again (it was left undeclared and blocked a 10/10 passing run)."""
import json

from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe6, tools
from forge_factory.lrtx import visit as V

REQ = "While no LL function has been called after reset, the CRC LL driver shall not write any CRC register."


def _ws(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws = tmp_path / "WO-T/workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": "WO-T", "layer": "LL", "peripheral": "crc"}))
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(f"# Software requirements\n\n- **SWR-003** {REQ}\n")
    (ws / "software/tests/software").mkdir(parents=True)
    (ws / "software/tests/software/scn_startup.c").write_text("/* scenario */\n")
    monkeypatch.setattr(swe6, "plan", lambda _ws: {"topics": {"startup": ["SWR-003"]}})
    monkeypatch.setattr(swe6, "scn_files", lambda t: ("software/tests/software/scn_startup.c", "software/tests/software/x.c"))
    monkeypatch.setattr(swe6, "_context", lambda *_a: [])
    monkeypatch.setattr(swe6, "_write", lambda *_a: None)
    monkeypatch.setattr(swe6, "validate_scenarios", lambda *_a: [])
    monkeypatch.setattr(S, "record", lambda *_a: None)
    monkeypatch.setattr(swe6.V, "reply", lambda _ws, _ph, status, issues, *_a, **_k: {"status": status, "issues": issues})
    return ws


def _decls(ws):
    return [json.loads(p.read_text()) for p in sorted((ws / ".forge-run/defects").glob("DEF-*.json"))]


def test_the_quote_is_the_cited_requirement_text(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch)
    assert V.requirement_quote(ws, ["SWR-999", "SWR-003"], "reason") == REQ
    assert V.requirement_quote(ws, [], "the reason") == "the reason"


def test_a_failing_scenario_rewritten_by_rework_is_declared_before_it_runs(tmp_path, monkeypatch):
    ws = _ws(tmp_path, monkeypatch)
    (ws / "evidence").mkdir()
    (ws / "evidence/tool-results.jsonl").write_text(json.dumps({"op": "run_robot", "phase": "SWE.6", "result": {
        "status": "FAIL", "issues": ["ROBOT_FAIL:SWR-003:check 3 failed in scn_startup.c [default]"]}}) + "\n")
    ck = V._ckpt(ws, "SWE.6", "scenario:startup")
    ck.parent.mkdir(parents=True, exist_ok=True)
    ck.write_text(json.dumps({"task": "scenario:startup", "status": "VALID", "doc": {"default_code": "old"}}))
    monkeypatch.setattr(swe6.V, "run_task", lambda *_a, **_k: {"task": "scenario:startup", "status": "VALID",
                                                               "doc": {"default_code": "new"}, "errors": []})
    monkeypatch.setattr(tools, "call", lambda *_a, **_k: {"status": "PASS", "summary": "robot: 1/1", "issues": []})
    rep = swe6._visit_tests(ws, "m", {"calls": 0, "max_calls": 5, "log": []},
                            ["run_robot: ROBOT_FAIL:SWR-003:check 3 failed in scn_startup.c [default]"])
    d = _decls(ws)
    assert rep["status"] == "PASS" and len(d) == 1 and d[0]["kind"] == "TEST"
    assert d[0]["requirement_ids"] == ["SWR-003"] and list(d[0]["test_files"]) == ["software/tests/software/scn_startup.c"]
