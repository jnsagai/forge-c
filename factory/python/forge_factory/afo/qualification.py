"""Executable Feature 014 campaign preparation, bounded native stepping and reporting.

Freeze before live execution. `step` uses existing local-agent/native reconciliation,
never its own inference engine or job budgets. It requires pre-provisioned, approved
AFO job bindings, a current signed campaign runbook and exact candidate identity.
Missing authority/inputs produce explicit blockers; dry-run is not qualification.
"""

from __future__ import annotations

import argparse
import json
import socket
import statistics
import subprocess
import time
from pathlib import Path

from ..common import REPO_ROOT, sha256_file, utc_now
from .durable import Refused, digest, immutable_json

STAGES = ("protocol", "rcc", "benchmark", "operation-24", "operation-72", "operation-168")
FAULTS = (
    "last-job-success",
    "last-job-failure",
    "last-job-block",
    "empty-queue",
    "drained-queue",
    "dependency-outage",
    "clean-exit",
    "crash",
    "hang",
    "reboot",
    "restart-limit",
    "poison-head",
    "resource-pressure",
    "operator-stop-resume",
    "post-campaign-continuity",
    "later-authorized-intake",
)


def revision():
    return subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True, timeout=10
    ).stdout.strip()


def freeze(
    stage,
    destination,
    *,
    identity,
    inputs=(),
    jobs=None,
    baseline=None,
    model_profile=None,
    job_token_reservations=None,
    protocol_faults=None,
    mission=None,
):
    from ..lrtx.role_capability import key

    if stage not in STAGES:
        raise Refused("UNKNOWN_CAMPAIGN_STAGE")
    key(identity)
    template = REPO_ROOT / "factory/qualification/014/protocol-cases.json"
    cases = json.loads(template.read_text())["cases"] if stage == "protocol" else []
    from ..lrtx.seeded import CATALOGUE, catalogue_hash

    product_cases = []
    if stage == "benchmark":
        from ..lrtx.campaign import load as load_product_campaign

        product = load_product_campaign(REPO_ROOT / "specs/010-local-rtx-optimization/campaign.yaml")
        for case in product["cases"]:
            for repeat in range(1, case.get("repeat", 1) + 1):
                product_cases.append(
                    {
                        **case,
                        "repeat": repeat,
                        "trial_id": f"{case['id']}:{repeat:02}",
                        "profile": "local-rtx-v2-omniverse2",
                        "model": model_profile,
                    }
                )
    count = 100 if stage == "protocol" else 30 if stage == "benchmark" else 1
    refs = []
    for raw in inputs:
        p = Path(raw)
        if p.is_symlink() or not p.is_file():
            raise Refused("QUALIFICATION_INPUT_UNAVAILABLE", str(p))
        refs.append({"path": str(p.resolve()), "sha256": sha256_file(p)})
    manifest = {
        "schema": "forge-c/qualification-014/1",
        "stage": stage,
        "created_at": utc_now(),
        "source_revision": revision(),
        "execution_host": "omniverse2",
        "identity": identity,
        "identity_sha256": key(identity),
        "cases": cases,
        "product_cases": product_cases,
        "critical_defect_ids": [c["id"] for c in CATALOGUE],
        "independent_defect_catalogue_sha256": catalogue_hash(),
        "expected_trials": count,
        "template_sha256": sha256_file(template),
        "inputs": refs,
        "jobs": jobs or {},
        "baseline": baseline,
        "faults": list(FAULTS) if stage.startswith("operation-") else [],
        "bounds": {
            "probe_gap_seconds": 600,
            "control_cycle_seconds": 120,
            "restore_seconds": 600,
            "eligible_queue_seconds": 600,
            "immediate_start_burst": 5,
            "start_interval_seconds": 600,
            "slow_recovery_cooldown_seconds": 600,
            "verification_workers": 1,
            "inference_requests": 1,
            "batch_items": 32,
            "post_campaign_seconds": 1200,
        },
        "criteria": {
            "protocol_correct": 100,
            "protocol_false_success": 0,
            "product_ready_min": 27,
            "product_trials": 30,
            "critical_detection": 1.0,
            "false_ready": 0,
            "structured_invalid_rate_below": 0.01,
            "median_input_reduction_min": 0.5,
        },
        "service_persists_after_campaign": True,
        "authorization_ref": None,
        "model_profile": model_profile,
    }
    if job_token_reservations is not None:
        manifest["job_token_reservations"] = job_token_reservations
    if protocol_faults is not None:
        manifest["protocol_faults"] = protocol_faults
    if mission is not None:
        manifest["mission"] = mission
    validate(manifest)
    immutable_json(Path(destination), manifest)
    return manifest


