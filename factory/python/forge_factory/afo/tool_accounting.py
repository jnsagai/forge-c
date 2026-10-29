"""Shared mission tool debit for native hooks and deterministic structured runners.

Uses the existing MissionLedger. The durable debit precedes handler execution:
failure/crash does not refund uncertain work, and no inference lease is released.
"""
from __future__ import annotations

from pathlib import Path

from .durable import Refused, strict_json


def charge(workspace: Path, event_id: str) -> dict | None:
    from .mission_ledger import MissionLedger
    from .queue import Store

    path = Path(workspace) / ".forge-run/durable-binding.json"
    if path.is_symlink():
        raise Refused("TOOL_MISSION_BINDING_UNSAFE")
    if not path.exists():
        return None  # Legacy workspaces without durable mission accounting are unchanged.
    job = strict_json(path.read_bytes(), 1024 * 1024)
    if (not isinstance(job, dict)
            or any(not isinstance(job.get(k), str) or not job[k] for k in ("mission_id", "job_id"))):
        raise Refused("TOOL_MISSION_BINDING_INVALID")
    MissionLedger(Store()).count(job["mission_id"], job["job_id"], "TOOL", event_id)
    return {"mission_id": job["mission_id"], "job_id": job["job_id"], "event_id": event_id}
