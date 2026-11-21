"""Extend existing AFO soak observation with frozen 014 fault/work/continuity evidence.

The observer has no model client and never stops the factory at a campaign boundary.
Only three exact Conductor fault recipes are executable here, under a signed runbook.
Reboot/storage/resource faults require their separately authorized external fixture
and are counted missing until its evidence is imported; no arbitrary shell recipe.
"""

from __future__ import annotations

import argparse
import json
import math
import socket
import subprocess
import time
from contextlib import nullcontext
from pathlib import Path

from . import qualification, soak
from .durable import Refused, digest, immutable_json

SIGNALS = {"clean-exit": "TERM", "crash": "KILL", "hang": "STOP"}
POST_CAMPAIGN_FAULTS = {"post-campaign-continuity", "later-authorized-intake"}
TRANSIENT_RECOVERY_FAULTS = {*SIGNALS, "dependency-outage", "restart-limit"}
TRANSIENT_RESTORE_OBJECTIVE_SECONDS = 600


def start(manifest, soak_id, authorization_ref, *, observer_plan_ref=None, host_plan_ref=None):
    result = qualification.preflight(manifest, live=True, authorization_ref=authorization_ref)
    if result["blockers"]:
        return result
    if not manifest["stage"].startswith("operation-"):
        raise Refused("OPERATIONAL_STAGE_REQUIRED")
    from .line_soak_prerequisites import line_plan_reference

    observer_plan_ref = line_plan_reference(manifest, observer_plan_ref)
    hours = int(manifest["stage"].split("-")[1])
    interval = 30
    line_plan = None
    replay = None
    if host_plan_ref is not None and observer_plan_ref is None:
        raise Refused("OPERATIONAL_COLLECTION_OBSERVER_PLAN_REQUIRED")
    if observer_plan_ref is not None:
        from .operational_collection import Collector

        collector = Collector(manifest, soak_id, observer_plan_ref, host_plan_ref)
        if "line_runtime" in collector.frozen:
            line_plan = collector.frozen
            from .line_soak import preflight

            result = preflight(manifest, observer_plan_ref, live=True, authorization_ref=authorization_ref)
            if result["blockers"]:
                return result
            replay = result["prerequisites"]
        interval = collector.config["interval_seconds"]
    def begin():
        immutable_json(soak.path(soak_id).with_suffix(".manifest.json"), manifest)
        if line_plan is not None:
            from .line_soak_prerequisites import admission_boundary

            current = admission_boundary(manifest, line_plan, replay)
            if current["blockers"]:
                return current
        head = soak.start(soak_id, hours, interval, authorization_ref)
        return {"status": "STARTED_OBSERVATION_ONLY", "soak_id": soak_id, "head": head, "service_stop_at_end": False}

    if line_plan is not None:
        from .operations import Intent

        with Intent(line_plan["intent"]).lock():
            # Heavy proof replay ran outside this lock. begin() fences the actual
            # append using its internal snapshot and current authority/intent.
            return begin()
    return begin()


def sample(soak_id, *, probes=None):
    """Model-free observation remains possible after engineering authority expires."""
    return soak.sample(soak_id, probes)


def collect(manifest, soak_id, observer_plan_ref, *, host_plan_ref=None, max_samples=None):
    """Resume bounded model-free collection; no authority renewal or factory stop."""
    from .operational_collection import Collector

    collector = Collector(manifest, soak_id, observer_plan_ref, host_plan_ref)
    allowance = collector.config["max_samples"]
    if max_samples is not None and (type(max_samples) is not int or not 1 <= max_samples <= allowance):
        raise Refused("OPERATIONAL_COLLECTION_SAMPLE_ALLOWANCE_INVALID")
    count = soak.run(soak_id, max_samples=max_samples or allowance, sampler=collector, stop_at_target=False)
    return {"status": "COLLECTION_INVOCATION_ENDED", "samples": count, "service_stop_at_end": False}