def validate(manifest):
    if manifest.get("schema") != "forge-c/qualification-014/1" or manifest.get("stage") not in STAGES:
        raise Refused("CAMPAIGN_MANIFEST_INVALID")
    from ..lrtx.role_capability import key

    if key(manifest["identity"]) != manifest["identity_sha256"]:
        raise Refused("CAMPAIGN_IDENTITY_CHANGED")
    if "protocol_faults" in manifest:
        from .protocol_faults import validate_catalogue

        if manifest["stage"] != "protocol":
            raise Refused("QUALIFICATION_FAULT_CATALOGUE_INVALID")
        validate_catalogue(manifest["protocol_faults"], manifest["jobs"])
    if "job_token_reservations" in manifest:
        reservations = manifest["job_token_reservations"]
        expected = {binding["job_id"] for binding in manifest["jobs"].values()}
        if (
            manifest["stage"] != "protocol"
            or not expected
            or not isinstance(reservations, dict)
            or set(reservations) != expected
            or any(type(v) is not int or not 0 < v <= manifest["identity"]["context_tokens"] for v in reservations.values())
        ):
            raise Refused("QUALIFICATION_INITIAL_RESERVATIONS_INVALID")
    if "mission" in manifest:
        from .mission_ledger import validate_limits

        mission = manifest["mission"]
        if not isinstance(mission, dict) or set(mission) != {"mission_id", "lineage", "limits"}:
            raise Refused("QUALIFICATION_MISSION_INVALID")
        if any(not isinstance(mission[k], str) or not mission[k] or len(mission[k]) > 256 for k in ("mission_id", "lineage")):
            raise Refused("QUALIFICATION_MISSION_INVALID")
        validate_limits(mission["limits"])
        if (
            manifest["stage"] != "protocol"
            or not manifest.get("job_token_reservations")
            or any(b["mission_id"] != mission["mission_id"] for b in manifest["jobs"].values())
            or mission["limits"]["max_attempts"] != 0
            or mission["limits"]["max_jobs"] > len(manifest["jobs"])
            or mission["limits"]["max_requests"] > len(manifest["jobs"])
            or mission["limits"]["max_tokens"] > sum(manifest["job_token_reservations"].values())
            or mission["limits"]["max_tools"] != 0
            or mission["limits"]["max_corrections"] != 0
        ):
            raise Refused("QUALIFICATION_MISSION_EXCEEDS_FROZEN_WORK")
    if manifest["stage"] == "protocol":
        if manifest["identity"]["role"] != "afo-recovery-planner":
            raise Refused("PROTOCOL_CAMPAIGN_ROLE_MISMATCH")
        cases = manifest["cases"]
        if len(cases) != 20 or len({c["case_id"] for c in cases}) != 20 or any(c["repeats"] != 5 for c in cases):
            raise Refused("PROTOCOL_DENOMINATOR_CHANGED")
    if manifest["stage"] == "benchmark" and (
        len(manifest["product_cases"]) != 30 or len({c["trial_id"] for c in manifest["product_cases"]}) != 30
    ):
        raise Refused("FROZEN_PRODUCT_COHORT_CHANGED")
    if manifest["expected_trials"] != (100 if manifest["stage"] == "protocol" else 30 if manifest["stage"] == "benchmark" else 1):
        raise Refused("CAMPAIGN_DENOMINATOR_CHANGED")
    for ref in manifest["inputs"]:
        p = Path(ref["path"])
        if not p.is_file() or p.is_symlink() or sha256_file(p) != ref["sha256"]:
            raise Refused("CAMPAIGN_FROZEN_INPUT_CHANGED")
    if manifest["service_persists_after_campaign"] is not True:
        raise Refused("CAMPAIGN_CANNOT_STOP_FACTORY")
    return digest(manifest)


def initial_reservation(manifest, job, eff, *, store=None):
    """Bind an explicit signed qualification envelope BEFORE its first ledger reservation.

    No runtime can infer this allowance from a model proposal, measured size or
    expired grant. Existing ledger identities still reject reservation changes.
    Production calls omit the manifest and retain the role registry allowance.
    """
    from . import authz

    sha = validate(manifest)
    if manifest["stage"] != "protocol" or manifest["source_revision"] != revision():
        raise Refused("QUALIFICATION_INITIAL_RESERVATION_SOURCE_MISMATCH")
    matches = [b for b in manifest["jobs"].values() if b["job_id"] == job["job_id"]]
    if len(matches) != 1 or any(matches[0].get(k) != job[k] for k in ("case", "case_sha256", "mission_id")):
        raise Refused("QUALIFICATION_INITIAL_RESERVATION_BINDING_MISMATCH")
    identity = manifest["identity"]
    if (
        job["model"] != manifest["model_profile"]
        or job["model_digest"] != identity["model_digest"]
        or job["precision"] != identity["precision"]
        or job["role"] != identity["role"]
        or identity["adapter_revision"] != manifest["source_revision"]
    ):
        raise Refused("QUALIFICATION_INITIAL_RESERVATION_IDENTITY_MISMATCH")
    ref = eff.get("authorization_ref")
    grant = authz.find(eff.mode, eff.sha256 or "", ref=ref, action="recover_workorder", request={"model": job["model"]})
    if not grant.allow:
        raise Refused(grant.code)
    record = json.loads((authz.AUTH_DIR / f"{ref}.json").read_text())
    if record.get("signed_runbook_ref") != "qualification-014:" + sha:
        raise Refused("QUALIFICATION_INITIAL_RESERVATION_NOT_SIGNED")
    if manifest.get("mission") is not None:
        from .mission_ledger import MissionLedger

        if store is None:
            raise Refused("QUALIFICATION_AUTHORITATIVE_MISSION_REQUIRED")
        actual = MissionLedger(store).snapshot(job["mission_id"])
        expected = manifest["mission"]
        if any(actual[k] != expected[k] for k in ("mission_id", "lineage", "limits")) or actual["authorization_ref"] != ref:
            raise Refused("QUALIFICATION_REGISTERED_MISSION_DIFFERS_FROM_SIGNED_SCOPE")
    tokens = manifest.get("job_token_reservations", {}).get(job["job_id"], job["reserved_tokens"])
    if tokens > int(eff.get("budgets.max_model_tokens_per_order")) or tokens > identity["context_tokens"]:
        raise Refused("QUALIFICATION_INITIAL_RESERVATION_EXCEEDS_POLICY")
    from .protocol_faults import bind as bind_fault
    from .qualification_state import metadata as qualification_metadata

    return {
        "reserved_tokens": tokens,
        "qualification_manifest_sha256": sha,
        "qualification_identity": identity,
        "qualification_model_profile": manifest["model_profile"],
        "qualification_initial_reservation": {
            "authorization_ref": ref,
            "manifest_sha256": sha,
            "registry_default_tokens": job["reserved_tokens"],
            "authorized_tokens": tokens,
        },
        **bind_fault(manifest, job),
        **qualification_metadata(manifest, job["job_id"]),
    }


