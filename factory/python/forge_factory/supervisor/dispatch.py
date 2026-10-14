"""T023 — repair dispatch with two launch paths and no circular dependency on Fabro.

* Fabro healthy  -> `fabro run` of the generated repair workflow (child run, fabric-repair node).
* Fabro DOWN     -> independent local repair worker process (`forge_factory.repair.worker`), started with
                    setsid from the supervisor; it talks to the local model via the gateway and to Forge MCP
                    servers via stdio, never via Fabro.
The supervisor itself never calls a model: it only spawns a process and records the dispatch.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

from ..common import REPO_ROOT, state_dir, utc_now
from ..events.emit import emit
from .store import IncidentStore


def dispatch(inc: dict, store: IncidentStore, fabro_healthy: bool, dry_run: bool = False,
             launcher: list[str] | None = None) -> dict:
    owner = f"supervisor-{os.getpid()}"
    fresh = store.get(inc["incident_id"])
    if fresh is None or fresh["state"] != "TRIAGED":  # never act on a stale snapshot
        return {"dispatched": False, "reason": "NOT_ELIGIBLE_STATE"}
    if not store.acquire_lease(inc["incident_id"], owner):
        return {"dispatched": False, "reason": "LEASE_HELD"}
    inc = fresh
    attempt_id = f"att-{uuid.uuid4().hex[:12]}"
    path = "fabro_child_run" if fabro_healthy and inc["component"] != "fabro" else "external_local_worker"
    store.transition(inc["incident_id"], "REPAIRING", f"dispatch {attempt_id} via {path}",
                     attempts=inc["attempts"] + 1)
    rec = {"attempt_id": attempt_id, "incident_id": inc["incident_id"], "agent_role": "fabric-repair",
           "status": "PROPOSED", "worktree_ref": f"worktree:repair-{attempt_id}", "tests": [],
           "protected_path_changes": [], "token_usage": {"total": None, "basis": "unknown"}, "started_at": utc_now()}
    store.record_attempt(rec)
    d = state_dir() / "repair" / attempt_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "dispatch.json").write_text(json.dumps({"incident_id": inc["incident_id"], "attempt_id": attempt_id,
                                                 "path": path, "dispatched_at": utc_now()}, indent=2))
    emit("supervisor", "WARN", f"repair {attempt_id} dispatched via {path}", incident_id=inc["incident_id"],
         correlation_id=inc["correlation_id"])
    if dry_run:
        return {"dispatched": True, "attempt_id": attempt_id, "path": path, "pid": None}
    argv = launcher or [sys.executable, "-m", "forge_factory.repair.worker", "--incident", inc["incident_id"],
                        "--attempt", attempt_id, "--path", path]
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "factory" / "python")}
    with open(d / "worker.log", "ab") as log:
        p = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env,
                             start_new_session=True, cwd=str(REPO_ROOT))
    (d / "worker.pid").write_text(str(p.pid))
    return {"dispatched": True, "attempt_id": attempt_id, "path": path, "pid": p.pid, "log": str(Path(d) / "worker.log")}