def fault(manifest, case, authorization_ref, destination, *, observer_plan_ref=None):
    if case not in SIGNALS:
        raise Refused("EXTERNAL_FAULT_FIXTURE_REQUIRED", case)
    result = qualification.preflight(manifest, live=True, authorization_ref=authorization_ref)
    if result["blockers"]:
        return result
    from . import authz
    from .line_soak_prerequisites import fault_target
    from .operations import UNIT, Intent
    from .policy import load

    target = fault_target(manifest, observer_plan_ref)
    replay = None
    if target:
        from .line_soak_prerequisites import check
        from .line_soak_snapshot import CURRENT

        replay = check(manifest, target, purpose="fault")
        if replay["blockers"]:
            return replay
        token = CURRENT.set(replay)
        try:
            from .line_soak_prerequisites import line_plan_reference, reference

            reference(line_plan_reference(manifest, observer_plan_ref), decode=False)
            replay.authority(authorization_ref)
            eff = load()
            action = "qualification-fault:" + case + ":" + UNIT
            allowed = authz.find(eff.mode, eff.sha256 or "", ref=authorization_ref, action="operate_service",
                                 request={"service_action": action})
            if not allowed.allow:
                raise Refused(allowed.code)
        finally:
            CURRENT.reset(token)
    intent = Intent(target["intent"]) if target else Intent()
    # The fixed local recipe shares the existing operator-intent serialization.
    # Generic campaigns retain their prior recipe and default unit.
    with intent.lock() if target else nullcontext():
        if target:
            from .line_soak_prerequisites import admission_boundary

            boundary = admission_boundary(manifest, target, replay, fault=True)
            if boundary["blockers"]:
                return boundary
        else:
            eff = load()
            action = "qualification-fault:" + case + ":" + UNIT
            allowed = authz.find(eff.mode, eff.sha256 or "", ref=authorization_ref, action="operate_service",
                                 request={"service_action": action})
            if not allowed.allow:
                raise Refused(allowed.code)
        current = intent.read()
        if current["mode"] != "RUNNING":
            raise Refused("FAULT_OPERATIONS_INTENT_NOT_RUNNING")
        command = ["systemctl", "--user", "kill", "--kill-who=main", "--signal=" + SIGNALS[case], UNIT]
        at = time.time()
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    record = {
        "schema": "forge-c/operational-fault/1",
        "manifest_sha256": digest(manifest),
        "fault": case,
        "unit": UNIT,
        **({"operations_epoch": current["epoch"]} if target else {}),
        "command": command,
        "at": at,
        "returncode": result.returncode,
        "host": socket.gethostname(),
        "authorization_ref": authorization_ref,
        "recovery_status": "AWAITING_INDEPENDENT_OBSERVATION",
    }
    immutable_json(Path(destination), record)
    return record