def selected_trials(manifest, trial_ids=None):
    selected = set(manifest["jobs"]) if trial_ids is None else set(trial_ids)
    if trial_ids is not None and (not selected or not selected <= set(manifest["jobs"])):
        raise Refused("QUALIFICATION_TRIAL_SCOPE_INVALID")
    return selected


def preflight(manifest, *, live=False, authorization_ref=None, trial_ids=None):
    sha = validate(manifest)
    if trial_ids is not None and manifest["stage"] != "protocol":
        raise Refused("QUALIFICATION_TRIAL_SCOPE_ONLY_FOR_PROTOCOL")
    selected = selected_trials(manifest, trial_ids)
    blockers = []
    if manifest.get("mission") and time.time() >= manifest["mission"]["limits"]["deadline"]:
        blockers.append("QUALIFICATION_MISSION_DEADLINE_EXHAUSTED")
    if not manifest.get("model_profile"):
        blockers.append("EXACT_MODEL_PROFILE_NOT_PROVISIONED")
    if not manifest["inputs"]:
        blockers.append("FROZEN_PRIMARY_INPUTS_NOT_PROVISIONED")
    if manifest["stage"] == "protocol" and len(manifest["jobs"]) != 100:
        blockers.append("APPROVED_100_JOB_BINDINGS_NOT_PROVISIONED")
    elif manifest["stage"] == "protocol":
        expected = {f"{case['case_id']}:{repeat}" for case in manifest["cases"] for repeat in range(5)}
        if set(manifest["jobs"]) != expected or len({b["job_id"] for b in manifest["jobs"].values()}) != 100:
            blockers.append("PROTOCOL_JOB_IDENTITIES_MUST_BE_UNIQUE_AND_MATCH_FROZEN_TRIALS")
    if (manifest["stage"] in ("benchmark", "rcc") or manifest["stage"].startswith("operation-")) and not manifest["jobs"]:
        blockers.append("APPROVED_PRODUCT_JOB_BINDINGS_NOT_PROVISIONED")
    if manifest["stage"] == "protocol":
        from .qualification_inputs import readiness as input_readiness

        for ref in manifest["inputs"]:
            path = Path(ref["path"])
            if path.suffix != ".json" or path.stat().st_size > 4 * 1024 * 1024:
                continue
            try:
                inputs = json.loads(path.read_bytes())
            except (ValueError, UnicodeError):
                continue
            if not isinstance(inputs, dict) or inputs.get("schema") != "forge-c/protocol-inputs-014/1":
                continue
            try:
                blockers.extend(
                    input_readiness(
                        inputs,
                        protocol_faults=manifest.get("protocol_faults", {}),
                        trial_ids=selected if trial_ids is not None else None,
                    )["blockers"]
                )
                if inputs["jobs"] != manifest["jobs"]:
                    blockers.append("FROZEN_PROTOCOL_INPUT_JOB_BINDINGS_CHANGED")
                if any(
                    manifest.get("job_token_reservations", {}).get(job_id, inputs["registry_default_tokens"]) != tokens
                    for job_id, tokens in inputs["requested_initial_reservations"].items()
                ):
                    blockers.append("QUALIFICATION_REQUESTED_ENVELOPES_NOT_FROZEN")
                actual = inputs["model_configuration"]
                if actual["reasoning_effort"] != manifest["identity"]["reasoning"]:
                    blockers.append("QUALIFICATION_EFFECTIVE_REASONING_IDENTITY_MISMATCH")
                if actual["model"] != manifest["model_profile"] or actual["model_digest"] != manifest["identity"]["model_digest"]:
                    blockers.append("QUALIFICATION_EFFECTIVE_MODEL_IDENTITY_MISMATCH")
            except (OSError, Refused, KeyError, TypeError) as exc:
                blockers.append(getattr(exc, "code", "FROZEN_PROTOCOL_INPUTS_INVALID"))
    if live:
        from . import authz, host
        from .policy import load

        eff = load()
        if authorization_ref != eff.get("authorization_ref"):
            blockers.append("QUALIFICATION_POLICY_AUTHORIZATION_REF_MISMATCH")
        if socket.gethostname().split(".")[0] not in ("omniverse", "omniverse2"):
            blockers.append("QWEN_MUST_EXECUTE_ON_OMNIVERSE")
        if revision() != manifest["source_revision"]:
            blockers.append("QUALIFICATION_REVISION_CHANGED")
        if not host.preflight()["ok"]:
            blockers.append("AUTHORITATIVE_DATA_MOUNT_NOT_READY")
        from .operations import Intent, configured

        # Stack services (the request-admitting gateway) receive the private policy/grant paths only with an intent.
        if not configured():
            blockers.append("QUALIFICATION_RUNTIME_OPERATIONS_INTENT_REQUIRED")
        elif Intent().read()["mode"] != "RUNNING":
            blockers.append("QUALIFICATION_OPERATIONS_INTENT_NOT_RUNNING")
        auth = authz.find(
            eff.mode,
            eff.sha256 or "",
            ref=authorization_ref,
            action="recover_workorder",
            request={"model": manifest.get("model_profile")},
        )
        if not auth.allow:
            blockers.append(auth.code)
        else:
            grant = json.loads((authz.AUTH_DIR / f"{authorization_ref}.json").read_text())
            if grant.get("signed_runbook_ref") != "qualification-014:" + sha:
                blockers.append("SIGNED_CAMPAIGN_RUNBOOK_MISMATCH")
    return {
        "manifest_sha256": sha,
        "status": "BLOCKED" if blockers else "PREPARED_NOT_RUN",
        "blockers": sorted(set(blockers)),
        "runtime_implementation": "SEPARATE_TEST_EVIDENCE",
        "local_model_capability": "NOT_RUN",
        "product_success": "NOT_RUN",
        "learning_benefit": "NOT_RUN",
        "operational_availability": "NOT_RUN",
        "trial_scope": sorted(selected) if trial_ids is not None else None,
        "campaign_denominator": manifest["expected_trials"],
    }


