"""Owner decision 2026-10-18 (config/factory/rework-policy.yaml): after the authored 3 failed cycles a phase gets up
to 2 more, one at a time, only while it measurably progresses; growing, identical or regressing cycles BLOCK as
before, and the CAPA-014 stuck rule still stops a phase early."""
import json

from forge_factory.inspection import gate as G
from forge_factory.inspection.engine import Store


def _ws(tmp_path):
    ws = tmp_path / "ws"
    (ws / ".forge-run/gates").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL", "created_at": "2026-10-18T00:00:00Z"}))
    return ws


def _rej(ws, n, *issues):
    with (ws / ".forge-run/gates/gate-log.jsonl").open("a") as fh:
        fh.write(json.dumps({"phase": "SWE.4", "ts": f"2026-10-18T10:0{n}:00Z", "step": "author", "result": "REJECTED",
                             "issues": list(issues)}) + "\n")


def _ins(ws, n, *findings):
    d = ws / "inspection/SWE.4"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"INS-SWE.4-{n:03d}.json").write_text(json.dumps({
        "inspection_id": f"INS-SWE.4-{n:03d}", "verdict": "FAIL", "recorded_at": f"2026-10-18T11:0{n}:00Z",
        "baseline_hash": "x", "findings": [{"id": c, "severity": "major", "detail": d} for c, d in findings]}))


def _route(ws):
    rc = G.step_route(Store(ws), "SWE.4")
    last = [json.loads(x) for x in (ws / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()][-1]
    return rc, last["gate"]


def test_progress_rule_cases(tmp_path):
    ws = _ws(tmp_path)
    s = Store(ws)
    _rej(ws, 1, "REQUIRED_TOOL_NOT_PASS:run_unit", "UT:TEST_NOT_OBSERVED:UT-003")
    _ins(ws, 1, ("SWE4-02", "UT-007 expects the DEF-004 behaviour"))
    assert G.progressing(s, "SWE.4", "")["progress"] is True                 # gates passed, reached inspection
    _ins(ws, 2, ("SWE4-02", "UT-009 asserts abstract bits"))
    p = G.progressing(s, "SWE.4", "")
    assert p["progress"] is True and "SWE4-02@DEF-004,UT-007" in p["resolved"]  # same check id, another item
    _ins(ws, 3, ("SWE4-02", "UT-009 is vacuous"), ("SWE4-06", "UT-006 bound"))
    assert G.progressing(s, "SWE.4", "")["progress"] is False                # findings grew 1 -> 2
    _ins(ws, 4, ("SWE4-02", "UT-009 is vacuous"), ("SWE4-06", "UT-006 bound"))
    assert G.progressing(s, "SWE.4", "")["progress"] is False                # identical
    _rej(ws, 9, "REQUIRED_TOOL_NOT_PASS:run_unit")
    assert G.progressing(s, "SWE.4", "")["progress"] is False                # inspection -> gate rejection


def test_route_extends_only_while_progressing_and_never_past_the_cap(tmp_path):
    ws = _ws(tmp_path)
    _rej(ws, 1, "CODE:DOXYGEN_WARNING:a.c:1", "CODE:DOXYGEN_WARNING:a.c:9", "UNIT:SWR_NOT_REFINED:SWR-013")
    _rej(ws, 2, "CODE:DOXYGEN_WARNING:a.c:1", "UNIT:SWR_NOT_REFINED:SWR-013")
    _rej(ws, 3, "CODE:DOXYGEN_WARNING:a.c:1", "UNIT:SWR_NOT_REFINED:SWR-014")
    rc, g = _route(ws)                                     # 3 failed cycles = authored maximum, but progressing
    assert rc == 0 and g["progress_extension"]["progress"] and g["progress_extension"]["cycle"] == 1
    _rej(ws, 4, "UNIT:SWR_NOT_REFINED:SWR-015")
    rc, g = _route(ws)
    assert rc == 0 and g["progress_extension"]["cycle"] == 2
    _rej(ws, 5, "UNIT:SWR_NOT_REFINED:SWR-016")
    rc, g = _route(ws)                                     # 5 = 3 + 2: cap reached even though still progressing
    assert rc == 1 and g["decision"] == "BLOCKED" and "progress_extension" not in g


def test_fewer_warnings_is_progress_a_moved_warning_is_not(tmp_path):
    ws = _ws(tmp_path)
    s = Store(ws)
    _rej(ws, 1, "CODE:DOXYGEN_WARNING:a.c:10:no brief", "CODE:DOXYGEN_WARNING:a.c:20:no brief")
    _rej(ws, 2, "CODE:DOXYGEN_WARNING:a.c:14:no brief")
    assert G.progressing(s, "SWE.4", "")["progress"] is True                 # 2 -> 1
    _rej(ws, 3, "CODE:DOXYGEN_WARNING:a.c:31:no brief")
    assert G.progressing(s, "SWE.4", "")["progress"] is False                # the same warning moved


def test_route_blocks_at_the_authored_maximum_without_progress(tmp_path):
    ws = _ws(tmp_path)
    _rej(ws, 1, "ARCH:NO_INTERFACES")
    _rej(ws, 2, "ARCH:NO_INTERFACES", "ARCH:NO_DYNAMIC_VIEW")
    _rej(ws, 3, "ARCH:NO_INTERFACES", "ARCH:NO_DYNAMIC_VIEW", "ARCH:NO_SWC")
    rc, g = _route(ws)
    assert rc == 1 and g["decision"] == "BLOCKED" and g["progress_extension"]["progress"] is False


def test_stuck_rule_still_stops_early_and_missing_policy_fails_closed(tmp_path, monkeypatch):
    ws = _ws(tmp_path)
    for n in (1, 2, 3):
        _rej(ws, n, "ARCH:NO_INTERFACES")
    rc, g = _route(ws)
    assert rc == 1 and g["reason"].startswith("STUCK") and "progress_extension" not in g
    monkeypatch.setattr(G, "EXTENSION_POLICY", "config/factory/does-not-exist.yaml")
    assert G.extra_cycles() == 0
