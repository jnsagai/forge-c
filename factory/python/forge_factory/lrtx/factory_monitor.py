"""Private read-only runtime observations for the EXISTING Plant Floor.

Service intent, observation mode, native liveness and product outcome are separate
facts. This module never initializes a store, authorizes work or calls a model.
Only allowlisted metadata leaves this boundary; job payloads and prose do not.
"""
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import time
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

FRESH_S = 180
MAX_RECORD = 131072
RECORD_QUERIES = {
    "afo_product_jobs": "SELECT job_id,substr(record,1,131073) FROM afo_product_jobs ORDER BY rowid DESC LIMIT 101",
    "afo_local_agent_jobs": "SELECT job_id,substr(record,1,131073) FROM afo_local_agent_jobs ORDER BY rowid DESC LIMIT 101",
    "afo_execution_liveness": "SELECT job_id,substr(record,1,131073) FROM afo_execution_liveness ORDER BY rowid DESC LIMIT 101",
}


def iso(epoch):
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _text(value, limit=160):
    return value if (isinstance(value, str) and 0 < len(value) <= limit and re.fullmatch(r"[\w./:@=+-]+", value)
                     and not re.search(r"(?i)(?:sk-|api[_-]?key=|bearer|secret=|token=)", value)) else None


def _json(path):
    if not path or not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_RECORD:
        return None
    try:
        value = json.loads(path.read_bytes())
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def _epoch(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def _fresh(epoch, now):
    return _number(epoch) and 0 <= now - epoch <= FRESH_S


def process_observation(pid, unit):
    """Kernel identity of this user's exact conductor, not a service-control call."""
    if type(pid) is not int or pid <= 1 or not _text(unit):
        return {"state": "UNKNOWN", "pid": None}
    root = Path("/proc") / str(pid)
    try:
        before = root.joinpath("stat").read_text().rsplit(")", 1)[1].split()[19]
        argv = root.joinpath("cmdline").read_bytes().split(b"\0")
        cgroup = root.joinpath("cgroup").read_text()
        after = root.joinpath("stat").read_text().rsplit(")", 1)[1].split()[19]
        present = (before == after and root.stat().st_uid == os.getuid()
                   and b"forge_factory.afo.line_conductor" in argv and unit in cgroup)
        requested = argv[argv.index(b"--mode") + 1].decode() if b"--mode" in argv else None
    except (OSError, IndexError, ValueError):
        present, requested = False, None
    return {"state": "PRESENT" if present else "UNKNOWN", "pid": pid,
            "requested_mode": requested if present and requested in ("OBSERVE", "ACT") else None}


def _jobs(root, now):
    path = root / "supervisor/line-queue.sqlite3"
    if not path.is_file() or path.is_symlink():
        return {"available": False, "reason": "QUEUE_NOT_OBSERVED", "items": []}
    try:
        until = time.monotonic() + .25
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=.2)) as db:
            db.set_progress_handler(lambda: int(time.monotonic() > until), 1000)
            tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {"afo_execution_liveness", "afo_work_orders"} <= tables:
                return {"available": False, "reason": "QUEUE_SCHEMA_NOT_OBSERVED", "items": []}
            records, executions, orders, truncated = {}, {}, {}, False
            if "afo_work_orders" in tables:
                orders = dict(db.execute("SELECT order_id,request_id FROM afo_work_orders ORDER BY rowid DESC LIMIT 2000"))
            for table in ("afo_product_jobs", "afo_local_agent_jobs", "afo_execution_liveness"):
                if table not in tables:
                    continue
                rows = db.execute(RECORD_QUERIES[table]).fetchall()
                truncated |= len(rows) > 100
                for jid, raw in rows[:100]:
                    if len(raw) > MAX_RECORD:
                        raise ValueError("record bound")
                    value = json.loads(raw)
                    if not isinstance(value, dict):
                        raise ValueError("record shape")
                    (executions if table == "afo_execution_liveness" else records)[jid] = value
            items = []
            for jid in records.keys() | executions.keys():
                record, execution = records.get(jid, {}), executions.get(jid, {})
                wo = _text(orders.get(record.get("order_id")))
                phase = re.search(r"(?:^|-)SWE([1-6])(?:-|$)", wo or "")
                items.append({"job_id": _text(jid), "work_order": wo,
                              "role": _text(record.get("role")), "requested_model": _text(record.get("model")),
                              "phase": f"SWE.{phase[1]}" if phase else None,
                              "task_outcome": _text(execution.get("task_outcome")),
                              "execution_liveness": _text(execution.get("execution_liveness")),
                              "resource_lease": _text(execution.get("resource_lease")),
                              "terminal_reason": _text(execution.get("terminal_reason")),
                              "execution_fresh": _fresh(_epoch(execution.get("last_reconciled_at")), now)})
            items.sort(key=lambda j: (j["resource_lease"] != "HELD", j["job_id"] or ""))
            return {"available": True, "inventory_complete": not truncated and len(items) <= 20,
                    "held_observed": sum(j["resource_lease"] == "HELD" for j in items), "items": items[:20]}
    except (OSError, ValueError, TypeError, sqlite3.Error):
        return {"available": False, "reason": "QUEUE_OBSERVATION_UNKNOWN", "items": []}


