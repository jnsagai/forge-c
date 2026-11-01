"""Feature 007 addendum (owner 2026-11-01): the factory floor view - read-only, model-free, from recorded decisions."""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer

import pytest
from forge_factory.lrtx import floor_api as F
from forge_factory.lrtx import progress_api as P

NOW = time.time()


def _iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S.000000Z", time.gmtime(t))


def _order(root, wo, gates, *, package=True, stop_after="SWE.1", visit=None, created=None, packets=(), age=0):
    ws = root / "workorders" / wo / "workspace"
    (ws / ".forge-run/gates").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": wo, "driver": "STM32N6 IWDG LL driver",
                                                            "created_at": _iso(created or NOW - 3600 - age),
                                                            "phase_scope": {"stop_after": stop_after}}))
    t0 = NOW - 3000 - age
    (ws / ".forge-run/gates/gate-log.jsonl").write_text("".join(
        json.dumps({**g, "ts": _iso(t0 + 60 * i)}) + "\n" for i, g in enumerate(gates)))
    if package:
        (ws / ".forge-run/package.json").write_text(json.dumps({"finalized_at": _iso(t0 + 900)}))
    for phase, task, status, attempts in packets:
        d = ws / ".forge-run/lrtx" / phase / "packets"
        d.mkdir(parents=True, exist_ok=True)
        (d / (task.replace(":", "__") + ".json")).write_text(json.dumps(
            {"task": task, "status": status, "at": _iso(NOW - 60), "doc": None,
             "attempts": [{"n": i + 1, "usage": {"completion_tokens": 1400}, "wall_ms": 10000.0} for i in range(attempts)]}))
    if visit:
        p = ws / ".forge-run/lrtx" / visit / "visit-state.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"open": True, "started_at": _iso(NOW - 600), "calls": 3, "continuations": 1}))
    if age:
        for f in ws.rglob("*"):
            if f.is_file():
                os.utime(f, (NOW - age, NOW - age))
    return ws


A, I, R = "author", "inspect", "route"


@pytest.fixture
def plant(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    _order(tmp_path, "WO-DONE", [{"phase": "SWE.1", "step": A, "result": "FROZEN"},
                                 {"phase": "SWE.1", "step": I, "gate": {"decision": "REWORK"}},
                                 {"phase": "SWE.1", "step": R, "gate": {"decision": "REWORK"}},
                                 {"phase": "SWE.1", "step": A, "result": "FROZEN"},
                                 {"phase": "SWE.1", "step": I, "gate": {"decision": "PASS"}}])
    _order(tmp_path, "WO-STOP", [{"phase": "SWE.1", "step": A, "result": "FROZEN"},
                                 {"phase": "SWE.1", "step": R, "gate": {"decision": "BLOCKED", "reason": "STUCK: SAME_ITEM_FAILED_3X:SWE1-04"}}])
    _order(tmp_path, "WO-RUN", [{"phase": "SWE.1", "step": A, "result": "FROZEN"},
                                {"phase": "SWE.1", "step": I, "gate": {"decision": "PASS"}}],
           package=False, stop_after="SWE.2", visit="SWE.2",
           packets=[("SWE.2", "interfaces", "VALID", 2), ("SWE.2", "design", "INVALID", 1)])
    _order(tmp_path, "WO-YESTERDAY", [{"phase": "SWE.1", "step": A, "result": "FROZEN"}], age=2 * 86400)
    return tmp_path


def test_orders_get_a_state_and_a_plain_note(plant):
    by = {o["wo"]: o for o in F.floor(now=NOW, since=NOW - 86400)["orders"]}
    assert set(by) == {"WO-DONE", "WO-STOP", "WO-RUN"}  # an earlier shift is not counted
    assert by["WO-DONE"]["state"] == "DONE" and by["WO-DONE"]["note"] == "1 rework cycle"
    assert by["WO-STOP"]["state"] == "STOPPED" and "SAME_ITEM_FAILED_3X" in by["WO-STOP"]["note"]
    assert by["WO-RUN"]["state"] == "RUNNING" and by["WO-RUN"]["at"] == "SWE.2"
    assert by["WO-RUN"]["route"] == {"SWE.1": "ok", "SWE.2": "run"}


def test_halls_and_kpis_count_recorded_decisions_only(plant):
    d = F.floor(now=NOW, since=NOW - 86400)
    h = {x["id"]: x for x in d["halls"]}
    assert (h["SWE.1"]["entered"], h["SWE.1"]["passed"], h["SWE.1"]["first_pass"], h["SWE.1"]["inspected"]) == (3, 2, 1, 2)
    assert h["SWE.1"]["reworks"] == 1 and h["SWE.2"]["state"] == "working" and h["SWE.2"]["running"] == ["WO-RUN"]
    assert h["SWE.3"]["state"] == "idle" and h["SWE.3"]["cells"] == [] and h["SHIP"]["passed"] == 0
    k = d["kpis"]
    assert (k["on_floor"], k["completed"], k["orders"], k["stopped"], k["fpy_swe1"]) == (1, 1, 3, 1, [1, 2])
    assert k["line_tok_s"] == 140  # 3 x 1400 output tokens in 3 x 10 s


def test_the_working_cell_shows_job_progress_and_speed(plant):
    cells = {c["id"]: c for c in next(h for h in F.floor(now=NOW, since=NOW - 86400)["halls"] if h["id"] == "SWE.2")["cells"]}
    a = cells["author"]
    assert a["state"] == "working" and a["progress"]["done"] == 1 and a["progress"]["total"] == 2
    assert a["speed"]["tok_s"] == 140 and "now design" in a["job"]
    assert cells["inspector"]["state"] == "waiting" and cells["freeze"]["state"] == "waiting"


def test_the_server_serves_the_page_and_the_floor(plant):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), P.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        base = f"http://127.0.0.1:{srv.server_port}"
        page = urllib.request.urlopen(base + "/").read().decode()
        assert "<title>Forge-C Plant Floor</title>" in page and "floor.json" in page
        d = json.loads(urllib.request.urlopen(base + "/floor.json?since=" + _iso(NOW - 86400)).read())
        assert d["schema"] == "forge-c/factory-floor/1" and len(d["orders"]) == 3
    finally:
        srv.shutdown()
        srv.server_close()


