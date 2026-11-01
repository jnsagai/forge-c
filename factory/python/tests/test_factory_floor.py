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
