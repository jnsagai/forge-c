"""Deterministic exposure/restoration predicates for the frozen DA-AT-052 cases.

Inputs are independent captured facts, never proposed success flags. This module
has no effect, model, scheduler or authority interface. External fixture receipts
only identify the intended exposure; the observations must establish that it occurred.
"""

from __future__ import annotations

import math
import re

from .durable import Refused

ACTIVE = {"ADMITTED", "RUNNING", "WAITING_RECOVERY", "VALIDATING"}
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}$")
PARAMETERS = {
    "last-job-success": {"order_id"},
    "last-job-failure": {"order_id"},
    "last-job-block": {"order_id"},
    "empty-queue": set(),
    "drained-queue": set(),
    "dependency-outage": {"dependency"},
    "reboot": set(),
    "restart-limit": set(),
    "poison-head": {"order_id", "eligible_order_id"},
    "resource-pressure": {"minimum_free_bytes"},
    "operator-stop-resume": set(),
    "post-campaign-continuity": set(),
    "later-authorized-intake": {"order_id"},
}


def validate_fixture(doc, fault, plan_ref, unit):
    if (
        not isinstance(doc, dict)
        or fault not in PARAMETERS
        or doc.get("schema") != "forge-c/operational-exposure-fixture/1"
        or doc.get("fault") != fault
        or doc.get("observer_plan_ref") != plan_ref
        or doc.get("unit") != unit
        or not isinstance(doc.get("parameters"), dict)
        or set(doc["parameters"]) != PARAMETERS[fault]
    ):
        raise Refused("OPERATIONAL_EXPOSURE_FIXTURE_INVALID")
    params = doc["parameters"]
    for k in ("order_id", "eligible_order_id"):
        if k in params and (not isinstance(params[k], str) or not ID.fullmatch(params[k])):
            raise Refused("OPERATIONAL_EXPOSURE_ORDER_INVALID")
    if "eligible_order_id" in params and params["order_id"] == params["eligible_order_id"]:
        raise Refused("OPERATIONAL_EXPOSURE_ORDER_NOT_INDEPENDENT")
    if "minimum_free_bytes" in params and (type(params["minimum_free_bytes"]) is not int or params["minimum_free_bytes"] <= 0):
        raise Refused("OPERATIONAL_EXPOSURE_RESOURCE_BOUND_INVALID")
    if "dependency" in params and params["dependency"] not in ("fabro", "gateway", "data_volume"):
        raise Refused("OPERATIONAL_EXPOSURE_DEPENDENCY_INVALID")
    return params


def healthy(sample, max_age=120):
    unit, health = sample.get("unit") or {}, sample.get("health") or {}
    hb = sample.get("heartbeat") or {}
    return (
        sample.get("complete") is True
        and unit.get("ActiveState") == "active"
        and isinstance(unit.get("MainPID"), str)
        and unit["MainPID"].isdecimal()
        and int(unit["MainPID"]) > 0
        and set(health) == {"conductor", "fabro", "gateway", "data_volume"}
        and all(v is True for v in health.values())
        and hb.get("pid") == int(unit["MainPID"])
        and hb.get("ok") is True
        and type(hb.get("cycle")) is int
        and hb["cycle"] >= 0
        and type(hb.get("epoch")) in (int, float)
        and 0 <= sample.get("completed_wall", sample["wall"]) - hb["epoch"] <= max_age
    )


def _orders(sample):
    return {r["order_id"]: r for r in sample["ledger"]["orders"]}


def _active(sample):
    return [r for r in sample["ledger"]["orders"] if r["state"] in ACTIVE]


def _no_capacity_held(sample):
    ex = sample["ledger"]["afo_execution_liveness"]
    requests = sample["ledger"]["afo_request_ledger"]
    return not any(r["resource_lease"] == "HELD" for r in ex) and all(r["state"] in ("QUIESCENT", "RESERVED") for r in requests)


def _known(sample):
    return sample.get("complete") is True and isinstance(sample.get("ledger"), dict)