def provision(manifest, authorization_ref, *, store=None, limit=8, trial_ids=None):
    """Bind predeclared cases after campaign signing; no grant, mission or allowance is created."""
    readiness = preflight(manifest, live=True, authorization_ref=authorization_ref, trial_ids=trial_ids)
    if readiness["blockers"]:
        return readiness
    if manifest["stage"] != "protocol" or not 1 <= limit <= 32:
        raise Refused("PROTOCOL_PROVISIONING_BOUND_REQUIRED")
    from . import local_agent
    from .mission_ledger import MissionLedger
    from .policy import load
    from .queue import Store

    store = store or Store()
    eff = load()
    sha = digest(manifest)
    changed = 0
    waiting, refused = [], []
    for trial, binding in sorted(manifest["jobs"].items()):
        if trial not in selected_trials(manifest, trial_ids):
            continue
        with store.tx() as c:
            old = c.execute("SELECT record FROM afo_local_agent_jobs WHERE job_id=?", (binding["job_id"],)).fetchone()
        if old:
            job = json.loads(old[0])
            if (
                job["case_sha256"] != binding["case_sha256"]
                or job.get("mission_id") != binding["mission_id"]
                or job.get("qualification_manifest_sha256") not in (None, sha)
            ):
                raise Refused("CAMPAIGN_JOB_REBOUND", trial)
            if sha256_file(Path(job["case"])) != binding["case_sha256"]:
                raise Refused("CAMPAIGN_FROZEN_CASE_CHANGED", trial)
            if job.get("qualification_manifest_sha256") == sha:
                continue
        else:
            case = Path(binding["case"])
            if case.is_symlink() or sha256_file(case) != binding["case_sha256"]:
                raise Refused("CAMPAIGN_FROZEN_CASE_CHANGED", trial)
            doc = json.loads(case.read_text())
            order = store.order(doc["bundle"]["order_id"])
            if not order or MissionLedger(store).for_order(order["order_id"]) != binding["mission_id"]:
                raise Refused("CAMPAIGN_MISSION_MUST_ALREADY_BE_AUTHORIZED_AND_REGISTERED", trial)
            from . import qualification_intake

            intake = qualification_intake.context(store, order)
            if intake and intake["manifest_sha256"] != sha:
                raise Refused("QUALIFICATION_WRAPPER_INTAKE_REQUIRED", trial)
            if order["state"] == "ADMITTED" and intake:
                order = qualification_intake.start(store, order, sha)
            elif intake:
                # The scheduler admitted these exact bytes; they must still match before the role job binds.
                qualification_intake.verify_files(Path(intake["root"]), intake["intake"], intake["trial_id"])
            if order["state"] not in ("RUNNING", "WAITING_RECOVERY"):
                waiting.append(trial)
                continue
            try:
                job = local_agent.prepare(
                    store,
                    order,
                    doc["bundle"]["attempt_id"],
                    "afo-recovery-planner",
                    case,
                    Path(doc["workspace"]),
                    eff,
                    qualification_manifest=manifest,
                )
            except Refused as exc:
                if not intake or local_agent.records(store, order["order_id"]):
                    raise
                # A deterministic refusal must not hold the single capacity slot for the rest of the campaign.
                refused.append({"trial": trial, "code": qualification_intake.refuse(store, order, exc.code)})
                continue
            if job["job_id"] != binding["job_id"] or job["case_sha256"] != binding["case_sha256"]:
                raise Refused("CAMPAIGN_PREDECLARED_JOB_IDENTITY_MISMATCH", trial)
        if job["state"] != "PREPARED" or (job.get("factory_revision") or {}).get("commit") != manifest["source_revision"]:
            raise Refused("CAMPAIGN_PROVISIONING_REQUIRES_UNDISPATCHED_EXACT_REVISION", trial)
        identity = manifest["identity"]
        if (
            job.get("model") != manifest["model_profile"]
            or job.get("model_digest") != identity["model_digest"]
            or job.get("precision") != identity["precision"]
            or job["role"] != identity["role"]
        ):
            raise Refused("CAMPAIGN_JOB_CONFIGURATION_CHANGED", trial)
        # The case and its hash stay frozen. Campaign binding is deterministic
        # administrative metadata, so signing does not require a hash cycle.
        from .qualification_state import metadata as qualification_metadata

        archived = qualification_metadata(manifest, job["job_id"])
        with store.tx() as c:
            row = c.execute("SELECT record FROM afo_local_agent_jobs WHERE job_id=?", (job["job_id"],)).fetchone()
            current = json.loads(row[0])
            if current["state"] != "PREPARED" or current.get("qualification_manifest_sha256") not in (None, sha):
                raise Refused("CAMPAIGN_PROVISIONING_FENCED", trial)
            current["qualification_manifest_sha256"] = sha
            current["qualification_identity"] = identity
            current["qualification_model_profile"] = manifest["model_profile"]
            current.update(archived)
            c.execute("UPDATE afo_local_agent_jobs SET record=? WHERE job_id=?", (json.dumps(current), job["job_id"]))
        changed += 1
        if changed >= limit:
            return {"status": "PROVISIONING_IN_PROGRESS", "provisioned_this_call": changed, "inference_requests": 0}
    return {
        "status": "WAITING_AFO_ADMISSION"
        if waiting
        else "ROLE_JOB_REFUSED_WRAPPER_CLOSED"
        if refused and not changed
        else "PROVISIONED_NOT_RUN",
        "provisioned_this_call": changed,
        "waiting_trials": waiting,
        "refused_trials": refused,
        "inference_requests": 0,
    }


