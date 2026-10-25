"""Qualification bookkeeping in the existing AFO store and immutable artifact tree.

This module neither admits work nor grants authority. It records already-terminal
role jobs, including after grant expiry, and closes only explicitly marked
qualification wrappers after independent native quiescence. It never claims a
product result, qualified capability or successful campaign.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ..common import state_dir, utc_now
from .durable import Refused, digest, immutable_json, strict_json

RESULT_KIND = "PROTOCOL_QUALIFICATION_ROW"
TERMINAL = {"SUCCEEDED", "FAILED", "UNKNOWN", "TIMED_OUT", "REVOKED"}


def metadata(manifest, job_id):
    """Called after the existing preparer has verified the exact owner signature."""
    sha = digest(manifest)
    trials = [trial for trial, binding in manifest["jobs"].items() if binding["job_id"] == job_id]
    if len(trials) != 1:
        raise Refused("QUALIFICATION_JOB_BINDING_NOT_UNIQUE")
    relative = f"afo/qualification-manifests/{sha}.json"
    immutable_json(state_dir() / relative, manifest)
    return {"qualification_trial_id": trials[0], "qualification_manifest_ref": {"path": relative, "sha256": sha}}


def load(job):
    from .diagnosis_packet import scoped_path

    sha = job.get("qualification_manifest_sha256")
    ref = job.get("qualification_manifest_ref") or {}
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
        raise Refused("QUALIFICATION_ARCHIVED_MANIFEST_REQUIRED")
    if ref != {"path": f"afo/qualification-manifests/{sha}.json", "sha256": sha}:
        raise Refused("QUALIFICATION_ARCHIVED_MANIFEST_REFERENCE_CHANGED")
    path = scoped_path(state_dir(), ref["path"])
    manifest = strict_json(path.read_bytes(), 4 * 1024 * 1024)
    trial = job["qualification_trial_id"]
    binding = manifest.get("jobs", {}).get(trial) or {}
    if (
        digest(manifest) != sha
        or manifest.get("stage") != "protocol"
        or manifest.get("source_revision") != (job.get("factory_revision") or {}).get("commit")
        or any(binding.get(k) != job[k] for k in ("job_id", "case_sha256", "mission_id"))
    ):
        raise Refused("QUALIFICATION_ARCHIVED_MANIFEST_BINDING_CHANGED")
    return manifest


def can_close(c, order_id):
    """Guard the neutral terminal state; model prose and ordinary product jobs cannot use it."""
    att = c.execute("SELECT record FROM afo_attempts WHERE order_id=? ORDER BY seq DESC LIMIT 1", (order_id,)).fetchone()
    if not att:
        return False
    attempt = json.loads(att[0])
    if (
        attempt.get("fabro_run_id")
        or c.execute("SELECT 1 FROM afo_commands_outbox WHERE order_id=? AND kind='FABRO_LAUNCH'", (order_id,)).fetchone()
    ):
        return False
    rows = c.execute("SELECT record FROM afo_local_agent_jobs WHERE order_id=?", (order_id,)).fetchall()
    for item in rows:
        worker = json.loads(item[0])
        held = c.execute("SELECT record FROM afo_execution_liveness WHERE job_id=?", (worker["job_id"],)).fetchone()
        if worker.get("state") not in TERMINAL or (held and json.loads(held[0])["resource_lease"] == "HELD"):
            return False
    for row in rows:
        job = json.loads(row[0])
        sha = job.get("qualification_manifest_sha256")
        if job.get("state") not in TERMINAL or not sha or "qualification-014:" + sha not in attempt.get("evidence_refs", []):
            continue
        saved = c.execute(
            "SELECT record,sha256 FROM afo_execution_evidence WHERE job_id=? AND kind=?", (job["job_id"], RESULT_KIND)
        ).fetchone()
        live = c.execute("SELECT record FROM afo_execution_liveness WHERE job_id=?", (job["job_id"],)).fetchone()
        if not saved or not live:
            continue
        result, execution = json.loads(saved["record"]), json.loads(live[0])
        if (
            digest(result) == saved["sha256"]
            and result.get("job_id") == job["job_id"]
            and result.get("manifest_sha256") == sha
            and result.get("case_sha256") == job["case_sha256"]
            and result.get("trial_id") == job.get("qualification_trial_id")
            and execution["resource_lease"] == "RELEASED"
            and execution["execution_liveness"] in ("NOT_STARTED", "QUIESCENT")
            and execution["launch_nonce"] == job["nonce"]
        ):
            return True
    return False


def record_completed(store, job, *, destination=None):
    """Publish once and recover wrapper closure after any crash; no new model/native effect."""
    if not job.get("qualification_manifest_ref") or job.get("state") not in TERMINAL:
        return None
    from . import qualification as Q
    from .execution_lifecycle import Executions
    from .protocol_faults import _record

    manifest = load(job)
    from .diagnosis_packet import scoped_path

    name = job["qualification_trial_id"].replace(":", "-") + ".json"
    relative = "lrtx/qualification-results/" + job["qualification_manifest_sha256"] + "/" + name
    path = scoped_path(state_dir(), relative)
    with store.tx() as c:
        old = c.execute(
            "SELECT record,sha256 FROM afo_execution_evidence WHERE job_id=? AND kind=?", (job["job_id"], RESULT_KIND)
        ).fetchone()
    if old:
        row = json.loads(old["record"])
        if digest(row) != old["sha256"]:
            raise Refused("QUALIFICATION_RESULT_STORAGE_CORRUPT")
    elif path.is_file():
        row = strict_json(path.read_bytes(), 1024 * 1024)
    else:
        row = Q.protocol_observation(store, manifest, job["qualification_trial_id"], job)
    if (
        row["job_id"] != job["job_id"]
        or row["manifest_sha256"] != job["qualification_manifest_sha256"]
        or row.get("case_sha256") != job["case_sha256"]
        or row.get("trial_id") != job["qualification_trial_id"]
    ):
        raise Refused("QUALIFICATION_RESULT_BINDING_CHANGED")
    # Publish before exposing the row in SQL; identical replay recovers a crash
    # on either side. Later usage and quiescence stay in their authoritative ledgers.
    immutable_json(path, row)
    _record(store, job["job_id"], RESULT_KIND, row)
    if destination is not None:
        immutable_json(Path(destination) / name, row)
    with store.tx() as c:
        closable = can_close(c, job["order_id"])
    if closable:
        att = store.attempts(job["order_id"])[-1]
        if att["state"] == "PREPARED":
            store.attempt_transition(
                att["attempt_id"],
                "CANCELLED",
                finished_utc=utc_now(),
                exit_status="qualification_wrapper_closed_without_product_launch",
            )
        live = Executions(store).get(job["job_id"])
        if live["task_outcome"] == "ACTIVE":
            Executions(store).outcome(job["job_id"], "BLOCKED", "QUALIFICATION_ONLY_NO_PRODUCT_DISPATCH")
        if store.order(job["order_id"])["state"] in ("RUNNING", "WAITING_RECOVERY"):
            store.transition(
                job["order_id"],
                "QUALIFICATION_RECORDED",
                "role qualification recorded; no product verdict",
                terminal_reason="QUALIFICATION_ONLY_NO_PRODUCT_ACCEPTANCE",
            )
    return {"row": row, "path": str(path), "sha256": digest(row), "product_acceptance": "NOT_REQUESTED"}
