"""Explicit signed protocol response faults at the native adapter boundary.

No fault is enabled by a model, environment flag, case name or campaign alone.
The existing signed manifest binds each intervention before initial preparation.
These controls exercise refusal paths; they do not measure unmodified model
competence or independently establish a successful outcome.
"""

from __future__ import annotations

import hashlib
import json
import time

from ..common import sha256_file
from .durable import Refused, canonical, digest, strict_json
from .qualification_inputs import FAULT_RECIPES

SUPPORTED = {"administrative-forgery", "empty-output", "malformed-output", "unqualified-local-alternative"}


def validate_catalogue(catalogue, jobs):
    if not isinstance(catalogue, dict) or not set(catalogue) <= set(jobs):
        raise Refused("QUALIFICATION_FAULT_CATALOGUE_INVALID")
    for trial, recipe in catalogue.items():
        name = trial.rsplit(":", 1)[0]
        if name not in SUPPORTED or recipe != FAULT_RECIPES[name]:
            raise Refused("QUALIFICATION_FAULT_RECIPE_UNSUPPORTED", trial)


def bind(manifest, job):
    """Called only after initial_reservation verifies the exact owner signature."""
    from pathlib import Path

    matches = [trial for trial, binding in manifest["jobs"].items() if binding["job_id"] == job["job_id"]]
    if len(matches) != 1:
        raise Refused("QUALIFICATION_FAULT_JOB_BINDING_INVALID")
    trial = matches[0]
    recipe = manifest.get("protocol_faults", {}).get(trial)
    if recipe is None:
        return {}
    case = json.loads(Path(job["case"]).read_text())
    fixture = case.get("qualification_fixture") or {}
    if (
        fixture.get("source_kind") != "SEEDED_PROTOCOL_NOT_PRODUCT"
        or fixture.get("evaluation_holdout") is not True
        or fixture.get("trial_id") != trial
        or fixture.get("prospective_fault") != recipe
    ):
        raise Refused("QUALIFICATION_FAULT_REQUIRES_EXPLICIT_FROZEN_FIXTURE")
    return {"qualification_fault": {"trial_id": trial, "recipe": recipe, "manifest_sha256": digest(manifest)}}