def report(manifest, soak_id, *, fault_refs=(), work_refs=(), continuity_refs=(),
           observer_plan_ref=None, host_plan_ref=None):
    from . import fault_observer as observer
    from . import operational_work
    from .continuous_metrics import frozen_availability_schedule, rolling_gross_availability, timeline

    sha = qualification.validate(manifest)
    raw = observer.read_bytes(soak.path(soak_id), observer.MAX_TRACE_BYTES)
    lines = [observer.strict_json(x, 65536) for x in raw.splitlines() if x.strip()]
    if not lines or lines[0].get("kind") != "start" or not manifest["stage"].startswith("operation-"):
        raise Refused("OPERATIONAL_OBSERVATION_HEAD_INVALID")
    head = lines[0]
    samples = [x for x in lines[1:] if x.get("kind") == "sample"]
    target_hours = int(manifest["stage"].split("-")[1])
    if (
        head.get("soak_id") != soak_id
        or head.get("target_hours") != target_hours
        or type(head.get("interval_s")) not in (int, float)
        or not math.isfinite(head["interval_s"])
        or not 5 <= head["interval_s"] <= 600
        or any(type(s.get(k)) not in (int, float) or not math.isfinite(s[k]) for s in [head, *samples] for k in ("wall", "mono"))
        or any(
            not isinstance(s.get("boot_id"), str) or s["boot_id"] in ("", "unknown")
            for s in [head, *samples]
        )
        or (samples and samples[0]["wall"] < head["wall"])
        or any(b["wall"] <= a["wall"] for a, b in zip(samples, samples[1:], strict=False))
    ):
        raise Refused("OPERATIONAL_OBSERVATION_WINDOW_INVALID")
    manifest_path = soak.path(soak_id).with_suffix(".manifest.json")
    manifest_bound = manifest_path.is_file() and digest(observer.read_json(manifest_path)) == sha
    collection = None
    if observer_plan_ref is not None or any("collection_ref" in row for row in samples):
        from .operational_collection import Collector

        if observer_plan_ref is None:
            raise Refused("OPERATIONAL_COLLECTION_REPORT_PLAN_REQUIRED")
        collection = Collector(manifest, soak_id, observer_plan_ref, host_plan_ref).verify()
        if collection["history_sha256"] != digest(lines):
            raise Refused("OPERATIONAL_COLLECTION_REPORT_HISTORY_CHANGED")
    if not samples:
        return {"status": "NOT_RUN", "target_hours": target_hours, "manifest_bound": manifest_bound}
    expected_end = head["wall"] + target_hours * 3600
    # Fixed wall window includes every missing sample, reboot gap and operator maintenance period.
    end = min(expected_end, samples[-1]["wall"])
    max_gap = min(head["interval_s"] * 2, manifest["bounds"]["probe_gap_seconds"])

    def probes(s):
        value = s.get("probes")
        return value if isinstance(value, dict) else {}

    def probes_known(s):
        observed = probes(s)
        return set(observed) == {"conductor", "fabro", "gateway", "data_volume"} and all(
            type(v) is bool for v in observed.values()
        )

    def worker_readiness(s):
        dependencies = [probes(s).get(k) for k in ("gateway", "fabro", "data_volume")]
        if any(value is False for value in dependencies):
            return False
        return True if all(value is True for value in dependencies) else None

    def clock_known(a, b):
        return (
            a["boot_id"] == b["boot_id"]
            and b["wall"] - a["wall"] <= max_gap
            and b["mono"] >= a["mono"]
            and abs((b["wall"] - a["wall"]) - (b["mono"] - a["mono"])) <= soak.CLOCK_SKEW_S
        )

    observations = []
    for a, b in zip(samples, [*samples[1:], None], strict=True):
        clock_ok = b is None or clock_known(a, b)
        control = probes(a).get("conductor")
        worker = worker_readiness(a)
        if b is not None and type(probes(b).get("conductor")) is not bool:
            control = None
        if b is not None and worker_readiness(b) is None:
            worker = None
        if b is not None and a["boot_id"] != b["boot_id"]:
            cause = "BOOT_CHANGED_INTERVAL_UNOBSERVED"
        elif not clock_ok or not probes_known(a) or (b is not None and not probes_known(b)):
            cause = "UNKNOWN_OR_CONTRADICTORY_TELEMETRY"
        else:
            cause = "OBSERVED_HEALTH" if control and worker else "DEPENDENCY_OR_CONTROL_OUTAGE"
        observations.append({"at": a["wall"], "control_plane": control, "worker_ready": worker,
                             "telemetry_known": clock_ok, "cause": cause})
    gross = timeline(observations, head["wall"], max(head["wall"] + 0.000001, end),
                     stale_after=head["interval_s"] * 2)
    rolling_gross = {"status": "NOT_DEMONSTRATED", "reason": "VERIFIED_COLLECTION_REQUIRED"}
    rolling_scheduled = rolling_gross.copy()
    if manifest_bound and collection is not None and collection.get("status") == "SOURCE_REPLAY_PASS":
        schedule = frozen_availability_schedule(manifest)
        rolling_gross = rolling_gross_availability(
            observations, head["wall"], samples[-1]["wall"], stale_after=head["interval_s"] * 2, schedule=schedule,
        )
        rolling_scheduled = rolling_gross.pop("scheduled", {
            "status": "NOT_DEMONSTRATED",
            "reason": "FROZEN_SERVICE_SCHEDULE_REQUIRED" if schedule is None else rolling_gross.get("reason"),
        })
        if schedule is not None:
            rolling_scheduled["schedule_ref"] = manifest["availability_schedule_ref"]

    byte_budget = observer.MAX_TRACE_BYTES

    def read(refs):
        nonlocal byte_budget
        if len(refs) > 10000:
            raise Refused("CAMPAIGN_EVIDENCE_COUNT_BOUND_EXCEEDED")
        out = []
        for ref in refs:
            import hashlib

            raw = observer.read_bytes(ref["path"], min(observer.MAX_BYTES, byte_budget))
            byte_budget -= len(raw)
            if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
                raise Refused("CAMPAIGN_EVIDENCE_CHANGED")
            record = observer.strict_json(raw, observer.MAX_BYTES)
            if record.get("manifest_sha256") != sha:
                raise Refused("CAMPAIGN_EVIDENCE_UNBOUND")
            out.append(record)
        return out

    faults = read(fault_refs)
    continuity = read(continuity_refs)
    # Legacy declarations remain readable evidence but cannot establish independent
    # recovery. New observer verdicts are recomputed from their original sources.
    from .fault_observer import verify as verify_observation

    verified = {}
    verified_reboots = {}
    recoveries = {}
    unverified_recovery_records = 0
    out_of_window = set()
    for index, row in enumerate([*faults, *continuity]):
        transient = index < len(faults) and row.get("fault") in TRANSIENT_RECOVERY_FAULTS
        if row.get("schema") == "forge-c/independent-operational-fault/1":
            source = {}
            verify_observation(manifest, row, source_details=source)
            identity = digest(row)
            receipt = source["receipt"]
            if transient and head["wall"] <= receipt["at"] < end:
                measurement = restoration_measurement(row, source, end, observer_plan_ref)
                injection = {k: receipt[k] for k in ("host", "unit", "fault", "at")}
                injection["parameters"] = source.get("fixture_parameters", {})
                recoveries.setdefault(digest(injection), []).append(measurement)
            if fault_in_window(manifest, row, receipt["at"], head["wall"], expected_end, samples[-1]["wall"]):
                verified[identity] = row
                if (
                    row["fault"] == "reboot"
                    and row["independently_restored"] is True and row["observation_gaps"] is False
                    and row["restoration_seconds"] <= manifest["bounds"]["restore_seconds"]
                    and (observer_plan_ref is None or row["plan_ref"] == observer_plan_ref)
                ):
                    # Replay already proved that this trace contains exactly one
                    # boot transition straddling the frozen injection.
                    before = after = None
                    for sample in source["samples"]:
                        if sample["wall"] > receipt["at"]:
                            after = sample
                            break
                        before = sample
                    if before is not None and after is not None:
                        verified_reboots.setdefault((before["boot_id"], after["boot_id"]), set()).add(receipt["at"])
            else:
                out_of_window.add(row["fault"])
        elif transient:
            unverified_recovery_records += 1
    fault_records = [*faults, *(r for r in continuity if r.get("fault") in POST_CAMPAIGN_FAULTS)]
    work = read(work_refs)
    verified_work = []
    for row in work:
        if row.get("schema") == operational_work.SCHEMA:
            verified_work.append(operational_work.verify(manifest, row))
    campaign_work = [
        r for r in verified_work
        if r["independently_verified"] is True and operational_work.work_in_window(r, head["wall"], end)
    ]
    post_campaign_work = [
        r for r in verified_work
        if r["independently_verified"] is True
        and operational_work.work_in_window(r, expected_end, samples[-1]["wall"])
        and r["native_terminal_observed_at"] > expected_end
    ]
    missing = sorted(set(manifest["faults"]) - {r["fault"] for r in fault_records})
    failed = [
        r["fault"]
        for r in fault_records
        if digest(r) not in verified
        or r.get("independently_restored") is not True
        or type(r.get("restoration_seconds")) not in (int, float)
        or not 0 <= r["restoration_seconds"] <= manifest["bounds"]["restore_seconds"]
        or r.get("unexpected_interventions") != 0
    ]
    duration_ok = samples[-1]["wall"] >= expected_end
    later = continuity_verdict(manifest, verified.values(), post_campaign_work, expected_end)
    accounted_work = len(campaign_work) + len(post_campaign_work)
    work_ok = bool(campaign_work) and accounted_work == len(work)
    accounted_reboots = []
    unexplained_telemetry = 0
    for a, b in zip([head, *samples], samples, strict=False):
        if clock_known(a, b) and probes_known(b):
            continue
        injections = verified_reboots.get((a["boot_id"], b["boot_id"]), ())
        if (
            b["wall"] - a["wall"] <= manifest["bounds"]["probe_gap_seconds"]
            and probes_known(a) and probes_known(b)
            and any(a["wall"] <= at < b["wall"] for at in injections)
        ):
            accounted_reboots.append({"start": a["wall"], "end": b["wall"]})
        else:
            unexplained_telemetry += 1
    telemetry_ok = unexplained_telemetry == 0 and not accounted_reboots
    intent_unchanged = None
    if collection is not None:
        intent = collection["campaign_intent"]
        if len(intent["observations"]) > 1:
            intent_unchanged = False
        elif (duration_ok and telemetry_ok and intent["observed_samples"] >= 2 and intent["unknown_samples"] == 0
              and intent["boundary"] is not None and intent["boundary"]["intent"] == intent["observations"][0]["intent"]):
            intent_unchanged = True
    pass_all = (
        duration_ok
        and manifest_bound
        and unexplained_telemetry == 0
        and not missing
        and not failed
        and not out_of_window
        and later
        and work_ok
        and all(
            r.get("ledger_reset") is False and r.get("duplicate_effects") == 0 and r.get("false_ready") is False
            for r in fault_records
        )
    )
    return {
        "status": "PASS" if pass_all else "INCOMPLETE" if not duration_ok else "FAIL",
        "manifest_sha256": sha,
        "target_hours": target_hours,
        "manifest_bound": manifest_bound,
        "telemetry_complete": telemetry_ok,
        "accounted_reboot_intervals": accounted_reboots,
        "unexplained_telemetry_intervals": unexplained_telemetry,
        "gross_24_7_window": gross,
        "missing_faults": missing,
        "failed_faults": failed,
        "out_of_window_faults": sorted(out_of_window),
        "real_work_exposures": len(campaign_work),
        "post_campaign_work_exposures": len(post_campaign_work),
        "unverified_work_records": len(work) - accounted_work,
        "post_campaign_continuity": later,
        "rolling_30_day_slo": rolling_scheduled["status"],
        "rolling_30_day_gross_availability": rolling_gross,
        "rolling_30_day_scheduled_availability": rolling_scheduled,
        "transient_restoration": restoration_summary(recoveries, unverified_recovery_records),
        "service_intent_unchanged": intent_unchanged,
        "native_model_capability": "SEPARATE_QUALIFICATION",
        "collection": collection,
    }