def _same_intent(a, b):
    return a.get("intent") == b.get("intent") and (b.get("intent") or {}).get("mode") == "RUNNING"


def _terminal(sample, oid, fault):
    order = _orders(sample).get(oid, {})
    attempts = [r for r in sample["ledger"].get("attempts", []) if r["order_id"] == oid]
    if not attempts or any(type(r.get("attempt_seq")) is not int or r["attempt_seq"] <= 0 for r in attempts):
        return False
    last = max(attempts, key=lambda r: r["attempt_seq"])
    if not last.get("fabro_run_id"):
        return False
    if fault == "last-job-success":
        return order.get("state") == "READY_FOR_OFFLINE_REVIEW" and last["state"] == "SUCCEEDED"
    if fault == "last-job-failure":
        return order.get("state") == "BLOCKED" and last["state"] in ("FAILED", "CANCELLED")
    return (
        order.get("state") == "BLOCKED"
        and last["state"] == "SUCCEEDED"
        and str(order.get("terminal_reason", "")).startswith("package BLOCKED / BLOCKED")
    )


def _no_admission_during_stop(rows, bound):
    stop = next((i for i, s in enumerate(rows) if (s.get("intent") or {}).get("mode") == "STOPPED"), None)
    if stop is None or stop == 0:
        return False
    epoch = rows[stop]["intent"]["epoch"]
    stopped = []
    for s in rows[stop:]:
        if (s.get("intent") or {}).get("mode") != "STOPPED":
            break
        stopped.append(s)
    if not stopped or not all(_known(s) for s in stopped):
        return False
    settled = [s for s in stopped if s["intent"].get("effective_stop") is True]
    if not settled or settled[0]["wall"] - stopped[0]["wall"] > bound:
        return False
    for s in stopped:
        if s["wall"] >= settled[0]["wall"] and (not _no_capacity_held(s) or (s.get("unit") or {}).get("MainPID") != "0"):
            return False
    for a, b in zip(stopped, stopped[1:], strict=False):
        for table, key in (("afo_request_ledger", "request_id"), ("afo_mission_executions", "identity")):
            if {r[key] for r in b["ledger"][table]} != {r[key] for r in a["ledger"][table]}:
                return False
        previous = _orders(a)
        if any(r["state"] in ACTIVE and previous.get(oid, {}).get("state") not in ACTIVE for oid, r in _orders(b).items()):
            return False
    return rows[stop - 1]["intent"]["epoch"] < epoch and any(
        s["intent"]["mode"] == "RUNNING" and s["intent"]["epoch"] > epoch for s in rows[stop + len(stopped) :]
    )


