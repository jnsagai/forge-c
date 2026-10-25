"""Collect actual AFO/native facts and independently produced qualification oracles.

No launch, model call, service effect, grant change or inferred PASS. Oracle files
must be hash-bound, outside the product workspace, and produced by independent
verification tooling. Unknown observations remain incomplete.
"""

from __future__ import annotations
import json
from pathlib import Path
from ..common import sha256_file, state_dir
from .durable import Refused, digest

PRODUCERS = {"CRE_VERIFIER", "REFERENCE_HARNESS", "METAMORPHIC_HARNESS", "MUTANT_HARNESS"}


def independent_audit(ref, manifest, trial, observation, *, workspace=None):
    root = (state_dir() / "lrtx/qualification-audits").resolve()
    if not ref:
        candidate = root / digest(manifest) / (trial.replace(":", "-") + ".json")
        if not candidate.is_file():
            return None
        ref = {"path": str(candidate), "sha256": sha256_file(candidate)}
    path = Path(ref["path"])
    if (
        path.is_symlink()
        or root not in path.resolve().parents
        or (workspace and Path(workspace).resolve() in path.resolve().parents)
        or sha256_file(path) != ref["sha256"]
    ):
        raise Refused("QUALIFICATION_AUDIT_REFERENCE_INVALID")
    record = json.loads(path.read_text())
    if (
        record.get("schema") != "forge-c/independent-qualification-audit/1"
        or record.get("producer") not in PRODUCERS
        or record.get("manifest_sha256") != digest(manifest)
        or record.get("source_revision") != manifest["source_revision"]
        or record.get("trial_id") != trial
        or record.get("observation_sha256") != digest(observation)
        or not record.get("oracle_refs")
    ):
        raise Refused("INDEPENDENT_QUALIFICATION_AUDIT_MISMATCH")
    for oracle in record["oracle_refs"]:
        p = Path(oracle["path"])
        if p.is_symlink() or sha256_file(p) != oracle["sha256"]:
            raise Refused("INDEPENDENT_ORACLE_CHANGED")
    return {**record, "audit_artifact": ref}


def product_observation(store, manifest, trial, binding):
    from .runtime import workspace_of
    from .dispatch import package_verdict
    from ..inspection.engine import Store as InspectionStore
    from .execution_lifecycle import Executions

    order = store.order(binding["order_id"])
    if not order:
        raise Refused("QUALIFICATION_ORDER_UNPROVISIONED")
    attempts = [a for a in store.attempts(order["order_id"]) if a["attempt_id"] == binding["attempt_id"]]
    if len(attempts) != 1:
        raise Refused("QUALIFICATION_ATTEMPT_UNPROVISIONED")
    attempt = attempts[0]
    ws = workspace_of(attempt)
    p = ws / ".forge-run/package.json"
    gates = {f"SWE.{i}": InspectionStore(ws).gate(f"SWE.{i}")["decision"] for i in range(1, 7)}
    verdict = package_verdict(p) if p.is_file() else {"verdict": "NOT_RUN"}
    with store.tx() as c:
        job_row = c.execute("SELECT record FROM afo_product_jobs WHERE job_id=?", (binding["job_id"],)).fetchone()
    if not job_row:
        raise Refused("QUALIFICATION_PRODUCT_JOB_UNPROVISIONED")
    job = json.loads(job_row[0])
    if (
        job["order_id"] != order["order_id"]
        or job["attempt_id"] != attempt["attempt_id"]
        or job["mission_id"] != binding["mission_id"]
    ):
        raise Refused("QUALIFICATION_PRODUCT_BINDING_CHANGED")
    if (job.get("factory_revision") or {}).get("commit") != manifest["source_revision"] or job.get("model") != manifest[
        "model_profile"
    ]:
        raise Refused("QUALIFICATION_PRODUCT_CONFIGURATION_CHANGED")
    execution = Executions(store).get(job["job_id"])
    with store.tx() as c:
        requests = [json.loads(r[0]) for r in c.execute("SELECT record FROM afo_request_ledger WHERE job_id=?", (job["job_id"],))]
        metadata = [
            json.loads(r[0])
            for r in c.execute(
                "SELECT record FROM afo_execution_evidence WHERE job_id=? AND kind LIKE 'REQUEST_METADATA:%'", (job["job_id"],)
            )
        ]
    measured = {r["request_id"]: r for r in metadata}
    complete = bool(requests) and all(r["request_id"] in measured for r in requests)
    observation = {
        "trial_id": trial,
        "manifest_sha256": digest(manifest),
        "job_id": job["job_id"],
        "order_state": order["state"],
        "attempt_id": attempt["attempt_id"],
        "native_run_id": attempt["record"].get("fabro_run_id"),
        "execution": execution,
        "package_sha256": sha256_file(p) if p.is_file() else None,
        "package_verdict": verdict,
        "gates": gates,
        "requests_sha256": digest(requests),
        "request_metadata_sha256": digest(metadata),
        "complete_prompt_tokens": sum(measured[r["request_id"]]["measurement"]["input_tokens"] for r in requests)
        if complete
        else None,
        "prompt_measurement_method": "CONSERVATIVE_ADMISSION_BOUND_NOT_NATIVE_TOKENIZER",
        "structured_calls": sum(m.get("schema_mode") in ("json_schema", "json_object") for m in metadata) if complete else None,
        "usage_unknown": not requests or any(r.get("reported_tokens") is None for r in requests),
    }
    return observation, ws


def product_row(store, manifest, trial, binding):
    observation, ws = product_observation(store, manifest, trial, binding)
    audit = independent_audit(binding.get("independent_audit"), manifest, trial, observation, workspace=ws)
    facts = audit.get("observations", {}) if audit else {}
    return {
        **observation,
        "observation_sha256": digest(observation),
        "sealed_ready": observation["package_verdict"].get("verdict") == "READY_FOR_OFFLINE_REVIEW",
        "native_all_six_gates": all(v == "PASS" for v in observation["gates"].values()) and bool(observation["native_run_id"]),
        "critical_defects": facts.get("critical_defects", []),
        "invalid_structured": facts.get("invalid_structured"),
        "false_ready": facts.get("false_ready"),
        "required_evidence_complete": facts.get("required_evidence_complete"),
        "independent_audit": audit["audit_artifact"] if audit else None,
        "qualification_status": "AUDITED" if audit else "INCOMPLETE_INDEPENDENT_AUDIT",
    }