def test_a_native_agent_node_shows_its_model_tokens_and_speed_from_fabro(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    ws = _order(tmp_path, "WO-NATIVE", [{"phase": "SWE.3", "step": A, "result": "REJECTED"},
                                       {"phase": "SWE.3", "step": R, "gate": {"decision": "REWORK"}}],
                package=False, stop_after="SWE.3")
    (ws / ".forge-run/fabro_run_id").write_text("RUN1")
    stages = {"swe3_author@1": {"state": "succeeded", "model": {"model_id": "qwen3.8:27b-q8_0"},
                                "usage": {"tokens": {"output": 20000}}, "timing": {"inference_time_ms": 400000}},
              "swe3_fix_author@1": {"state": "running", "model": {"model_id": "qwen3.8:27b-q8_0"}, "started_at": _iso(NOW - 900),
                                    "usage": {"tokens": {"output": 30000}}, "live_inference_ms": 600000},
              "swe3_author_gate@1": {"state": "failed", "usage": {"tokens": {"output": 0}}, "timing": {"inference_time_ms": 0}}}
    monkeypatch.setattr(F, "fabro_stages", lambda rid, finished: stages if rid == "RUN1" else None)
    d = F.floor(now=NOW, since=NOW - 86400)
    o = d["orders"][0]
    assert o["state"] == "RUNNING" and o["at"] == "SWE.3" and "swe3_fix_author" in o["note"]
    cells = {c["id"]: c for c in next(h for h in d["halls"] if h["id"] == "SWE.3")["cells"]}
    a = cells["author"]
    assert a["state"] == "working" and a["tag"] == "Qwen3.8, native agent" and "15 min" in a["job"]
    assert a["speed"]["tok_s"] == 50 and ["output tokens", 50000] in a["counters"] and ["calls", 2] in a["counters"]
    assert cells["freeze"]["state"] == "waiting" and d["kpis"]["line_tok_s"] == 50


def test_the_gpu_station_reads_the_latest_gateway_sample(tmp_path, monkeypatch):
    state = tmp_path / "state"
    (state / "llm-gateway").mkdir(parents=True)
    (tmp_path / "run").mkdir()
    sample = {"sample": {"ts": NOW - 5, "gpu": {"util_pct": 97.0, "power_w": 298.6, "temp_c": 84.0,
                                               "mem_used_mib": 46611.0, "mem_total_mib": 49140.0}}}
    (state / "llm-gateway/usage.jsonl").write_text(json.dumps({"model": "m", "tokens_output": 3}) + "\n" + json.dumps(sample) + "\n")
    (tmp_path / "run/model-swaps.jsonl").write_text(json.dumps({"to": "qwen3.8:27b-q8_0"}) + "\n")
    monkeypatch.setenv("FORGE_STATE_DIR", str(state))
    st = F.station(NOW)
    assert st["available"] is True and st["util_pct"] == 97.0 and st["model"] == "qwen3.8:27b-q8_0"
    assert F.station(NOW + 600)["available"] is False  # an old sample is not presented as live


def test_without_a_fabro_url_nothing_is_requested(monkeypatch):
    monkeypatch.delenv("FORGE_FLOOR_FABRO_URL", raising=False)
    assert F.fabro_stages("RUN1", False) is None and F.node_cell("swe2_author_more_serve@3") == "tool"
    assert [F.node_cell(n) for n in ("swe1_author_gate", "swe3_delivery_check", "swe1_inspector_more", "swe1_route")] == \
        ["freeze", "freeze", "inspector", "router"]


def test_every_cell_has_a_bar_that_says_whether_it_is_measured_or_an_estimate(plant):
    cells = {c["id"]: c for c in next(h for h in F.floor(now=NOW, since=NOW - 86400)["halls"] if h["id"] == "SWE.2")["cells"]}
    assert cells["author"]["bar"] == {"kind": "measured", "done": 1, "total": 2, "unit": "tasks", "eta": cells["author"]["bar"]["eta"]}
    assert cells["inspector"]["bar"] == {"kind": "waiting", "for": "the freeze gate"}
    idle = {c["id"]: c for c in next(h for h in F.floor(now=NOW, since=NOW - 86400)["halls"] if h["id"] == "SWE.1")["cells"]}
    assert all(c["bar"] == {"kind": "idle"} for c in idle.values())  # no order in SWE.1 now


def test_a_native_node_gets_a_time_estimate_against_its_typical_duration(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    ws = _order(tmp_path, "WO-NATIVE", [{"phase": "SWE.3", "step": A, "result": "REJECTED"}], package=False, stop_after="SWE.3")
    (ws / ".forge-run/fabro_run_id").write_text("RUN1")
    stages = {"swe3_fix_author@1": {"state": "running", "model": {"model_id": "qwen3.8:27b-q8_0"}, "started_at": _iso(NOW - 900),
                                    "usage": {"tokens": {"output": 30000}}, "live_inference_ms": 600000}}
    monkeypatch.setattr(F, "fabro_stages", lambda rid, finished: stages if rid == "RUN1" else None)
    monkeypatch.setattr(F, "history", lambda now: {"typical": {"swe3_fix_author": {"s": 600, "n": 3}},
                                                    "refs": {("STM32N6 IWDG LL driver", "SWE.3"): 5}})
    cells = {c["id"]: c for c in next(h for h in F.floor(now=NOW, since=NOW - 86400)["halls"] if h["id"] == "SWE.3")["cells"]}
    b = cells["author"]["bar"]
    assert b["kind"] == "estimate" and b["pct"] == 95 and b["over"] is True and b["typical_s"] == 600 and b["n"] == 3
    assert b["work_products"] == {"have": 0, "expect": 5}
    assert cells["freeze"]["bar"] == {"kind": "step", "step": "rejected", "decision": "REJECTED"}  # its last decision
    monkeypatch.setattr(F, "history", lambda now: {"typical": {}, "refs": {}})
    b = {c["id"]: c for c in next(h for h in F.floor(now=NOW, since=NOW - 86400)["halls"] if h["id"] == "SWE.3")["cells"]}["author"]["bar"]
    assert b["kind"] == "estimate" and "pct" not in b and b["elapsed_s"] == 900  # no earlier run: no invented percentage


def test_typical_durations_are_medians_of_finished_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    for i, secs in enumerate((300, 600, 900)):
        ws = _order(tmp_path, f"WO-H{i}", [{"phase": "SWE.3", "step": I, "gate": {"decision": "PASS"}}], stop_after="SWE.3")
        (ws / ".forge-run/fabro_run_id").write_text(f"H{i}")
    runs = {f"H{i}": {"swe3_author@1": {"state": "succeeded", "timing": {"wall_time_ms": s * 1000}}}
            for i, s in enumerate((300, 600, 900))}
    monkeypatch.setattr(F, "fabro_stages", lambda rid, finished: runs.get(rid))
    monkeypatch.setitem(F._HISTORY, "at", 0.0)
    assert F.history(NOW)["typical"]["swe3_author"] == {"s": 600, "n": 3}