def external(manifest, fault, params, receipt, rows):
    """Return exposure and the first observed recovery; unknown classes never default to success."""

    def ok(sample):
        return healthy(sample, manifest["bounds"]["control_cycle_seconds"])

    at = receipt["at"]
    before = [r for r in rows if r["wall"] <= at]
    after = [r for r in rows if r["wall"] > at]
    if not before or not after or not _known(before[-1]) or not ok(before[-1]):
        return False, None
    base = before[-1]
    if not 0 <= at - base["wall"] <= manifest["bounds"]["probe_gap_seconds"] or base["intent"]["mode"] != "RUNNING":
        return False, None
    known = [s for s in after if _known(s)]
    changed = []
    if fault.startswith("last-job-"):
        oid = params["order_id"]
        if _orders(base).get(oid, {}).get("state") in ACTIVE and len(_active(base)) == 1:
            changed = [s for s in known if _terminal(s, oid, fault) and not _active(s)]
    elif fault == "empty-queue":
        changed = [s for s in known if not _active(s) and not any(r["state"] == "QUEUED" for r in _orders(s).values())]
    elif fault == "drained-queue":
        changed = [
            s
            for s in known
            if s["intent"]["mode"] == "DRAINING"
            and s["ledger"].get("controls", {}).get("draining") == "1"
            and not _active(s)
            and _no_capacity_held(s)
        ]
    elif fault == "dependency-outage":
        changed = [s for s in after if (s.get("health") or {}).get(params["dependency"]) is False]
    elif fault == "reboot":
        changed = (
            [s for s in known if s.get("boot_id") not in (None, "unknown", base["boot_id"])]
            if base["boot_id"] != "unknown"
            else []
        )
    elif fault == "restart-limit":
        changed = [
            s for s in known if (s.get("unit") or {}).get("Result") == "start-limit-hit" and s["unit"]["ActiveState"] == "failed"
        ]
    elif fault == "poison-head":
        oid, other = params["order_id"], params["eligible_order_id"]
        candidate, eligible = _orders(base).get(oid, {}), _orders(base).get(other, {})
        if (
            candidate.get("state") == eligible.get("state") == "QUEUED"
            and candidate.get("envelope_valid") is False
            and eligible.get("envelope_valid") is True
            and candidate.get("created_epoch", math.inf) <= eligible.get("created_epoch", -math.inf)
        ):
            changed = [
                s
                for s in known
                if _orders(s).get(oid, {}).get("state") == "BLOCKED"
                and _orders(s).get(other, {}).get("state") in ACTIVE
                and _orders(s)[other].get("authorization_id")
            ]
    elif fault == "resource-pressure":
        threshold = params["minimum_free_bytes"]
        if type(base.get("free_bytes")) is int and base["free_bytes"] >= threshold:
            changed = [s for s in after if type(s.get("free_bytes")) is int and s["free_bytes"] < threshold]
    elif fault == "operator-stop-resume":
        changed = (
            [s for s in known if s["intent"]["mode"] == "STOPPED"]
            if _no_admission_during_stop([base, *after], manifest["bounds"]["restore_seconds"])
            else []
        )
    elif fault == "post-campaign-continuity":
        end = rows[0]["wall"] + int(manifest["stage"].split("-")[1]) * 3600
        if at >= end:
            changed = [
                s
                for s in known
                if s["wall"] >= at + manifest["bounds"]["post_campaign_seconds"]
                and all(ok(r) and _same_intent(base, r) for r in after if r["wall"] <= s["wall"])
            ]
    elif fault == "later-authorized-intake":
        oid = params["order_id"]
        if oid not in _orders(base):
            changed = [
                s
                for s in known
                if _orders(s).get(oid, {}).get("state") in ACTIVE
                and _orders(s)[oid].get("authorization_id")
                and any(r["order_id"] == oid and r.get("fabro_run_id") for r in s["ledger"].get("attempts", []))
            ]
    else:
        return False, None
    if not changed:
        return False, None
    first = changed[0]
    bound = (
        manifest["bounds"]["eligible_queue_seconds"]
        if fault in ("poison-head", "later-authorized-intake")
        else manifest["bounds"]["restore_seconds"]
    )

    def restored(s):
        if not ok(s) or s["wall"] < first["wall"]:
            return False
        if fault.startswith("last-job-") or fault in ("empty-queue", "drained-queue"):
            window = [r for r in after if first["wall"] <= r["wall"] <= s["wall"]]
            if (
                s["wall"] - first["wall"] < manifest["bounds"]["control_cycle_seconds"]
                or not all(ok(r) for r in window)
                or s["heartbeat"]["cycle"] <= first["heartbeat"]["cycle"]
            ):
                return False
        if fault == "drained-queue":
            return s["intent"]["mode"] == "DRAINING" and not _active(s) and _no_capacity_held(s)
        if fault == "operator-stop-resume":
            return s["intent"]["mode"] == "RUNNING" and s["intent"]["epoch"] > first["intent"]["epoch"]
        if not _same_intent(base, s):
            return False
        if fault == "resource-pressure":
            return type(s.get("free_bytes")) is int and s["free_bytes"] >= params["minimum_free_bytes"]
        if fault in ("restart-limit", "reboot"):
            return (s["boot_id"], s["unit"]["MainPID"]) != (base["boot_id"], base["unit"]["MainPID"])
        if fault == "post-campaign-continuity":
            return s in changed
        return True

    recovery = next((s for s in known if restored(s) and (fault == "post-campaign-continuity" or s["wall"] - at <= bound)), None)
    return True, recovery
