"""Operator-stop queue truth must not depend on another running scheduler cycle.

Real SQLite order/execution/mission stores, deterministic native protocol fixture;
no inference, GPU, service-manager command or production state is used.
"""
# ruff: noqa: F811 - shared isolated fixture
import json
from types import SimpleNamespace

import pytest
from forge_factory.afo import operations
from forge_factory.afo.durable import digest
from forge_factory.lrtx import stack
from test_afo_m3_reconcile import admitted  # noqa: F401
from test_da014_product_outcomes import setup


def stopped(admitted, tmp_path, monkeypatch):
    store, oid, ledger, executions, job, _ = setup(admitted, monkeypatch, package=None)
    aid = job["attempt_id"]
    store.attempt_transition(aid, "DISPATCH_PENDING")
    store.attempt_transition(aid, "RUNNING", fabro_run_id="native")
    store.transition(oid, "RUNNING", "native fixture accepted")
    directory = tmp_path / "private-operations"
    directory.mkdir(mode=0o700)
    intent = operations.Intent(directory / "intent.json")
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(intent.path))
    monkeypatch.setattr(stack, "managed_serving", lambda: False)
    intent.set("STOPPED", actor="owner", reason="bounded fixture shutdown", initialize=True)
    return store, oid, ledger, executions, job, intent


def native(status):
    return SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": status}}},
                           cancel=lambda _: 202)


@pytest.mark.parametrize("status", ["RUNNING", "FAILED"])
def test_shutdown_projects_blocked_order_without_inventing_native_quiescence(admitted, tmp_path, monkeypatch, status):
    store, oid, ledger, executions, job, intent = stopped(admitted, tmp_path, monkeypatch)
    before = ledger.snapshot("product")
    attempt = store.attempts(oid)[-1]
    result = operations.settle_shutdown(store, client=native(status))
    assert store.order(oid)["state"] == "BLOCKED"
    assert store.order(oid)["terminal_reason"] == "OPERATOR_SHUTDOWN"
    assert result["settled"] == (status == "FAILED")
    assert executions.get(job["job_id"])["resource_lease"] == ("RELEASED" if status == "FAILED" else "HELD")
    assert executions.get(job["job_id"])["task_outcome"] == "BLOCKED"
    assert store.attempts(oid)[-1] == attempt  # no native status invented from operator intent
    assert ledger.snapshot("product") == before
    assert intent.read()["mode"] == "STOPPED"
    version = store.order(oid)["version"]
    operations.settle_shutdown(store, client=native(status))
    assert store.order(oid)["version"] == version
    with store.tx() as c:
        records = [json.loads(row[0]) for row in c.execute(
            "SELECT record FROM afo_lifecycle_events WHERE type='afo.operator_shutdown_projected'")]
    assert len(records) == 1
    assert records[0]["payload"]["job_id"] == job["job_id"]
    assert records[0]["payload"]["operations_epoch"] == intent.read()["epoch"]
    # Reconciliation may already have changed the mutable lifecycle row on the
    # second call. The original event must retain the exact source bytes' data.
    payload = records[0]["payload"]
    assert digest(payload["execution_record"]) == payload["execution_record_sha256"]
    assert payload["execution_record"]["task_outcome"] == "BLOCKED"
    assert payload["execution_record"]["terminal_reason"] == "OPERATOR_SHUTDOWN"


def test_crash_after_capacity_settlement_still_projects_the_stopped_order(admitted, tmp_path, monkeypatch):
    store, oid, ledger, executions, job, _ = stopped(admitted, tmp_path, monkeypatch)
    executions.outcome(job["job_id"], "BLOCKED", "OPERATOR_SHUTDOWN")
    executions.revoke(job["job_id"])
    assert executions.reconcile(job["job_id"], native("FAILED"))["resource_lease"] == "RELEASED"
    assert executions.pending() == []
    assert operations.settle_shutdown(store, client=native("FAILED"))["settled"]
    assert store.order(oid)["state"] == "BLOCKED"


def test_old_stopped_execution_cannot_block_a_newer_attempt(admitted, tmp_path, monkeypatch):
    store, oid, _, executions, job, _ = stopped(admitted, tmp_path, monkeypatch)
    executions.outcome(job["job_id"], "BLOCKED", "OPERATOR_SHUTDOWN")
    executions.reconcile(job["job_id"], native("FAILED"))
    prior = store.attempts(oid)[-1]
    newer = {**prior["record"], "attempt_id": oid + "-a2", "attempt_seq": 2}
    with store.tx() as c:
        c.execute("INSERT INTO afo_attempts VALUES (?,?,?,?,?,?,?)",
                  (newer["attempt_id"], oid, 2, prior["state"], json.dumps(newer), prior["created_utc"], None))
    operations.settle_shutdown(store, client=native("FAILED"))
    assert store.order(oid)["state"] == "RUNNING"


def test_newer_resume_intent_fences_stale_shutdown_projection(admitted, tmp_path, monkeypatch):
    store, oid, _, executions, job, intent = stopped(admitted, tmp_path, monkeypatch)
    executions.outcome(job["job_id"], "BLOCKED", "OPERATOR_SHUTDOWN")
    intent.set("RUNNING", actor="owner", reason="newer operator intent")
    with pytest.raises(ValueError, match="SHUTDOWN_INTENT_SUPERSEDED"):
        operations.settle_shutdown(store, client=native("FAILED"))
    assert store.order(oid)["state"] == "RUNNING"


@pytest.mark.parametrize("field", ["nonce", "mission_id"])
def test_mismatched_job_binding_is_reported_without_changing_the_order(admitted, tmp_path, monkeypatch, field):
    store, oid, _, executions, job, intent = stopped(admitted, tmp_path, monkeypatch)
    altered = {**job, field: "unrelated-binding"}
    with store.tx() as c:
        c.execute("UPDATE afo_product_jobs SET record=? WHERE job_id=?", (json.dumps(altered), job["job_id"]))
    result = operations.settle_shutdown(store, client=native("FAILED"))
    assert result["settled"] and intent.read()["effective_stop"]
    assert executions.get(job["job_id"])["task_outcome"] == "BLOCKED"
    assert result["order_projection"]["status"] == "PENDING"
    assert result["order_projection"]["binding_errors"] == [job["job_id"]]
    assert store.order(oid)["state"] == "RUNNING"


def test_projection_storage_failure_does_not_delay_physical_stop_or_claim_metadata_complete(admitted, tmp_path, monkeypatch):
    store, oid, _, _, _, intent = stopped(admitted, tmp_path, monkeypatch)

    def unavailable(*args, **kwargs):
        raise OSError("synthetic metadata store failure")

    monkeypatch.setattr(operations, "_project_shutdown_orders", unavailable, raising=False)
    result = operations.settle_shutdown(store, client=native("FAILED"))
    assert result["settled"] is True and intent.read()["effective_stop"] is True
    assert result["order_projection"] == {"status": "PENDING", "error_type": "OSError"}
    assert store.order(oid)["state"] == "RUNNING"