def apply_response(store, job, raw, eff):
    """Apply a fixed intervention once logically; preserve only bounded hashes in the existing ledger."""
    fault = job.get("qualification_fault")
    if fault is None:
        return raw
    from pathlib import Path

    from . import authz, local_agent
    from .completion_receipt import Context
    from .execution_lifecycle import Executions

    name = fault["trial_id"].rsplit(":", 1)[0]
    if name not in SUPPORTED or fault["recipe"] != FAULT_RECIPES[name]:
        raise Refused("QUALIFICATION_FAULT_RECIPE_UNSUPPORTED")
    if not isinstance(raw, str) or len(raw.encode()) > 65536:
        raise Refused("QUALIFICATION_RESPONSE_FAULT_INPUT_INVALID")
    ctx = Context.from_job(store, job["job_id"])
    if ctx.launch_nonce != job["nonce"] or ctx.case_sha256 != job["case_sha256"]:
        raise Refused("QUALIFICATION_FAULT_JOB_BINDING_INVALID")
    with store.tx() as c:
        row = c.execute("SELECT record FROM afo_local_agent_jobs WHERE job_id=?", (job["job_id"],)).fetchone()
    current = json.loads(row[0])
    if current.get("qualification_fault") != fault or fault["manifest_sha256"] != current.get("qualification_manifest_sha256"):
        raise Refused("QUALIFICATION_FAULT_NOT_BOUND_TO_JOB")
    if (
        current.get("policy_sha256") != eff.sha256
        or current.get("model") != job.get("model")
        or time.time() >= current["deadline_epoch"]
    ):
        raise Refused("QUALIFICATION_FAULT_POLICY_OR_DEADLINE_CHANGED")
    if sha256_file(Path(job["case"])) != ctx.case_sha256:
        raise Refused("QUALIFICATION_FAULT_CASE_CHANGED")
    ref = eff.get("authorization_ref")
    order = store.order(ctx.order_id)
    if not order or order["state"] not in ("RUNNING", "WAITING_RECOVERY"):
        raise Refused("QUALIFICATION_FAULT_ORDER_NOT_ACTIVE")
    request = {**local_agent.request_for(order), "model": current["model"]}
    grant = authz.find(eff.mode, eff.sha256 or "", ref=ref, action="recover_workorder", request=request)
    if not grant.allow:
        raise Refused(grant.code)
    record = json.loads((authz.AUTH_DIR / f"{ref}.json").read_text())
    if record.get("signed_runbook_ref") != "qualification-014:" + fault["manifest_sha256"]:
        raise Refused("QUALIFICATION_FAULT_NOT_SIGNED")
    live = Executions(store).get(job["job_id"]) or {}
    if (
        live.get("launch_nonce") != job["nonce"]
        or live.get("resource_lease") != "HELD"
        or live.get("task_outcome") != "ACTIVE"
        or live.get("authorization_state") != "VALID"
        or live.get("admission_state") not in ("DISPATCH_INTENT_RECORDED", "NATIVE_ACCEPTED")
    ):
        raise Refused("QUALIFICATION_FAULT_EXECUTION_NOT_ACTIVE")
    if name == "empty-output":
        changed = ""
    elif name == "malformed-output":
        changed = raw.rstrip()[:-1] if raw.strip().endswith("}") else '{"qualification_incomplete":'
    else:
        value = strict_json(raw)
        if not isinstance(value, dict):
            raise Refused("QUALIFICATION_RESPONSE_FAULT_REQUIRES_JSON_OBJECT")
        if name == "administrative-forgery":
            value["order_id"] = "qualification-forged-administrative-id"
        else:
            if value.get("decision") != "PROPOSE_REPAIR":
                raise Refused("QUALIFICATION_MODEL_SWITCH_FAULT_REQUIRES_REPAIR_PROPOSAL")
            value["strategy"] = "SWITCH_PREAPPROVED_MODEL_PROFILE"
            value["model_profile"] = "qualification-unqualified-model"
        changed = canonical(value).decode()
    evidence = {
        "schema": "forge-c/protocol-fault-observation/1",
        "job_id": job["job_id"],
        "nonce": job["nonce"],
        "case_sha256": ctx.case_sha256,
        **fault,
        "original_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "injected_response_sha256": hashlib.sha256(changed.encode()).hexdigest(),
        "scope": "DECLARED_INTERVENTION_NOT_UNMODIFIED_MODEL_COMPETENCE",
    }
    # Immutable insert in the authoritative evidence table: a changed replay is
    # refused rather than overwriting the first intervention's observation.
    with store.tx() as c:
        previous = c.execute(
            "SELECT sha256 FROM afo_execution_evidence WHERE job_id=? AND kind='PROTOCOL_RESPONSE_FAULT'", (job["job_id"],)
        ).fetchone()
        if previous and previous[0] != digest(evidence):
            raise Refused("QUALIFICATION_FAULT_REPLAY_CHANGED")
        c.execute(
            "INSERT OR IGNORE INTO afo_execution_evidence VALUES (?,?,?,?)",
            (job["job_id"], "PROTOCOL_RESPONSE_FAULT", canonical(evidence).decode(), digest(evidence)),
        )
    return changed


def observation_matches(manifest, row):
    """An expected refusal cannot stand in for the declared fault exposure."""
    recipe = manifest.get("protocol_faults", {}).get(row["trial_id"])
    if recipe is None:
        return True
    binding = manifest["jobs"][row["trial_id"]]
    fact = row.get("fault_observation") or {}
    declared = row.get("declared_fault") or {}
    if not isinstance(fact, dict) or not isinstance(declared, dict):
        return False
    return (
        declared == {"trial_id": row["trial_id"], "recipe": recipe, "manifest_sha256": digest(manifest)}
        and all(fact.get(k) == v for k, v in declared.items())
        and fact.get("job_id") == binding["job_id"] == row["job_id"]
        and fact.get("case_sha256") == binding["case_sha256"]
        and fact.get("nonce") == (row.get("execution") or {}).get("launch_nonce")
        and fact.get("schema") == "forge-c/protocol-fault-observation/1"
        and fact.get("scope") == "DECLARED_INTERVENTION_NOT_UNMODIFIED_MODEL_COMPETENCE"
        and all(
            isinstance(fact.get(k), str) and len(fact[k]) == 64 and all(c in "0123456789abcdef" for c in fact[k])
            for k in ("original_response_sha256", "injected_response_sha256")
        )
        and fact["original_response_sha256"] != fact["injected_response_sha256"]
    )
