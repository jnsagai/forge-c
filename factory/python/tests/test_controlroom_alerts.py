"""CR-T033: alerts - each condition, stable ids (updated, not duplicated), violations not filterable and forcing
VIOLATION, no server-side acknowledgement."""
from datetime import datetime

from controlroom_fixtures import CFG, FakeProbe, inspect, passed, rejected, route, workspace
from forge_factory.controlroom.alerts import collect, from_quality, from_scorecard
from forge_factory.controlroom.floor import Floor

NOW = datetime.fromisoformat("2026-10-19T12:30:00+00:00").timestamp()


def _floor(root, now=NOW):
    return Floor(root=root, probe=FakeProbe(last_ts="2026-10-19T12:29:00Z")).snapshot(CFG, now=now)


def _conds(res):
    return sorted(a["condition"] for a in res["alerts"])


def test_station_blocked_and_rework_budget_near(tmp_path):
    workspace(tmp_path, "WO-A-r1", [*passed("SWE.1", 1), route("SWE.2", 5, "BLOCKED", "rework budget exhausted")])
    workspace(tmp_path, "WO-B-r1", [*passed("SWE.1", 1), inspect("SWE.2", 4, "REWORK"), route("SWE.2", 5),
                                    rejected("SWE.2", 7), route("SWE.2", 8)])
    res = collect(_floor(tmp_path), CFG)
    assert _conds(res) == ["REWORK_BUDGET_NEAR", "STATION_BLOCKED"]
    blk = next(a for a in res["alerts"] if a["condition"] == "STATION_BLOCKED")
    assert blk["severity"] == "critical" and blk["reason"] == "SWE.2: rework budget exhausted" and blk["filterable"]
    near = next(a for a in res["alerts"] if a["condition"] == "REWORK_BUDGET_NEAR")
    assert near["reason"] == "SWE.2: 2 of 3 rework cycles used"


def test_same_condition_keeps_its_id_and_is_not_duplicated(tmp_path):
    ws = workspace(tmp_path, "WO-A-r1", [*passed("SWE.1", 1), route("SWE.2", 5, "BLOCKED", "x")])
    f = Floor(root=tmp_path, probe=FakeProbe(last_ts="2026-10-19T12:29:00Z"))
    a1 = collect(f.snapshot(CFG, now=NOW), CFG)["alerts"]
    from controlroom_fixtures import append

    append(ws, route("SWE.2", 6, "BLOCKED", "x"))
    a2 = collect(f.snapshot(CFG, now=NOW + 30), CFG)["alerts"]
    assert [a["alert_id"] for a in a1] == [a["alert_id"] for a in a2] and len(a2) == 1


def test_lead_time_and_stale_feed(tmp_path):
    workspace(tmp_path, "WO-L-r1", passed("SWE.1", 1), created="2026-10-19T04:00:00Z")
    res = collect(_floor(tmp_path), CFG)
    assert "LEAD_TIME_OVER_LIMIT" in _conds(res)
    stale = {**_floor(tmp_path), "stale": True, "data_age_s": 900}
    assert "FEED_STALE" in _conds(collect(stale, CFG))


def test_safety_violation_is_critical_unfilterable_and_forces_violation_status(tmp_path):
    sc = {"status": "OK", "window": {"kind": "today", "start_utc": "2026-10-18T23:00:00Z"},
          "kpis": [{"metric_id": "K20", "display": "VALUE", "status": "MEASURED", "value": 2.0, "evidence_refs": ["e1"]},
                   {"metric_id": "K02", "display": "VALUE", "status": "MEASURED", "value": 0.3, "sample_count": 25,
                    "filters": {"phase": "SWE.4"}}]}
    al = from_scorecard(sc, CFG)
    v = next(a for a in al if a["condition"] == "SAFETY_PROCESS_VIOLATION")
    assert v["severity"] == "critical" and v["filterable"] is False
    assert any(a["condition"] == "YIELD_BELOW_THRESHOLD" and "SWE.4" in a["reason"] for a in al)
    workspace(tmp_path, "WO-A-r1", passed("SWE.1", 1))
    snap = Floor(root=tmp_path, probe=FakeProbe()).snapshot(CFG, now=NOW, violations_open=1)
    res = collect(snap, CFG, sc)
    assert snap["factory_status"] == "VIOLATION" and res["violations_open"] == 1
    assert res["alerts"][0]["condition"] == "SAFETY_PROCESS_VIOLATION"           # critical first


def test_yield_out_of_control_only_for_the_latest_point():
    pts = [{"t": f"d{i}"} for i in range(12)]
    q = {"charts": {"SWE.3": {"first_pass_yield": {"status": "OK", "points": pts,
                                                    "violations": [{"rule": "WE1", "point_index": 11}]}},
                    "SWE.4": {"first_pass_yield": {"status": "OK", "points": pts,
                                                    "violations": [{"rule": "WE1", "point_index": 3}]}}}}
    assert [a["subject"]["station"] for a in from_quality(q)] == ["SWE.3"]


def test_no_acknowledgement_route_on_the_server(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    from fastapi.testclient import TestClient
    from forge_factory.controlroom import config as C
    from forge_factory.dashboard.app import create_app, tokens

    monkeypatch.setattr(C, "load", lambda path=None: dict(CFG))
    app = create_app(collect=False, control_room_floor=Floor(root=tmp_path / "wo", probe=FakeProbe()))
    assert not [r for r in app.routes if any(s.startswith("ack") for s in getattr(r, "path", "").split("/"))]
    c = TestClient(app)
    r = c.get("/api/v1/control-room/alerts", headers={"Authorization": f"Bearer {tokens()['viewer']}"})
    assert r.status_code == 200 and r.json()["alerts"] == [] and "browser only" in r.json()["acknowledgement"]