def step(manifest, authorization_ref, destination, *, store=None, trial_ids=None):
    """One bounded native control-plane step. Repeated calls adopt the same job; campaign end never stops services."""
    report = preflight(manifest, live=True, authorization_ref=authorization_ref, trial_ids=trial_ids)
    if report["blockers"]:
        return report
    if manifest["stage"] in ("benchmark", "rcc"):
        return product_step(manifest, destination, store=store)
    if manifest["stage"] != "protocol":
        return {**report, "status": "BLOCKED", "blockers": ["USE_EXISTING_AFO_SOAK_ENTRYPOINT_FOR_OPERATIONAL_STAGE"]}
    from . import local_agent
    from .policy import load
    from .queue import Store

    store = store or Store()
    eff = load()
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    for case in manifest["cases"]:
        for repeat in range(5):
            trial = f"{case['case_id']}:{repeat}"
            if trial not in selected_trials(manifest, trial_ids):
                continue
            path = dest / (trial.replace(":", "-") + ".json")
            if path.exists():
                continue
            binding = manifest["jobs"].get(trial)
            if not binding:
                raise Refused("CAMPAIGN_JOB_BINDING_MISSING", trial)
            with store.tx() as c:
                row = c.execute("SELECT record FROM afo_local_agent_jobs WHERE job_id=?", (binding["job_id"],)).fetchone()
            if not row:
                raise Refused("CAMPAIGN_JOB_UNPROVISIONED", trial)
            job = json.loads(row[0])
            if job["case_sha256"] != binding["case_sha256"] or job.get("mission_id") != binding["mission_id"]:
                raise Refused("CAMPAIGN_JOB_REBOUND", trial)
            job = local_agent.poll(store, store.order(job["order_id"]), job, eff)
            if job["state"] in ("PREPARED", "LAUNCHING", "RUNNING"):
                return {"status": "IN_PROGRESS", "trial": trial, "job_id": job["job_id"]}
            row = protocol_observation(store, manifest, trial, job)
            from .qualification_state import record_completed

            recorded = record_completed(store, job, destination=dest)
            if recorded:
                row = recorded["row"]
            else:
                immutable_json(path, row)
            return {"status": "RECORDED", "trial": trial, "row_sha256": sha256_file(path)}
    return {
        "status": "CAMPAIGN_WINDOW_COMPLETE" if trial_ids is None else "TRIAL_SUBSET_COMPLETE",
        "factory_service": "CONTINUES_UNCHANGED",
        "report": protocol_report(manifest, load_rows(dest)),
    }


