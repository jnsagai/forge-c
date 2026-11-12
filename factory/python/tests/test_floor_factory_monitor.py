"""The existing floor observes authority and execution separately; it never starts work."""
import json
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest
from forge_factory.lrtx import factory_monitor as M


def feed(now, mode="OBSERVE"):
    return {"available": True, "age_s": 3, "generated_at": M.iso(now - 3),
            "supervisor": {"mode": mode, "pid": 123, "unit": "forge-line-conductor-local.service",
                           "model_calls_healthy": 0}, "issues": [], "placement": {"mode": "OBSERVING"}}


def setup(tmp_path, monkeypatch, now=1000):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("FORGE_FLOOR_SUPERVISOR_FEED", str(tmp_path / "supervisor/issues.json"))
    intent = tmp_path / "private-intent.json"
    intent.write_text(json.dumps({"mode": "RUNNING", "epoch": 1}))
    monkeypatch.setenv("FORGE_FLOOR_OPERATIONS_INTENT", str(intent))
    (tmp_path / "supervisor").mkdir()
    (tmp_path / "supervisor/line-conductor.heartbeat").write_text(json.dumps(
        {"epoch": now - 3, "pid": 123, "mode": "OBSERVE", "ok": True, "cycle": 8}))
    monkeypatch.setattr(M, "process_observation", lambda pid, unit: {"state": "PRESENT", "pid": pid})
    return tmp_path / "supervisor/line-queue.sqlite3"


def test_observe_and_running_intent_are_not_fake_product_work(tmp_path, monkeypatch):
    db = setup(tmp_path, monkeypatch)
    result = M.snapshot(feed(1000), [], {}, None, now=1000)
    assert result["operations"] == {"desired": "RUNNING", "epoch": 1, "available": True}
    assert result["conductor"]["observed_mode"] == "OBSERVE"
    assert result["conductor"]["readiness"] == "OBSERVING"
    assert result["work"]["driver_activity"] == "NO_CURRENT_DRIVER_OBSERVED"
    assert result["work"]["jobs"]["available"] is False
    assert not db.exists()  # status cannot initialize a queue or mission
    assert result["throughput"]["tok_s"] is None
    assert result["conductor"]["model_calls_healthy"] == 0


