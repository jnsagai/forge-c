"""Gross wall-clock availability, separate from worker readiness and product yield."""

from __future__ import annotations

import json
import math
import time

from .durable import Refused

ROLLING_WINDOW_SECONDS = 30 * 86400
AVAILABILITY_OBJECTIVE = 0.99
MAINTENANCE_REASONS = {"OPERATOR_MAINTENANCE", "PLANNED_STORAGE_OUTAGE", "PLANNED_POWER_OUTAGE"}


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


def validate_availability_schedule(schedule):
    """Frozen UTC service windows and separately accounted planned exclusions."""
    keys = {"schema", "valid_from", "valid_through", "service_windows", "exclusions"}

    def epoch(value):
        return type(value) is int and 0 <= value < 2**53

    if (
        not isinstance(schedule, dict) or set(schedule) != keys
        or schedule["schema"] != "forge-c/availability-schedule/1"
        or not all(epoch(schedule[k]) for k in ("valid_from", "valid_through"))
        or schedule["valid_through"] - schedule["valid_from"] < ROLLING_WINDOW_SECONDS
    ):
        raise Refused("AVAILABILITY_SCHEDULE_INVALID")
    for field in ("service_windows", "exclusions"):
        entries = schedule[field]
        if not isinstance(entries, list) or len(entries) > 10000 or (field == "service_windows" and not entries):
            raise Refused("AVAILABILITY_SCHEDULE_INVALID")
        prior_end = schedule["valid_from"]
        for entry in entries:
            expected = {"start", "end"} if field == "service_windows" else {"start", "end", "reason"}
            if (
                not isinstance(entry, dict) or set(entry) != expected
                or not all(epoch(entry[k]) for k in ("start", "end"))
                or not prior_end <= entry["start"] < entry["end"] <= schedule["valid_through"]
                or (field == "exclusions" and (
                    not isinstance(entry["reason"], str) or entry["reason"] not in MAINTENANCE_REASONS
                ))
            ):
                raise Refused("AVAILABILITY_SCHEDULE_INVALID")
            prior_end = entry["end"]
    service = iter(schedule["service_windows"])
    window = next(service)
    for excluded in schedule["exclusions"]:
        while window is not None and window["end"] <= excluded["start"]:
            window = next(service, None)
        if window is None or not window["start"] <= excluded["start"] < excluded["end"] <= window["end"]:
            raise Refused("AVAILABILITY_EXCLUSION_OUTSIDE_SERVICE_WINDOW")
    return schedule


def frozen_availability_schedule(manifest):
    if "availability_schedule_ref" not in manifest:
        return None
    ref = manifest["availability_schedule_ref"]
    if not manifest["stage"].startswith("operation-") or ref not in manifest["inputs"]:
        raise Refused("AVAILABILITY_SCHEDULE_NOT_FROZEN")
    from .fault_observer import bound_json

    return validate_availability_schedule(bound_json(ref))


def measure_windows(intervals, windows, start, end):
    observations = iter(intervals)
    row = next(observations, None)
    for window in windows:
        a, b = max(start, window["start"]), min(end, window["end"])
        if a >= b:
            continue
        while row is not None and row["end"] <= a:
            row = next(observations, None)
        available = unknown = 0.0
        while row is not None and row["start"] < b:
            seconds = min(b, row["end"]) - max(a, row["start"])
            available += seconds if row["control_plane"] == "AVAILABLE" else 0
            unknown += seconds if row["control_plane"] == "UNKNOWN" else 0
            if row["end"] >= b:
                break
            row = next(observations, None)
        yield {**window, "start": a, "end": b, "seconds": b - a,
               "available_seconds": available, "unknown_seconds": unknown}


def scheduled_availability(intervals, start, end, schedule):
    if not schedule["valid_from"] <= start < end <= schedule["valid_through"]:
        return {"status": "NOT_DEMONSTRATED", "reason": "SCHEDULE_HORIZON_DOES_NOT_COVER_ROLLING_WINDOW"}
    scheduled = list(measure_windows(intervals, schedule["service_windows"], start, end))
    exclusions = list(measure_windows(intervals, schedule["exclusions"], start, end))
    denominator_before_exclusions = sum(row["seconds"] for row in scheduled)
    denominator = denominator_before_exclusions - sum(row["seconds"] for row in exclusions)
    if denominator <= 0:
        return {"status": "NOT_DEMONSTRATED", "reason": "NO_SCHEDULED_SECONDS_AFTER_EXCLUSIONS",
                "exclusions": exclusions, "scheduled_seconds_before_exclusions": denominator_before_exclusions}
    available = sum(row["available_seconds"] for row in scheduled) - sum(row["available_seconds"] for row in exclusions)
    unknown = sum(row["unknown_seconds"] for row in scheduled) - sum(row["unknown_seconds"] for row in exclusions)
    fraction = available / denominator
    return {
        "status": "TARGET_MET" if fraction >= AVAILABILITY_OBJECTIVE else "TARGET_MISSED",
        "scope": "SCHEDULED_CONTROL_PLANE_FROZEN_SERVICE_WINDOWS",
        "start": start,
        "end": end,
        "target": AVAILABILITY_OBJECTIVE,
        "scheduled_seconds_before_exclusions": denominator_before_exclusions,
        "outside_schedule_seconds": end - start - denominator_before_exclusions,
        "scheduled_seconds": denominator,
        "available_seconds": available,
        "unavailable_seconds": denominator - available,
        "control_plane_unknown_seconds": unknown,
        "availability": fraction,
        "exclusions": exclusions,
    }


def rolling_gross_availability(samples, observed_since, observed_until, *, stale_after, schedule=None):
    """Evaluate the last full 30 days of a verified, unadjusted wall-clock history."""
    start = observed_until - ROLLING_WINDOW_SECONDS
    if observed_since > start:
        return {"status": "NOT_DEMONSTRATED", "reason": "FULL_WINDOW_REQUIRED"}
    measured = timeline(samples, start, observed_until, stale_after=stale_after)
    result = {
        "status": "TARGET_MET" if measured["gross_availability"] >= AVAILABILITY_OBJECTIVE else "TARGET_MISSED",
        "scope": "GROSS_24_7_WALL_CLOCK_NO_EXCLUSIONS",
        "start": start,
        "end": observed_until,
        "target": AVAILABILITY_OBJECTIVE,
        **{k: measured[k] for k in ("window_seconds", "available_seconds", "unavailable_seconds",
                                   "control_plane_unknown_seconds", "gross_availability")},
    }
    if schedule is not None:
        result["scheduled"] = scheduled_availability(measured["intervals"], start, observed_until, schedule)
    return result


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