def restoration_measurement(record, source, cutoff, observer_plan_ref):
    at = source["receipt"]["at"]
    detected, restored = source["detected_at"], source["restored_at"]
    detected_in_window = record["fault_exposed"] is True and detected is not None and at <= detected <= cutoff
    observed_until = min(cutoff, source["samples"][-1]["wall"])
    effects_end = min(restored, observed_until) if restored is not None else observed_until
    before = [s for s in source["samples"] if s["wall"] <= at][-1:]
    relevant = [*before, *(s for s in source["samples"] if at < s["wall"] <= effects_end)]
    storage = [(s.get("health") or {}).get("data_volume") for s in relevant]
    known_boots = {s.get("boot_id") for s in relevant}
    prerequisite_lost = (
        source.get("fixture_parameters", {}).get("dependency") == "data_volume"
        or any(value is False for value in storage)
        or len(known_boots - {None, "", "unknown"}) > 1
    )
    comparable = observer_plan_ref is None or record["plan_ref"] == observer_plan_ref
    covered = (
        bool(storage) and all(value is True for value in storage)
        and len(known_boots) == 1 and not known_boots & {None, "", "unknown"}
        and record["observation_gaps"] is False and comparable
    )
    interventions = record["unexpected_interventions"]
    return {
        "fault": record["fault"], "exposed": detected_in_window and comparable, "prerequisite_lost": prerequisite_lost,
        "coverage_complete": covered,
        "detection_seconds": detected - at if detected_in_window and comparable else None,
        "restoration_seconds": restored - at if (detected_in_window and covered and not prerequisite_lost
                                                 and restored is not None and detected <= restored <= observed_until) else None,
        "observed_seconds_after_injection": max(0, observed_until - at),
        "no_unexpected_interventions": interventions == 0 if type(interventions) is int else None,
    }