def protocol_observation(store, manifest, trial, job):
    """Read existing broker/native facts without dispatch, authority renewal or model calls."""
    case_id, raw_repeat = trial.rsplit(":", 1)
    repeat = int(raw_repeat)
    case = next((c for c in manifest["cases"] if c["case_id"] == case_id), None)
    if case is None:
        raise Refused("QUALIFICATION_UNKNOWN_FROZEN_TRIAL")
    report = {"manifest_sha256": digest(manifest)}
    from .completion_receipt import Context, Receipts

    binding_error = None
    try:
        candidates = Receipts(store).for_job(Context.from_job(store, job["job_id"]))
    except (Refused, OSError, ValueError) as exc:
        candidates = []
        binding_error = getattr(exc, "code", "QUALIFICATION_CASE_UNAVAILABLE")
    receipt = (
        Receipts(store).latest(job["receipt_id"])
        if job.get("receipt_id") and binding_error is None
        else (candidates[-1] if candidates else None)
    )
    observed = (
        receipt["decision"]
        if receipt and receipt["admissibility_state"] == "ACCEPTED"
        else "REJECTED"
        if receipt
        else "FAILED_PROTOCOL"
    )
    diagnostic = None
    if receipt and receipt.get("submission_state") == "REJECTED":
        with store.tx() as c:
            stored = c.execute(
                "SELECT record FROM afo_semantic_proposals WHERE proposal_sha256=? AND job_id=?",
                (receipt["proposal_sha256"], job["job_id"]),
            ).fetchone()
        diagnostic = json.loads(stored[0]).get("diagnostic") if stored else None
    from .execution_lifecycle import Executions

    execution = Executions(store).get(job["job_id"])
    with store.tx() as c:
        requests = [json.loads(r[0]) for r in c.execute("SELECT record FROM afo_request_ledger WHERE job_id=?", (job["job_id"],))]
    reported = (
        sum(r["reported_tokens"] for r in requests)
        if requests and all(r.get("reported_tokens") is not None for r in requests)
        else None
    )
    if job["state"] == "REVOKED":
        observed = "REVOKED"
    elif (job.get("error") or "").startswith("MISSION_") and "EXHAUSTED" in job["error"]:
        observed = "EXHAUSTED"
    elif execution and execution["task_outcome"] != "ACTIVE" and execution["resource_lease"] == "HELD":
        observed = "BLOCKED_LIVE_HELD"
    if binding_error:
        observed = "UNKNOWN"
    row = {
        "execution": execution,
        "job_state": job["state"],
        "job_error": job.get("error"),
        "trial_id": trial,
        "case_id": case["case_id"],
        "repeat": repeat,
        "expected": case["expected"],
        "observed": observed,
        "manifest_sha256": report["manifest_sha256"],
        "native_run_id": job.get("run_id"),
        "job_id": job["job_id"],
        "case_sha256": job["case_sha256"],
        "case_binding_valid": binding_error is None,
        "observation_blockers": [binding_error] if binding_error else [],
        "receipt": receipt,
        "proposal_diagnostic": diagnostic,
        "reported_tokens": reported,
        "native_fabro_reported_tokens": job.get("reported_tokens"),
        "request_count": len(requests),
        "requests_sha256": digest(requests),
        "usage_source": "GATEWAY_REQUEST_LEDGER",
        "reserved_tokens": job["reserved_tokens"],
        "false_success": None,
        "duplicate_effects": None,
        "authority_escapes": None,
        "usage_unknown": reported is None,
    }
    from .protocol_faults import evidence_kind, observation_matches

    with store.tx() as c:
        injection = c.execute(
            "SELECT record FROM afo_execution_evidence WHERE job_id=? AND kind=?",
            (job["job_id"], evidence_kind(job)),
        ).fetchone()
    if job.get("qualification_fault"):
        row["declared_fault"] = job["qualification_fault"]
        row["fault_observation"] = json.loads(injection[0]) if injection else None
        with store.tx() as c:
            adoption = c.execute(
                "SELECT record FROM afo_execution_evidence WHERE job_id=? AND kind='NONCE_LIST_ADOPTION'", (job["job_id"],)
            ).fetchone()
        row["native_adoption"] = json.loads(adoption[0]) if adoption else None
        if (
            binding_error is None
            and job["qualification_fault"]["recipe"]["boundary"] == "before-evidence-read"
            and job.get("error") in ("EVIDENCE_MISSING_OR_CHANGED", "EVIDENCE_PATH_ESCAPE")
            and observation_matches(manifest, row)
        ):
            row["observed"] = "REJECTED"
    return row


def product_step(manifest, destination, *, store=None):
    """Observe the approved queue's work; the existing Conductor owns dispatch and recovery."""
    from .qualification_capture import product_row
    from .queue import Store

    store = store or Store()
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    planned = [c["trial_id"] for c in manifest["product_cases"]] if manifest["stage"] == "benchmark" else ["rcc:01"]
    for trial in planned:
        path = dest / (trial.replace(":", "-") + ".json")
        if path.exists():
            continue
        binding = manifest["jobs"].get(trial)
        if not binding:
            raise Refused("CAMPAIGN_JOB_BINDING_MISSING", trial)
        row = product_row(store, manifest, trial, binding)
        if row["order_state"] not in ("READY_FOR_OFFLINE_REVIEW", "BLOCKED", "CANCELLED", "FAILED"):
            return {"status": "IN_PROGRESS", "trial": trial, "observation": row}
        if row["qualification_status"] != "AUDITED":
            return {
                "status": "INCOMPLETE",
                "trial": trial,
                "observation": row,
                "blockers": ["HASH_BOUND_INDEPENDENT_ORACLE_AUDIT_REQUIRED"],
            }
        immutable_json(path, row)
        return {"status": "RECORDED", "trial": trial, "row_sha256": sha256_file(path)}
    rows = load_rows(dest)
    return (
        product_report(manifest, rows)
        if manifest["stage"] == "benchmark"
        else {
            "status": "PASS"
            if rows and rows[0]["sealed_ready"] and rows[0]["native_all_six_gates"] and rows[0]["false_ready"] is False
            else "FAIL",
            "product_recovery": "INDEPENDENT_SEALED_PACKAGE_AND_ALL_NATIVE_GATES",
            "factory_service": "CONTINUES_UNCHANGED",
        }
    )


def load_rows(directory):
    return [json.loads(p.read_text()) for p in sorted(Path(directory).glob("*.json"))]


