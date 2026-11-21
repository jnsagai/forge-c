"""Gross wall-clock availability, separate from worker readiness and product yield."""

from __future__ import annotations

import json
import math
import time

from .durable import Refused

ROLLING_WINDOW_SECONDS = 30 * 86400
AVAILABILITY_OBJECTIVE = 0.99


def timeline(samples, start, end, *, stale_after=120):
    if (
        any(type(v) not in (int, float) or not math.isfinite(v) for v in (start, end, stale_after))
        or end <= start or stale_after < 1
    ):
        raise Refused("AVAILABILITY_WINDOW_INVALID")
    rows = list(samples)
    if any(
        not isinstance(row, dict) or type(row.get("at")) not in (int, float) or not math.isfinite(row["at"])
        for row in rows
    ):
        raise Refused("AVAILABILITY_OBSERVATION_INVALID")
    rows.sort(key=lambda s: s["at"])
    if len({r["at"] for r in rows}) != len(rows):
        raise Refused("AVAILABILITY_DUPLICATE_OBSERVATION")
    points = sorted(
        {start, end, *[max(start, min(end, r["at"])) for r in rows], *[max(start, min(end, r["at"] + stale_after)) for r in rows]}
    )
    intervals = []
    healthy = worker = 0.0
    control_unknown = worker_unknown = 0.0
    cursor = 0
    prior = None
    for a, b in zip(points, points[1:], strict=False):
        if b <= a:
            continue
        while cursor < len(rows) and rows[cursor]["at"] <= a:
            prior = rows[cursor]
            cursor += 1
        known = prior is not None and a - prior["at"] < stale_after and prior.get("telemetry_known", True) is True
        control = prior.get("control_plane") if known else None
        ready = prior.get("worker_ready") if known else None
        seconds = b - a
        healthy += seconds if control is True else 0
        worker += seconds if ready is True else 0
        control_unknown += seconds if type(control) is not bool else 0
        worker_unknown += seconds if type(ready) is not bool else 0
        intervals.append(
            {
                "start": a,
                "end": b,
                "seconds": seconds,
                "control_plane": "AVAILABLE" if control is True else "UNAVAILABLE" if control is False else "UNKNOWN",
                "worker": "READY" if ready is True else "UNREADY" if ready is False else "UNKNOWN",
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
        "control_plane_unknown_seconds": control_unknown,
        "worker_ready_seconds": worker,
        "worker_unknown_seconds": worker_unknown,
        "intervals": intervals,
        "rolling_30_day_status": ("NOT_DEMONSTRATED" if end - start < ROLLING_WINDOW_SECONDS
                                  else "REQUIRES_SLO_EVALUATION"),
    }


def rolling_gross_availability(samples, observed_since, observed_until, *, stale_after):
    """Evaluate the last full 30 days of a verified, unadjusted wall-clock history."""
    start = observed_until - ROLLING_WINDOW_SECONDS
    if observed_since > start:
        return {"status": "NOT_DEMONSTRATED", "reason": "FULL_WINDOW_REQUIRED"}
    measured = timeline(samples, start, observed_until, stale_after=stale_after)
    return {
        "status": "TARGET_MET" if measured["gross_availability"] >= AVAILABILITY_OBJECTIVE else "TARGET_MISSED",
        "scope": "GROSS_24_7_WALL_CLOCK_NO_EXCLUSIONS",
        "start": start,
        "end": observed_until,
        "target": AVAILABILITY_OBJECTIVE,
        **{k: measured[k] for k in ("window_seconds", "available_seconds", "unavailable_seconds",
                                   "control_plane_unknown_seconds", "gross_availability")},
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