def restoration_summary(recoveries, unverified):
    """Empirical nearest-rank p95 of distinct, replayed in-scope recoveries."""
    results = []
    for identity, rows in sorted(recoveries.items()):
        elapsed = {r["restoration_seconds"] for r in rows if r["restoration_seconds"] is not None}
        detections = [r["detection_seconds"] for r in rows if r["detection_seconds"] is not None]
        prerequisite_lost = any(r["prerequisite_lost"] for r in rows)
        if prerequisite_lost:
            outcome = "OUTSIDE_TRANSIENT_SCOPE"
        elif not any(r["exposed"] for r in rows):
            outcome = "UNCONFIRMED_EXPOSURE"
        elif len(elapsed) == 1:
            outcome = "RECOVERED"
        elif len(elapsed) > 1:
            outcome = "AMBIGUOUS"
        elif any(r["coverage_complete"] and r["exposed"] for r in rows):
            outcome = "RIGHT_CENSORED"
        else:
            outcome = "RECOVERY_UNVERIFIED"
        interventions = [r["no_unexpected_interventions"] for r in rows]
        results.append({
            "injection_identity_sha256": identity, "fault": rows[0]["fault"], "outcome": outcome,
            "detection_seconds": min(detections, default=None),
            "restoration_seconds": next(iter(elapsed)) if outcome == "RECOVERED" else None,
            "observed_seconds_after_injection": max(r["observed_seconds_after_injection"] for r in rows),
            "no_unexpected_interventions": (False if any(v is False for v in interventions)
                                            else True if all(v is True for v in interventions) else None),
        })
    recovered = sorted(r["restoration_seconds"] for r in results if r["outcome"] == "RECOVERED")
    counts = {outcome: sum(r["outcome"] == outcome for r in results) for outcome in (
        "RECOVERED", "OUTSIDE_TRANSIENT_SCOPE", "UNCONFIRMED_EXPOSURE", "AMBIGUOUS", "RIGHT_CENSORED",
        "RECOVERY_UNVERIFIED",
    )}
    rank = (95 * len(recovered) + 99) // 100
    p95 = recovered[rank - 1] if rank else None
    missing = sorted(TRANSIENT_RECOVERY_FAULTS - {r["fault"] for r in results if r["outcome"] == "RECOVERED"})
    blockers = []
    if not rank or rank == len(recovered):
        blockers.append("NO_TAIL_RESOLUTION_BEYOND_SAMPLE_MAXIMUM")
    if unverified or any(counts[k] for k in ("UNCONFIRMED_EXPOSURE", "AMBIGUOUS", "RIGHT_CENSORED", "RECOVERY_UNVERIFIED")) or missing:
        blockers.append("INCOMPLETE_ELIGIBLE_RECOVERY_EVIDENCE")
    if any(r["no_unexpected_interventions"] is None for r in results if r["outcome"] != "OUTSIDE_TRANSIENT_SCOPE"):
        blockers.append("HOST_INTERVENTION_EVIDENCE_REQUIRED")
    if any(r["no_unexpected_interventions"] is False for r in results if r["outcome"] != "OUTSIDE_TRANSIENT_SCOPE"):
        blockers.append("UNEXPECTED_INTERVENTION_OBSERVED")
    return {
        "status": ("NOT_DEMONSTRATED" if blockers else "TARGET_MET" if p95 <= TRANSIENT_RESTORE_OBJECTIVE_SECONDS
                   else "TARGET_MISSED"),
        "objective_seconds": TRANSIENT_RESTORE_OBJECTIVE_SECONDS,
        "p95_seconds": p95, "nearest_rank": rank or None, "p95_denominator": len(recovered),
        "recoveries_over_objective": sum(seconds > TRANSIENT_RESTORE_OBJECTIVE_SECONDS for seconds in recovered),
        "by_outcome": counts, "unverified_records": unverified, "missing_recovered_fault_classes": missing,
        "blockers": blockers, "incidents": results,
    }


