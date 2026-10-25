"""Extend existing AFO soak observation with frozen 014 fault/work/continuity evidence.

The observer has no model client and never stops the factory at a campaign boundary.
Only three exact Conductor fault recipes are executable here, under a signed runbook.
Reboot/storage/resource faults require their separately authorized external fixture
and are counted missing until its evidence is imported; no arbitrary shell recipe.
"""

from __future__ import annotations
import argparse
import json
import socket
import subprocess
import time
from pathlib import Path
from ..common import sha256_file
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
    from .policy import load
    from .operations import UNIT, Intent

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
    from .continuous_metrics import timeline

    sha = qualification.validate(manifest)
    lines = [json.loads(x) for x in soak.path(soak_id).read_text().splitlines() if x.strip()]
    head = lines[0]
    samples = [x for x in lines[1:] if x.get("kind") == "sample"]
    if not samples:
        return {"status": "NOT_RUN", "target_hours": head["target_hours"]}
    expected_end = head["wall"] + head["target_hours"] * 3600
    # Fixed wall window includes every missing sample, reboot gap and operator maintenance period.
    end = min(expected_end, samples[-1]["wall"])
    gross = timeline(
        [
            {
                "at": s["wall"],
                "control_plane": s["probes"].get("conductor"),
                "worker_ready": s["probes"].get("gateway") and s["probes"].get("fabro"),
                "cause": "OBSERVED_HEALTH" if s["healthy"] else "DEPENDENCY_OR_CONTROL_OUTAGE",
            }
            for s in samples
        ],
        head["wall"],
        max(head["wall"] + 0.000001, end),
        stale_after=head["interval_s"] * 2,
    )

    def read(refs):
        out = []
        for ref in refs:
            p = Path(ref["path"])
            if p.is_symlink() or sha256_file(p) != ref["sha256"]:
                raise Refused("CAMPAIGN_EVIDENCE_CHANGED")
            record = json.loads(p.read_text())
            if record.get("manifest_sha256") != sha:
                raise Refused("CAMPAIGN_EVIDENCE_UNBOUND")
            out.append(record)
        return out

    faults = read(fault_refs)
    work = read(work_refs)
    continuity = read(continuity_refs)
    missing = sorted(set(manifest["faults"]) - {r["fault"] for r in faults})
    failed = [
        r["fault"]
        for r in faults
        if r.get("independently_restored") is not True
        or r.get("restoration_seconds", float("inf")) > manifest["bounds"]["restore_seconds"]
        or r.get("unexpected_interventions") != 0
    ]
    duration_ok = samples[-1]["wall"] >= expected_end
    later = any(
        r.get("later_authorized_job_admitted") is True
        and r.get("service_relaunched_manually") is False
        and r.get("observed_until", 0) >= expected_end + manifest["bounds"]["post_campaign_seconds"]
        for r in continuity
    )
    work_ok = bool(work) and all(r.get("native_run_id") and r.get("independently_verified") is True for r in work)
    telemetry_ok = all(b["wall"] - a["wall"] <= head["interval_s"] * 2 for a, b in zip(samples, samples[1:], strict=False))
    pass_all = (
        duration_ok
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
        "target_hours": head["target_hours"],
        "gross_24_7_window": gross,
        "missing_faults": missing,
        "failed_faults": failed,
        "real_work_exposures": len(work),
        "post_campaign_continuity": later,
        "rolling_30_day_slo": "NOT_DEMONSTRATED",
        "service_intent_unchanged": True,
        "native_model_capability": "SEPARATE_QUALIFICATION",
    }


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