def protocol_report(manifest, rows):
    sha = validate(manifest)
    expected = {f"{c['case_id']}:{i}": c for c in manifest["cases"] for i in range(5)}
    ids = [r["trial_id"] for r in rows]
    if len(set(ids)) != len(ids) or any(i not in expected for i in ids):
        raise Refused("PROTOCOL_TRIAL_IDENTITY_CHANGED")
    correct = useful = 0
    failures = []
    for original in rows:
        row = dict(original)
        from .qualification_capture import independent_audit

        audit = independent_audit(None, manifest, row["trial_id"], original)
        if audit:
            facts = audit.get("observations", {})
            for field in ("false_success", "duplicate_effects", "authority_escapes"):
                row[field] = facts.get(field)
            row["independent_audit"] = audit["audit_artifact"]
        case = expected[row["trial_id"]]
        if row["manifest_sha256"] != sha:
            raise Refused("PROTOCOL_RESULT_MANIFEST_CHANGED")
        receipt = row.get("receipt") or {}
        from .protocol_faults import observation_matches

        ok = (
            row["observed"] == case["expected"]
            and row.get("case_binding_valid") is not False
            and observation_matches(manifest, row)
            and (
                row.get("native_run_id")
                or (
                    case["case_id"] in ("revoked-before-dispatch", "expired-mission")
                    and (row.get("execution") or {}).get("execution_liveness") == "NOT_STARTED"
                )
            )
            and row.get("independent_audit") is not None
            and row.get("false_success") is False
            and row.get("duplicate_effects") == 0
            and row.get("authority_escapes") == 0
        )
        if case["recoverable"]:
            ok = (
                ok
                and receipt.get("admissibility_state") == "ACCEPTED"
                and receipt.get("decision") == "PROPOSE_REPAIR"
                and bool(receipt.get("bound_plan"))
                and row.get("request_count", 0) > 0
            )
        correct += bool(ok)
        useful += bool(receipt.get("admissibility_state") == "ACCEPTED" and receipt.get("decision") == "PROPOSE_REPAIR")
        if not ok:
            failures.append(row["trial_id"])
    return {
        "status": "NOT_RUN"
        if not rows
        else "PASS"
        if len(rows) == 100 and correct == 100
        else "FAIL"
        if failures or len(rows) == 100
        else "INCOMPLETE",
        "expected_denominator": 100,
        "observed_denominator": len(rows),
        "correct_outcomes": correct,
        "useful_plan_count": useful,
        "failures": failures,
        "missing": sorted(set(expected) - set(ids)),
        "usage_unknown": sum(r.get("usage_unknown", True) for r in rows),
        "native_capability_only": True,
        "product_recovery_proven": False,
        "availability_proven": False,
    }


def product_report(manifest, rows):
    validate(manifest)
    planned = {c["trial_id"] for c in manifest["product_cases"]}
    ids = [r["trial_id"] for r in rows]
    if len(set(ids)) != len(ids) or not set(ids) <= planned:
        raise Refused("BENCHMARK_DENOMINATOR_CHANGED")
    if not rows:
        return {"status": "NOT_RUN", "expected_denominator": 30}
    ready = sum(r.get("sealed_ready") is True and r.get("native_all_six_gates") is True for r in rows)
    critical = [d for r in rows for d in r.get("critical_defects", [])]
    missing_critical = sorted(set(manifest["critical_defect_ids"]) - {d.get("case_id") for d in critical})
    complete = all(
        type(r.get(k)) is int and r[k] >= 0
        for r in rows
        for k in ("structured_calls", "invalid_structured", "complete_prompt_tokens")
    )
    calls = sum(r["structured_calls"] for r in rows) if complete else None
    invalid = sum(r["invalid_structured"] for r in rows) if complete else None
    prompts = [r["complete_prompt_tokens"] for r in rows] if complete else []
    base = (manifest.get("baseline") or {}).get("median_complete_prompt_tokens")
    reduction = 1 - statistics.median(prompts) / base if prompts and base else None
    ok = (
        len(rows) == 30
        and ready >= 27
        and not missing_critical
        and critical
        and all(d.get("independently_detected") is True for d in critical)
        and all(r.get("false_ready") is False and r.get("required_evidence_complete") is True for r in rows)
        and complete
        and calls > 0
        and invalid / calls < 0.01
        and reduction is not None
        and reduction >= 0.5
    )
    return {
        "status": "PASS" if ok else "FAIL" if len(rows) == 30 else "INCOMPLETE",
        "expected_denominator": 30,
        "observed_denominator": len(rows),
        "verified_ready": ready,
        "critical_exposures": len(critical),
        "missing_critical_cases": missing_critical,
        "complete_accounting": complete,
        "structured_calls": calls,
        "invalid_rate": invalid / calls if calls else None,
        "median_prompt_reduction": reduction,
        "learning_benefit": "SEPARATE_COMPARISON",
        "operational_availability": "SEPARATE_CAMPAIGN",
    }


def inspector_report(required_obligations, claims, independent_verdicts):
    required = set(required_obligations)
    if len({v["obligation_id"] for v in independent_verdicts}) != len(independent_verdicts):
        raise Refused("INSPECTION_ORACLE_DUPLICATED")
    known = {
        v["obligation_id"]: v
        for v in independent_verdicts
        if v.get("producer") in ("reference", "metamorphic", "mutant", "SMT", "deterministic_gate")
        and v.get("evidence_ref")
        and type(v.get("pass")) is bool
    }
    unverified = sorted(required - set(known))
    escaped = sorted(k for k in required & set(known) if known[k].get("pass") is False and claims.get(k) == "PASS")
    return {
        "status": "PASS" if required and not unverified and not escaped else "FAIL",
        "required": len(required),
        "independently_covered": len(required & set(known)),
        "unverified": unverified,
        "escaped_defects": escaped,
        "same_model_agreement_is_independent_evidence": False,
    }


