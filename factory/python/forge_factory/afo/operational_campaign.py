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
from pathlib import Path

from . import qualification, soak
from .durable import Refused, digest, immutable_json

SIGNALS = {"clean-exit": "TERM", "crash": "KILL", "hang": "STOP"}


def start(manifest, soak_id, authorization_ref):
    result = qualification.preflight(manifest, live=True, authorization_ref=authorization_ref)
    if result["blockers"]:
        return result
    if not manifest["stage"].startswith("operation-"):
        raise Refused("OPERATIONAL_STAGE_REQUIRED")
    hours = int(manifest["stage"].split("-")[1])
    head = soak.start(soak_id, hours, 30, authorization_ref)
    immutable_json(soak.path(soak_id).with_suffix(".manifest.json"), manifest)
    return {"status": "STARTED_OBSERVATION_ONLY", "soak_id": soak_id, "head": head, "service_stop_at_end": False}


def sample(soak_id, *, probes=None):
    """Model-free observation remains possible after engineering authority expires."""
    return soak.sample(soak_id, probes)


def fault(manifest, case, authorization_ref, destination):
    if case not in SIGNALS:
        raise Refused("EXTERNAL_FAULT_FIXTURE_REQUIRED", case)
    result = qualification.preflight(manifest, live=True, authorization_ref=authorization_ref)
    if result["blockers"]:
        return result
    from . import authz
    from .operations import UNIT, Intent
    from .policy import load

    eff = load()
    action = "qualification-fault:" + case + ":" + UNIT
    allowed = authz.find(
        eff.mode, eff.sha256 or "", ref=authorization_ref, action="operate_service", request={"service_action": action}
    )
    if not allowed.allow:
        raise Refused(allowed.code)
    if Intent().read()["mode"] != "RUNNING":
        raise Refused("FAULT_OPERATIONS_INTENT_NOT_RUNNING")
    # No shell, no process-name matching, no other project's unit. This is an explicitly selected live fault.
    command = ["systemctl", "--user", "kill", "--kill-who=main", "--signal=" + SIGNALS[case], UNIT]
    at = time.time()
    result = subprocess.run(command, capture_output=True, text=True, timeout=10)
    record = {
        "schema": "forge-c/operational-fault/1",
        "manifest_sha256": digest(manifest),
        "fault": case,
        "unit": UNIT,
        "command": command,
        "at": at,
        "returncode": result.returncode,
        "host": socket.gethostname(),
        "authorization_ref": authorization_ref,
        "recovery_status": "AWAITING_INDEPENDENT_OBSERVATION",
    }
    immutable_json(Path(destination), record)
    return record


