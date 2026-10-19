"""CR-T017/CR-T018: scorecard - K01-K20 identical to the feature-003 engine, NOT_MEASURED for missing inputs,
READY and BLOCKED separate, cohorts never mixed silently, idempotent on replay, previous window of equal length."""
import json

import pytest
from controlroom_fixtures import CFG, passed, route, workspace
from forge_factory.controlroom.scorecard import EventCache, counts, scorecard
from forge_factory.controlroom.windows import window

PHASES = ["SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"]


def _six(m0=0):
    return [x for i, p in enumerate(PHASES) for x in passed(p, m0 + i * 10)]


@pytest.fixture()
def fx(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    root = tmp_path / "wo"
    cloud = {"default": "deepseek-flash", "provider": "deepseek", "nodes": [], "local_only": False}
    local = {"default": "qwen3:8b", "provider": "ollama", "nodes": [], "local_only": True}
    workspace(root, "WO-R-r1", _six(), package="READY_FOR_OFFLINE_REVIEW", finalized="2026-10-19T11:30:00Z", profile=local)
    workspace(root, "WO-B-r1", [*passed("SWE.1", 1), route("SWE.2", 9, "BLOCKED", "rework budget exhausted")],
              package="BLOCKED", finalized="2026-10-19T10:40:00Z", profile=cloud)
    workspace(root, "WO-W-r1", passed("SWE.1", 2), run_id=None, profile=cloud)  # still in progress
    c = EventCache(root=root, fabro=lambda ws: (None, None))
    c.warm()
    return c


def _win():
    from datetime import UTC, datetime

    return window("today", CFG, now=datetime(2026, 10, 19, 12, 0, tzinfo=UTC))


def test_kpis_are_the_engine_values_unchanged(fx):
    from forge_factory.kpi.engine import snapshot
    from forge_factory.kpi.service import load_baselines

    w = _win()
    sc = scorecard(fx, w, "all")
    ref = snapshot(fx.events("all"), w["start_utc"], w["end_utc"], "IN_PROGRESS", load_baselines())
    strip = lambda ms: [{k: v for k, v in m.items() if k not in ("display", "reason", "low_sample")} for m in ms]  # noqa: E731
    assert strip(sc["kpis"]) == ref["metric_values"] and sc["snapshot_ids"]["current"] == ref["snapshot_id"]


def test_ready_and_blocked_are_separate_and_blocked_is_not_output(fx):
    c = scorecard(fx, _win(), "all")["counts"]
    assert c["packages_ready"]["value"] == 1 and c["packages_blocked"]["value"] == 1
    assert c["started_orders"]["value"] == 3
    k04 = next(m for m in scorecard(fx, _win(), "all")["kpis"] if m["metric_id"] == "K04")
    assert k04["status"] != "MEASURED" or k04["value"] == 1          # review-ready throughput counts READY only


def test_missing_inputs_are_not_measured_with_a_reason(fx):
    ks = {m["metric_id"]: m for m in scorecard(fx, _win(), "all")["kpis"]}
    k19 = ks["K19"]                                                   # factory OEE: no calibrated baseline
    assert k19["display"] == "NOT_MEASURED" and k19["value"] is None and k19["reason"].startswith(k19["status"])
    assert all(m["display"] == "VALUE" or m["value"] is None for m in ks.values())


def test_cohorts_are_kept_apart(fx):
    prod = scorecard(fx, _win(), "production")["counts"]
    cloud = scorecard(fx, _win(), "cloud")["counts"]
    assert prod["packages_ready"]["value"] == 1 and prod["packages_blocked"]["value"] == 0
    assert cloud["packages_blocked"]["value"] == 1 and cloud["started_orders"]["value"] == 2
    assert "cloud-model runs" in scorecard(fx, _win(), "all")["cohort_note"]


def test_replay_is_idempotent(fx):
    a = scorecard(fx, _win(), "all")
    evs = fx.events("all")
    assert counts(evs + evs, _win()["start_utc"], _win()["end_utc"]) == a["counts"]
    from forge_factory.kpi.sources import dedup_sort

    assert dedup_sort(evs + evs) == evs and scorecard(fx, _win(), "all")["event_set_digest"] == a["event_set_digest"]


def test_previous_window_has_equal_length_and_warming_up_is_explicit(fx, tmp_path):
    sc = scorecard(fx, _win(), "all")
    assert sc["window"]["previous"]["end_utc"] == "2026-10-18T12:00:00Z"
    cold = EventCache(root=tmp_path / "none", fabro=lambda ws: (None, None))
    assert scorecard(cold, _win(), "all")["status"] == "WARMING_UP"


def test_scorecard_api(tmp_path, monkeypatch, fx):
    from fastapi.testclient import TestClient
    from forge_factory.controlroom import config as C
    from forge_factory.controlroom.floor import Floor
    from forge_factory.dashboard.app import create_app, tokens

    monkeypatch.setattr(C, "load", lambda path=None: dict(CFG))
    c = TestClient(create_app(collect=False, control_room_floor=Floor(root=tmp_path / "x"), control_room_events=fx))
    h = {"Authorization": f"Bearer {tokens()['viewer']}"}
    for w in ("shift", "today", "7d", "30d"):
        r = c.get(f"/api/v1/control-room/scorecard?window={w}", headers=h)
        assert r.status_code == 200 and r.json()["status"] == "OK", r.text
    assert c.get("/api/v1/control-room/scorecard?window=custom&start=2026-10-02T00:00&end=2026-10-01T00:00",
                 headers=h).status_code == 422
    assert c.get("/api/v1/control-room/scorecard?cohort=everything", headers=h).status_code == 422
    assert json.loads(c.get("/api/v1/control-room/scorecard?window=7d&cohort=production", headers=h).text)["cohort"] == \
        "production"