def fault_in_window(manifest, record, at, start, expected_end, last_observed):
    """Check the operation and its measured recovery against the observed stage."""
    duration = record["restoration_seconds"]
    restored = at if duration is None else at + duration
    if record["fault"] in POST_CAMPAIGN_FAULTS:
        if record["fault"] == "post-campaign-continuity":
            restored = at + manifest["bounds"]["post_campaign_seconds"]
        return expected_end <= at <= restored <= last_observed
    return start <= at < expected_end and at <= restored <= min(expected_end, last_observed)


def continuity_verdict(manifest, records, work, expected_end):
    """Derive post-campaign service and later work from verified source records."""
    from .fault_observer import bound_json
    from .operational_work import work_in_window

    eligible = [r for r in records if r.get("independently_restored") is True and r.get("observation_gaps") is False]
    post = [r for r in eligible if r.get("fault") == "post-campaign-continuity"]
    later = [r for r in eligible if r.get("fault") == "later-authorized-intake"]
    for continued in post:
        end_rows = [bound_json(ref) for ref in continued["sample_refs"]]
        receipt = bound_json(continued["injection_ref"])
        continuous_until = receipt["at"] + manifest["bounds"]["post_campaign_seconds"]
        if receipt["at"] < expected_end or end_rows[-1]["wall"] < continuous_until:
            continue
        for admitted in later:
            if admitted["plan_ref"] != continued["plan_ref"]:
                continue
            intake = bound_json(admitted["injection_ref"])
            fixture = bound_json(intake["fixture_ref"])
            oid = fixture["parameters"]["order_id"]
            if intake["at"] < continuous_until:
                continue
            if any(
                w["independently_verified"] is True
                and w["plan_ref"] == continued["plan_ref"]
                and w["order_id"] == oid
                and w["native_terminal_observed_at"] >= intake["at"]
                and work_in_window(w, intake["at"], w["observed_until"])
                for w in work
            ):
                return True
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["start", "sample", "collect", "fault", "report"])
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--soak-id", required=True)
    ap.add_argument("--authorization-ref")
    ap.add_argument("--fault", choices=list(SIGNALS))
    ap.add_argument("--out", type=Path)
    ap.add_argument("--observer-plan", type=Path, help="Existing frozen observer plan, never an authority grant")
    ap.add_argument("--host-plan", type=Path, help="Existing frozen segmented host plan")
    ap.add_argument("--max-samples", type=int, help="Finite samples for this collector invocation")
    ap.add_argument("--evidence", type=Path, help="JSON object containing hash-bound fault_refs/work_refs/continuity_refs")
    a = ap.parse_args(argv)
    manifest = json.loads(a.manifest.read_text())
    from .operational_collection import reference

    refs = {"observer_plan_ref": reference(a.observer_plan.resolve()) if a.observer_plan else None,
            "host_plan_ref": reference(a.host_plan.resolve()) if a.host_plan else None}
    if a.command == "start":
        out = start(manifest, a.soak_id, a.authorization_ref, **refs)
    elif a.command == "sample":
        if refs["observer_plan_ref"] is None:
            out = sample(a.soak_id)
        else:
            from .operational_collection import Collector

            out = Collector(manifest, a.soak_id, refs["observer_plan_ref"], refs["host_plan_ref"])(a.soak_id)
    elif a.command == "collect":
        if refs["observer_plan_ref"] is None:
            ap.error("--observer-plan required for collect")
        out = collect(manifest, a.soak_id, **refs, max_samples=a.max_samples)
    elif a.command == "fault":
        if not a.out or not a.fault:
            ap.error("--fault and --out required")
        out = fault(manifest, a.fault, a.authorization_ref, a.out, observer_plan_ref=refs["observer_plan_ref"])
    else:
        evidence = json.loads(a.evidence.read_text()) if a.evidence else {}
        out = report(manifest, a.soak_id, **{**evidence, **{k: v for k, v in refs.items() if v is not None}})
    print(json.dumps(out, indent=2))
    return 2 if out.get("status") in ("FAIL", "BLOCKED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