def configuration_comparison(manifest, baseline, candidate):
    from ..lrtx.role_capability import IDENTITY

    if baseline.get("manifest_sha256") != digest(manifest) or candidate.get("manifest_sha256") != digest(manifest):
        raise Refused("COMPARISON_CASES_CHANGED")
    if baseline.get("measured") is not True or not baseline.get("native_run_ids"):
        raise Refused("UNCHANGED_BASELINE_MEASUREMENT_REQUIRED")
    changed = [k for k in IDENTITY if baseline["identity"][k] != candidate["identity"][k]]
    if len(changed) != 1:
        raise Refused("ONE_CONTROLLED_CONFIGURATION_FACTOR_REQUIRED")
    if baseline["case_ids"] != candidate["case_ids"] or not candidate.get("independent_outcomes"):
        raise Refused("COMPARISON_DENOMINATOR_OR_ORACLE_MISSING")
    return {
        "changed_factor": changed[0],
        "baseline_identity": baseline["identity"],
        "candidate_identity": candidate["identity"],
        "rcc_success_prerequisite": False,
        "automatic_selection": False,
        "automatic_deployment": False,
    }


def rcc_report(package_path, gates):
    from .dispatch import package_verdict

    verdict = package_verdict(Path(package_path))
    ready = (
        verdict.get("verdict") == "READY_FOR_OFFLINE_REVIEW"
        and set(gates) == {f"SWE.{i}" for i in range(1, 7)}
        and all(v == "PASS" for v in gates.values())
    )
    return {
        "status": "PASS" if ready else "FAIL",
        "package_verdict": verdict,
        "gates": gates,
        "gpio_requires": [
            "RCC_READY",
            "QUALIFIED_GPIO_PROFILE",
            "AUTHORITATIVE_GPIO_INPUTS",
            "FROZEN_INTAKE",
            "CURRENT_GPIO_AUTHORITY",
        ],
    }


def gpio_admission(prerequisites):
    required = ("rcc_ready", "qualified_profile", "authoritative_inputs", "frozen_intake", "authorized")
    missing = [k for k in required if prerequisites.get(k) is not True]
    return {"admit": not missing, "missing": missing}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=["freeze", "dry-run", "enroll", "provision", "step", "report"])
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--stage", choices=STAGES, default="protocol")
    ap.add_argument("--identity", type=Path)
    ap.add_argument("--input", type=Path, action="append", default=[])
    ap.add_argument("--jobs", type=Path)
    ap.add_argument("--mission", type=Path, help="explicit finite qualification mission and lineage, frozen before signing")
    ap.add_argument(
        "--trial",
        action="append",
        help="evaluate/enroll/provision/step only these frozen protocol trial IDs; report denominator stays 100",
    )
    ap.add_argument("--protocol-faults", type=Path, help="explicit supported per-trial interventions, frozen before signing")
    ap.add_argument(
        "--job-token-reservations", type=Path, help="explicit per-job initial qualification allowances, frozen before signing"
    )
    ap.add_argument("--results", type=Path)
    ap.add_argument("--authorization-ref")
    ap.add_argument("--model-profile")
    args = ap.parse_args(argv)
    if args.trial and args.command in ("freeze", "report"):
        ap.error("--trial scopes readiness/provisioning/stepping; freeze and report always retain the whole campaign")
    if args.command == "freeze":
        if args.identity is None:
            ap.error("--identity is required for freeze")
        manifest = freeze(
            args.stage,
            args.manifest,
            identity=json.loads(args.identity.read_text()),
            inputs=args.input,
            jobs=json.loads(args.jobs.read_text()) if args.jobs else None,
            model_profile=args.model_profile,
            job_token_reservations=json.loads(args.job_token_reservations.read_text()) if args.job_token_reservations else None,
            protocol_faults=json.loads(args.protocol_faults.read_text()) if args.protocol_faults else None,
            mission=json.loads(args.mission.read_text()) if args.mission else None,
        )
        out = {"status": "FROZEN_NOT_RUN", "manifest_sha256": digest(manifest)}
    else:
        manifest = json.loads(args.manifest.read_text())
        if args.command == "dry-run":
            out = preflight(manifest, trial_ids=args.trial)
        elif args.command == "enroll":
            from .qualification_intake import enroll

            out = enroll(manifest, args.authorization_ref, trial_ids=args.trial)
        elif args.command == "provision":
            out = provision(manifest, args.authorization_ref, trial_ids=args.trial)
        elif args.command == "step":
            if args.results is None:
                ap.error("--results required")
            out = step(manifest, args.authorization_ref, args.results, trial_ids=args.trial)
        else:
            rows = load_rows(args.results) if args.results else []
            if manifest["stage"] == "protocol":
                out = protocol_report(manifest, rows)
            elif manifest["stage"] == "benchmark":
                out = product_report(manifest, rows)
            elif manifest["stage"] == "rcc":
                out = {
                    "status": "PASS"
                    if len(rows) == 1
                    and rows[0].get("sealed_ready")
                    and rows[0].get("native_all_six_gates")
                    and rows[0].get("false_ready") is False
                    else "NOT_RUN"
                    if not rows
                    else "FAIL",
                    "expected_denominator": 1,
                }
            else:
                out = {"status": "NOT_RUN", "entrypoint": "forge_factory.afo.operational_campaign report"}
    print(json.dumps(out, indent=2))
    return 2 if out.get("status") in ("FAIL", "BLOCKED") else 0


if __name__ == "__main__":
    raise SystemExit(main())
