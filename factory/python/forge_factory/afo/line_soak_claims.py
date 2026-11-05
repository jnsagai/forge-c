"""Pure replay of optional prior M6/M7/M8 claims; no curator, broker or verifier dispatch.

These observations do not substitute for stage outcomes or authorize future work.
Only existing authoritative stores and independently sealed receipts are consumed.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

from .durable import Refused, digest

HISTORY_BOUNDS = {"max_entries": 4096, "max_bytes": 32 * 1024 * 1024, "max_file_bytes": 1024 * 1024, "timeout_seconds": 3}


def lesson(claim):
    from ..common import state_dir, utc_now
    from ..knowledge.qualification import issues
    from ..knowledge.store import LessonStore
    from .line_soak_prerequisites import reference
    from .queue import ReadSnapshot

    record = reference(claim["record_ref"])
    path = state_dir() / "knowledge/lessons.sqlite3"
    with ReadSnapshot(path, max_rows=1000, timeout_s=3) as reader:
        with reader.tx() as c:
            row = c.execute("SELECT record,state,expires_at FROM lessons WHERE lesson_id=?", (record["lesson_id"],)).fetchone()
        if (not row or json.loads(row["record"]) != record or row["state"] != "VALIDATED"
                or not row["expires_at"] or row["expires_at"] <= utc_now()):
            raise Refused("LINE_SOAK_LESSON_NOT_CURRENT_VALIDATED")
        # Adapt the existing validator's read API, never construct/migrate a writer.
        view = SimpleNamespace(_conn=reader.tx, content_hash=LessonStore.content_hash)
        if issues(view, record, history_bounds=HISTORY_BOUNDS):
            raise Refused("LINE_SOAK_LESSON_QUALIFICATION_INVALID")
    return {"kind": "lesson", "record_sha256": digest(record), "benefit_inferred": False,
            "application_inferred": False, "scope": "VALIDATED_MEMORY_RECORD_ONLY",
            "applicability": record.get("applicability"), "role_qualification_inferred": False}


def maintenance(claim, manifest, store):
    from ..common import state_dir
    from ..reliability import promotion
    from ..reliability.policy import load
    from . import maintainer as M
    from .completion_receipt import Context
    from .execution_lifecycle import Executions
    from .line_soak_prerequisites import reference
    from .queue import ReadSnapshot

    with store.tx() as c:
        row = c.execute("SELECT record FROM afo_local_agent_jobs WHERE job_id=?", (claim["job_id"],)).fetchone()
    if not row:
        raise Refused("LINE_SOAK_MAINTENANCE_JOB_UNBOUND")
    job = json.loads(row[0])
    case = reference({"path": job["case"], "sha256": job["case_sha256"]})
    Context.from_job(store, job["job_id"])
    executions = Executions(store)
    execution = executions.get(job["job_id"])
    if (job.get("state") != "SUCCEEDED" or not execution or execution["execution_liveness"] != "QUIESCENT"
            or execution["resource_lease"] != "RELEASED" or execution["launch_nonce"] != job["nonce"]
            or execution["mission_id"] != job["mission_id"] or not executions._evidence(job["job_id"], "QUIESCENCE")
            or not execution.get("native_run_ids") or job.get("run_id") not in execution["native_run_ids"]):
        raise Refused("LINE_SOAK_MAINTENANCE_NATIVE_COMPLETION_UNPROVEN")
    if (job.get("role") != "afo-factory-maintainer" or case.get("proposal_id") != claim["proposal_id"]
            or case.get("base") != manifest["source_revision"]
            or job.get("factory_revision", {}).get("commit") != case.get("base")
            or job.get("factory_revision", {}).get("dirty") is not False
            or not job.get("line_origin")
            or any((case.get("line_binding") or {}).get(k) != job.get(k) for k in ("mission_id", "order_id", "attempt_id"))
            or (case.get("line_binding") or {}).get("source_revision") != case.get("base")):
        raise Refused("LINE_SOAK_MAINTENANCE_CONTEXT_CHANGED")
    submission, _ = M.submission(case, require_receipt=True)
    prior = store.proposal(claim["proposal_id"])
    if not prior:
        raise Refused("LINE_SOAK_MAINTENANCE_REVIEW_ABSENT")
    saved = prior["record"]
    decision = reference(claim["decision_ref"])
    with ReadSnapshot(state_dir() / "supervisor/incidents.sqlite3", max_rows=1000, timeout_s=3) as registry:
        with registry.tx() as c:
            actual = c.execute("SELECT candidate,baseline,decision,record FROM cre_promotion_decisions WHERE decision_id=?",
                               (saved["cre_promotion_id"],)).fetchone()
            triggers = dict(c.execute("SELECT name,sql FROM sqlite_master WHERE type='trigger' "
                                      "AND tbl_name='cre_promotion_decisions'"))
    if not actual or json.loads(actual[3]) != decision or not all(
            "RAISE(ABORT" in triggers.get("cre_promotion_decisions_no_" + op, "").upper() for op in ("update", "delete")):
        raise Refused("LINE_SOAK_MAINTENANCE_DECISION_UNTRUSTED")
    gates = {g["name"]: g for g in decision.get("hard_gates", [])}
    expected = {"protected_files", "policy_integrity", "reproducer", "prevention", "quality_process",
                "golden_benchmark", "holdout"}
    if (promotion.schema_errors(decision) or set(gates) != expected or len(decision["hard_gates"]) != len(expected)
            or any(g["result"] != "PASS" and not (name == "reproducer" and g["result"] == "NOT_RUN"
                    and g.get("reason_code") == "NOT_APPLICABLE_FOR_CHANGE") for name, g in gates.items())
            or decision["decision"] != "ELIGIBLE_FOR_OFFLINE_REVIEW"
            or decision.get("evaluator_kind") != "INDEPENDENT_DETERMINISTIC_RUNNER"
            or decision["policy_sha256"] != load().sha256 or decision["allowed_auto_deployment"] is not False
            or saved.get("auto_deployment_allowed") is not False
            or saved["tests_ref"] != "local-agent:" + job["job_id"]
            or saved["baseline_commit"] != case["base"] or saved["candidate_commit"] != submission["candidate"]
            or actual[0] != submission["candidate"] or actual[1] != case["base"] or actual[2] != decision["decision"]
            or decision["candidate_sha256"] != _tree(submission["candidate"], Path(case["repo"]))
            or decision["baseline_sha256"] != _tree(case["base"], Path(case["repo"]))):
        raise Refused("LINE_SOAK_MAINTENANCE_INDEPENDENT_REVIEW_INVALID")
    return {"kind": "maintenance", "decision_sha256": digest(decision), "source_deployed": False,
            "role_qualification_inferred": False, "repair_benefit_inferred": False,
            "scope": "OFFLINE_CANDIDATE_ELIGIBILITY_ONLY"}


def _tree(revision, repo):
    """Same git-ls-tree byte identity as promotion.tree_sha256, with a 3s observation bound."""
    from ..common import sha256_bytes

    result = subprocess.run(["git", "ls-tree", "-r", revision], cwd=repo, capture_output=True, check=True, timeout=3)
    return sha256_bytes(result.stdout)