def snapshot(supervisor, orders, station, speed, *, now=None):
    now = time.time() if now is None else now
    root = Path(os.environ.get("FORGE_STATE_DIR") or "state")
    intent_path = os.environ.get("FORGE_FLOOR_OPERATIONS_INTENT") or os.environ.get("FORGE_OPERATIONS_INTENT")
    intent = _json(Path(intent_path)) if intent_path else None
    mode = (intent or {}).get("mode")
    if mode not in ("RUNNING", "PAUSED", "DRAINING", "STOPPED"):
        mode = None
    operations = {"desired": mode, "epoch": (intent or {}).get("epoch") if type((intent or {}).get("epoch")) is int else None,
                  "available": mode is not None}
    feed_path = os.environ.get("FORGE_FLOOR_SUPERVISOR_FEED")
    heartbeat = _json(Path(feed_path).with_name("line-conductor.heartbeat")) if feed_path else None
    sv = supervisor.get("supervisor") or {}
    feed_fresh = (supervisor.get("available") is True and _number(supervisor.get("age_s"))
                  and 0 <= supervisor["age_s"] <= FRESH_S)
    hb_epoch = (heartbeat or {}).get("epoch")
    hb_fresh = (_fresh(hb_epoch, now) and (heartbeat or {}).get("pid") == sv.get("pid")
                and (heartbeat or {}).get("mode") == sv.get("mode"))
    proc = process_observation(sv.get("pid"), sv.get("unit")) if feed_fresh else {"state": "UNKNOWN", "pid": None}
    observed = _text(sv.get("mode")) if feed_fresh else None
    ready = "UNKNOWN"
    if feed_fresh and hb_fresh and heartbeat.get("ok") is True and proc["state"] == "PRESENT":
        acting = (observed == "PILOT" and mode == "RUNNING"
                  and (supervisor.get("placement") or {}).get("mode") == "ACTING")
        ready = "OBSERVING" if observed == "OBSERVE" else "ACTING" if acting else "UNKNOWN"
        if mode in ("STOPPED", "PAUSED", "DRAINING"):
            ready = mode
    drivers = []
    for order in orders:
        if order.get("state") != "RUNNING":
            continue
        node = order.get("node") or {}
        drivers.append({"work_order": _text(order.get("wo")), "phase": _text(order.get("at")),
                        "agent": _text(node.get("cell")), "node": _text(node.get("node")),
                        "observed_model": _text(node.get("model")),
                        "reworks": sum(p.get("reworks", 0) for p in order.get("phases", {}).values())})
    issues = [{k: _text(i.get(k)) for k in ("issue_id", "status", "class", "phase", "error_code")}
              for i in supervisor.get("issues") or [] if i.get("status") != "RESOLVED"]
    measured = (isinstance(speed, dict) and _number(speed.get("tok_s")) and speed["tok_s"] >= 0
                and _number(speed.get("age_s")) and 0 <= speed["age_s"] <= 600)
    source_state = "CURRENT" if feed_fresh else "STALE" if supervisor.get("reason") == "FEED_STALE" else "UNKNOWN"
    swap_basis = "LAST_SUCCESSFUL_SWAP_RECORD" if station.get("model_verified") else "UNVERIFIED_OR_MISSING_SWAP_RECORD"
    return {"schema": "forge-c/factory-runtime-monitor/1", "observed_at": iso(now),
            "connection": {"source_state": source_state,
                           "feed_age_s": supervisor.get("age_s"), "feed_at": supervisor.get("generated_at")},
            "operations": operations,
            "conductor": {"requested_mode": proc.get("requested_mode"), "observed_mode": observed,
                          "readiness": ready, "process": proc,
                          "heartbeat": {"fresh": hb_fresh, "age_s": round(now - hb_epoch) if _number(hb_epoch) else None},
                          "model_calls_healthy": sv.get("model_calls_healthy") if feed_fresh else None},
            "model": {"last_reported_loaded": _text(station.get("model")),
                      "fresh": station.get("available") is True and station.get("model_verified") is True
                      and _number(station.get("model_age_s"))
                      and 0 <= station["model_age_s"] < 120,
                      "age_s": station.get("model_age_s"),
                      "basis": swap_basis},
            "throughput": {"tok_s": speed["tok_s"] if measured else None,
                           "model": _text(speed.get("model")) if measured else None,
                           "age_s": speed.get("age_s") if measured else None,
                           "kind": "RECENT_CALL_MEASUREMENT" if measured else "UNKNOWN"},
            "work": {"driver_activity": "OBSERVED" if drivers else "NO_CURRENT_DRIVER_OBSERVED",
                     "drivers": drivers[:20], "jobs": _jobs(root, now)},
            "recovery": {"open_observed": len(issues), "issues": issues[:20]}}