def test_stale_or_future_heartbeat_never_claims_readiness(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    path = tmp_path / "supervisor/line-conductor.heartbeat"
    for epoch in (1, 2000):
        path.write_text(json.dumps({"epoch": epoch, "pid": 123, "mode": "OBSERVE", "ok": True}))
        result = M.snapshot(feed(1000), [], {}, None, now=1000)
        assert result["conductor"]["readiness"] == "UNKNOWN"
        assert result["conductor"]["heartbeat"]["fresh"] is False


def test_stale_feed_is_not_a_healthy_observer(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    result = M.snapshot({"available": False, "reason": "FEED_STALE", "age_s": 999}, [], {}, None, now=1000)
    assert result["conductor"]["readiness"] == "UNKNOWN"
    assert result["conductor"]["observed_mode"] is None
    assert result["connection"]["source_state"] == "STALE"


def test_live_execution_remains_visible_after_task_blocked_and_never_leaks_payload(tmp_path, monkeypatch):
    db = setup(tmp_path, monkeypatch)
    with sqlite3.connect(db) as c:
        c.executescript("""CREATE TABLE afo_product_jobs(job_id TEXT, record TEXT);
            CREATE TABLE afo_local_agent_jobs(job_id TEXT, record TEXT);
            CREATE TABLE afo_execution_liveness(job_id TEXT, record TEXT);
            CREATE TABLE afo_work_orders(order_id TEXT,request_id TEXT);""")
        c.execute("INSERT INTO afo_work_orders VALUES (?,?)", ("afo-001", "WO-F014-SWE6-CRC-TEST"))
        c.execute("INSERT INTO afo_product_jobs VALUES (?,?)", ("job-001", json.dumps(
            {"job_id": "job-001", "order_id": "afo-001", "model": "ornith:35b", "nonce": "SECRET",
             "prompt": "PRIVATE", "role": "swe6-author"})))
        c.execute("INSERT INTO afo_execution_liveness VALUES (?,?)", ("job-001", json.dumps(
            {"task_outcome": "BLOCKED", "resource_lease": "HELD", "execution_liveness": "RUNNING",
             "last_reconciled_at": M.iso(998), "terminal_reason": "NEEDS_REVIEW"})))
    before = db.read_bytes()
    result = M.snapshot(feed(1000), [], {}, None, now=1000)
    job = result["work"]["jobs"]["items"][0]
    assert job["task_outcome"] == "BLOCKED" and job["execution_liveness"] == "RUNNING"
    assert job["resource_lease"] == "HELD" and job["phase"] == "SWE.6"
    assert job["execution_fresh"] is True
    assert "SECRET" not in json.dumps(result) and "PRIVATE" not in json.dumps(result)
    assert db.read_bytes() == before


def test_recent_speed_is_labelled_measurement_not_current_job_speed(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    measurement = {"tok_s": 122, "model": "qwen:27b", "age_s": 15, "calls": 2,
                   "basis": "gateway per-call output tokens / latency"}
    result = M.snapshot(feed(1000), [], {"available": False, "model": "ornith:35b"}, measurement, now=1000)
    assert result["throughput"]["tok_s"] == 122
    assert result["throughput"]["model"] == "qwen:27b"
    assert result["throughput"]["kind"] == "RECENT_CALL_MEASUREMENT"
    assert result["model"]["fresh"] is False


def test_running_driver_and_repair_issue_are_distinct_observations(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    supervisor = feed(1000)
    supervisor["issues"] = [{"issue_id": "SUP-001", "status": "ESCALATED", "class": "MODEL_CONVERGENCE",
                             "phase": "SWE.6", "error_code": "REQUIRED_TOOL_NOT_PASS:run_robot",
                             "summary": "DO_NOT_EXPOSE_UNBOUNDED_PROSE"}]
    orders = [{"wo": "WO-F014-SWE6-CRC", "state": "RUNNING", "at": "SWE.6",
               "node": {"node": "swe6_author", "cell": "author", "model": "ornith:35b"},
               "phases": {"SWE.6": {"reworks": 2}}}]
    result = M.snapshot(supervisor, orders, {}, None, now=1000)
    assert result["work"]["drivers"][0]["agent"] == "author"
    assert result["work"]["drivers"][0]["reworks"] == 2
    assert result["recovery"]["issues"][0]["status"] == "ESCALATED"
    assert "DO_NOT_EXPOSE" not in json.dumps(result)


def test_failed_swap_target_and_legacy_record_are_not_current_loaded_model(tmp_path, monkeypatch):
    from forge_factory.lrtx import floor_api as F

    state = tmp_path / "state"
    monkeypatch.setenv("FORGE_STATE_DIR", str(state))
    (state / "llm-gateway").mkdir(parents=True)
    (tmp_path / "run").mkdir()
    (state / "llm-gateway/usage.jsonl").write_text(json.dumps({"sample": {"ts": 998, "gpu": {}}}) + "\n")
    path = tmp_path / "run/model-swaps.jsonl"
    path.write_text(json.dumps({"at": M.iso(998), "to": "qwen:27b", "result": "FAILED"}) + "\n")
    assert F.station(1000)["model"] is None
    path.write_text(json.dumps({"to": "legacy-model"}) + "\n")
    station = F.station(1000)
    assert station["model"] == "legacy-model" and station["model_verified"] is False
    assert M.snapshot({}, [], station, None, now=1000)["model"]["fresh"] is False


def test_unknown_queue_schema_and_corrupt_row_do_not_become_idle(tmp_path, monkeypatch):
    db = setup(tmp_path, monkeypatch)
    with sqlite3.connect(db) as c:
        c.execute("CREATE TABLE unrelated(x)")
    assert M.snapshot(feed(1000), [], {}, None, now=1000)["work"]["jobs"]["available"] is False


def test_readiness_cannot_infer_active_authority_from_a_pilot_label(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch)
    supervisor = feed(1000, "PILOT")
    path = tmp_path / "supervisor/line-conductor.heartbeat"
    path.write_text(json.dumps({"epoch": 998, "pid": 123, "mode": "PILOT", "ok": True}))
    assert M.snapshot(supervisor, [], {}, None, now=1000)["conductor"]["readiness"] == "UNKNOWN"
    supervisor["placement"]["mode"] = "ACTING"
    assert M.snapshot(supervisor, [], {}, None, now=1000)["conductor"]["readiness"] == "ACTING"
    monkeypatch.delenv("FORGE_FLOOR_OPERATIONS_INTENT")
    assert M.snapshot(supervisor, [], {}, None, now=1000)["conductor"]["readiness"] == "UNKNOWN"


def test_actual_frontend_monitor_labels_unknown_and_disconnect_without_live_animation():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is not installed: frontend execution NOT_RUN")
    page = Path(M.__file__).parents[1] / "dashboard/static/factory-floor.html"
    html = page.read_text()
    source = html[html.index("function renderRuntime(d)"):html.index("function render() {")]
    esc = next(line for line in html.splitlines() if line.startswith("const esc ="))
    fixture = """
const elements = new Map(); const $ = (id) => { if (!elements.has(id)) elements.set(id, {}); return elements.get(id); };
const classes = new Set(); const document = {body: {classList: {add: (x) => classes.add(x)}}};
""" + esc + "\n" + source + """
renderRuntime({monitor:{operations:{desired:'RUNNING',epoch:1},conductor:{observed_mode:'OBSERVE',readiness:'OBSERVING',model_calls_healthy:0},
 connection:{reachable:true,source_state:'CURRENT',feed_age_s:3},work:{drivers:[],jobs:{available:false}},throughput:{tok_s:null}}});
const text = $('#runtime-monitor').innerHTML;
if (!text.includes('Observing only; no orders are placed.') || !text.includes('Operations RUNNING does not imply a running job.') || !text.includes('No recent completed-call measurement; not zero.')) throw Error('false activity/speed label');
renderRuntime({monitor:{operations:{desired:'<PRIVATE>'},work:{drivers:[],jobs:{available:false}}}});
if ($('#runtime-monitor').innerHTML.includes('<PRIVATE>')) throw Error('unescaped data');
disconnectedRuntime();
if (!classes.has('telemetry-stale') || !$('#runtime-connection').textContent.includes('DISCONNECTED')) throw Error('stale connection not shown');
"""
    subprocess.run([node, "-e", fixture], check=True, capture_output=True, text=True, timeout=5)
    assert ".telemetry-stale .conveyor" in html and "animation-play-state: paused" in html