def report(manifest, soak_id, *, fault_refs=(), work_refs=(), continuity_refs=()):
    from . import fault_observer as observer
    from . import operational_work
    from .continuous_metrics import timeline

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
        or any(not s.get("boot_id") or s["boot_id"] == "unknown" for s in [head, *samples])
        or (samples and samples[0]["wall"] < head["wall"])
        or any(b["wall"] <= a["wall"] for a, b in zip(samples, samples[1:], strict=False))
    ):
        raise Refused("OPERATIONAL_OBSERVATION_WINDOW_INVALID")
    manifest_path = soak.path(soak_id).with_suffix(".manifest.json")
    manifest_bound = manifest_path.is_file() and digest(observer.read_json(manifest_path)) == sha
    if not samples:
        return {"status": "NOT_RUN", "target_hours": target_hours, "manifest_bound": manifest_bound}
    expected_end = head["wall"] + target_hours * 3600
    # Fixed wall window includes every missing sample, reboot gap and operator maintenance period.
    end = min(expected_end, samples[-1]["wall"])
    max_gap = min(head["interval_s"] * 2, manifest["bounds"]["probe_gap_seconds"])

    def probes_known(s):
        return set(s.get("probes") or {}) == {"conductor", "fabro", "gateway", "data_volume"} and all(
            type(v) is bool for v in s["probes"].values()
        )

    def clock_known(a, b):
        return b["wall"] - a["wall"] <= max_gap and (
            a["boot_id"] != b["boot_id"] or (
                b["mono"] >= a["mono"]
                and abs((b["wall"] - a["wall"]) - (b["mono"] - a["mono"])) <= soak.CLOCK_SKEW_S
            )
        )

    gross = timeline(
        [
            {
                "at": s["wall"],
                "control_plane": (s.get("probes") or {}).get("conductor") is True,
                "worker_ready": all((s.get("probes") or {}).get(k) is True for k in ("gateway", "fabro")),
                "telemetry_known": probes_known(s) and (
                    i == len(samples) - 1 or (probes_known(samples[i + 1]) and clock_known(s, samples[i + 1]))
                ),
                "cause": "UNKNOWN_OR_CONTRADICTORY_TELEMETRY"
                if not probes_known(s) or (i + 1 < len(samples) and (
                    not probes_known(samples[i + 1]) or not clock_known(s, samples[i + 1])
                ))
                else "OBSERVED_HEALTH" if all(s["probes"].values()) else "DEPENDENCY_OR_CONTROL_OUTAGE",
            }
            for i, s in enumerate(samples)
        ],
        head["wall"],
        max(head["wall"] + 0.000001, end),
        stale_after=head["interval_s"] * 2,
    )

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

    verified = set()
    for row in [*faults, *continuity]:
        if row.get("schema") == "forge-c/independent-operational-fault/1":
            verify_observation(manifest, row)
            verified.add(digest(row))
    work = read(work_refs)
    verified_work = []
    for row in work:
        if row.get("schema") == operational_work.SCHEMA:
            verified_work.append(operational_work.verify(manifest, row))
    window_work = [
        r for r in verified_work
        if r["native_terminal_observed_at"] is not None
        and head["wall"] <= r["native_terminal_observed_at"] <= samples[-1]["wall"]
    ]
    missing = sorted(set(manifest["faults"]) - {r["fault"] for r in faults})
    failed = [
        r["fault"]
        for r in faults
        if digest(r) not in verified
        or r.get("independently_restored") is not True
        or type(r.get("restoration_seconds")) not in (int, float)
        or not 0 <= r["restoration_seconds"] <= manifest["bounds"]["restore_seconds"]
        or r.get("unexpected_interventions") != 0
    ]
    duration_ok = samples[-1]["wall"] >= expected_end
    later = continuity_verdict(
        manifest, [r for r in [*faults, *continuity] if digest(r) in verified], window_work, expected_end
    )
    work_ok = bool(work) and len(window_work) == len(work) and all(r["independently_verified"] is True for r in window_work)
    telemetry_ok = all(
        clock_known(a, b) and probes_known(b)
        for a, b in zip([head, *samples], samples, strict=False)
    )
    pass_all = (
        duration_ok
        and manifest_bound
        and telemetry_ok
        and not missing
        and not failed
        and later
        and work_ok
        and all(
            r.get("ledger_reset") is False and r.get("duplicate_effects") == 0 and r.get("false_ready") is False for r in faults
        )
    )
    return {
        "status": "PASS" if pass_all else "INCOMPLETE" if not duration_ok else "FAIL",
        "manifest_sha256": sha,
        "target_hours": target_hours,
        "manifest_bound": manifest_bound,
        "telemetry_complete": telemetry_ok,
        "gross_24_7_window": gross,
        "missing_faults": missing,
        "failed_faults": failed,
        "real_work_exposures": sum(r["independently_verified"] for r in window_work),
        "unverified_work_records": len(work) - sum(r["independently_verified"] for r in window_work),
        "post_campaign_continuity": later,
        "rolling_30_day_slo": "NOT_DEMONSTRATED",
        "service_intent_unchanged": None,  # requires the independent intent timeline; never assume it from a report call
        "native_model_capability": "SEPARATE_QUALIFICATION",
    }


def continuity_verdict(manifest, records, work, expected_end):
    """Derive post-campaign service and later work from verified source records."""
    from .fault_observer import bound_json

    eligible = [r for r in records if r.get("independently_restored") is True and r.get("observation_gaps") is False]
    post = [r for r in eligible if r.get("fault") == "post-campaign-continuity"]
    later = [r for r in eligible if r.get("fault") == "later-authorized-intake"]
    for continued in post:
        end_rows = [bound_json(ref) for ref in continued["sample_refs"]]
        receipt = bound_json(continued["injection_ref"])
        if receipt["at"] < expected_end or end_rows[-1]["wall"] < expected_end + manifest["bounds"]["post_campaign_seconds"]:
            continue
        for admitted in later:
            if admitted["plan_ref"] != continued["plan_ref"]:
                continue
            intake = bound_json(admitted["injection_ref"])
            fixture = bound_json(intake["fixture_ref"])
            oid = fixture["parameters"]["order_id"]
            if intake["at"] < expected_end:
                continue
            if any(
                w["independently_verified"] is True
                and w["plan_ref"] == continued["plan_ref"]
                and w["order_id"] == oid
                and w["native_terminal_observed_at"] >= intake["at"]
                for w in work
            ):
                return True
    return False


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["start", "sample", "fault", "report"])
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--soak-id", required=True)
    ap.add_argument("--authorization-ref")
    ap.add_argument("--fault", choices=list(SIGNALS))
    ap.add_argument("--out", type=Path)
    ap.add_argument("--evidence", type=Path, help="JSON object containing hash-bound fault_refs/work_refs/continuity_refs")
    a = ap.parse_args(argv)
    manifest = json.loads(a.manifest.read_text())
    if a.command == "start":
        out = start(manifest, a.soak_id, a.authorization_ref)
    elif a.command == "sample":
        out = sample(a.soak_id)
    elif a.command == "fault":
        if not a.out or not a.fault:
            ap.error("--fault and --out required")
        out = fault(manifest, a.fault, a.authorization_ref, a.out)
    else:
        out = report(manifest, a.soak_id, **(json.loads(a.evidence.read_text()) if a.evidence else {}))
    print(json.dumps(out, indent=2))
    return 2 if out.get("status") in ("FAIL", "BLOCKED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
