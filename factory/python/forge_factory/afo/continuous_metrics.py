"""Gross wall-clock availability, separate from worker readiness and product yield."""

from __future__ import annotations

import json
import time

from .durable import Refused


def timeline(samples, start, end, *, stale_after=120):
    if end <= start or stale_after < 1:
        raise Refused("AVAILABILITY_WINDOW_INVALID")
    rows = sorted(samples, key=lambda s: s["at"])
    if len({r["at"] for r in rows}) != len(rows):
        raise Refused("AVAILABILITY_DUPLICATE_OBSERVATION")
    points = sorted(
        {start, end, *[max(start, min(end, r["at"])) for r in rows], *[max(start, min(end, r["at"] + stale_after)) for r in rows]}
    )
    intervals = []
    healthy = worker = 0.0
    for a, b in zip(points, points[1:], strict=False):
        if b <= a:
            continue
        prior = next((r for r in reversed(rows) if r["at"] <= a), None)
        known = prior is not None and a - prior["at"] < stale_after and prior.get("telemetry_known", True) is True
        control = known and prior.get("control_plane") is True
        ready = known and prior.get("worker_ready") is True
        healthy += (b - a) if control else 0
        worker += (b - a) if ready else 0
        intervals.append(
            {
                "start": a,
                "end": b,
                "seconds": b - a,
                "control_plane": "AVAILABLE" if control else "UNAVAILABLE" if known else "UNKNOWN",
                "worker": "READY" if ready else "UNREADY" if known else "UNKNOWN",
                "cause": prior.get("cause", "OBSERVED")
                if known or (prior is not None and prior.get("telemetry_known") is False)
                else "MISSING_OR_STALE_TELEMETRY",
                "desired_mode": prior.get("desired_mode", "UNKNOWN") if known else "UNKNOWN",
                "product_progress": prior.get("product_progress", "UNKNOWN") if known else "UNKNOWN",
            }
        )
    return {
        "window_seconds": end - start,
        "available_seconds": healthy,
        "unavailable_seconds": end - start - healthy,
        "gross_availability": healthy / (end - start),
        "worker_ready_seconds": worker,
        "intervals": intervals,
        "rolling_30_day_status": "NOT_DEMONSTRATED" if end - start < 30 * 86400 else "REQUIRES_SLO_EVALUATION",
    }


def status(store):
    from .operations import Intent, configured

    now = time.time()
    with store.tx() as c:
        missions = [json.loads(r[0]) for r in c.execute("SELECT record FROM afo_missions")]
        liveness = [json.loads(r[0]) for r in c.execute("SELECT record FROM afo_execution_liveness")]
        waits = [
            {"next_probe": r[0], **json.loads(r[1])} for r in c.execute("SELECT next_probe,record FROM afo_dependency_waits")
        ]
        queue = c.execute("SELECT MIN(created_epoch) FROM afo_work_orders WHERE state='QUEUED'").fetchone()[0]
    from .mission_ledger import MissionLedger

    return {
        "service_intent": Intent().read() if configured() else {"mode": "LEGACY_UNCONFIGURED"},
        "native_executions": liveness,
        "missions": [MissionLedger(store).snapshot(m["mission_id"]) for m in missions],
        "waits": waits,
        "overdue_probes": sum(w["next_probe"] < now for w in waits),
        "oldest_queue_age_seconds": max(0, now - queue) if queue is not None else None,
        "product_success": "DERIVE_FROM_SEALED_PACKAGE_ONLY",
        "availability": "UNKNOWN_WITHOUT_OBSERVATION_WINDOW",
    }
