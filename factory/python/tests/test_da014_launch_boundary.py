"""Local launch proof versus actual native uncertainty; no live model execution."""

# ruff: noqa: F811
import subprocess
from types import SimpleNamespace

import pytest
from forge_factory.afo import local_agent as L
from forge_factory.afo.durable import Refused
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.operations import Intent
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_integration import ready
from test_da014_protocol import protocol  # noqa: F401


def forbidden_client():
    def fail(*a, **kw):
        pytest.fail("known local refusal must not need a native observation")

    return SimpleNamespace(list_runs=fail, get_run=fail, usage=fail)


def test_real_dirty_source_refusal_records_non_dispatch_and_releases_capacity(protocol, monkeypatch):
    from forge_factory import workorder

    p = protocol
    job = ready(p, monkeypatch)
    monkeypatch.setattr(workorder, "factory_revision", lambda: {"dirty": True})
    result = L.poll(p.store, p.order, job, p.eff, client=forbidden_client())
    live = Executions(p.store).get(job["job_id"])
    assert result["state"] == "FAILED" and result["error"].startswith("NATIVE_LAUNCH_NOT_STARTED:")
    assert live["admission_state"] == "DISPATCH_INTENT_RECORDED"  # no intent/history reset
    assert live["execution_liveness"] == "NOT_STARTED" and live["resource_lease"] == "RELEASED"
    assert live["task_outcome"] == "BLOCKED" and not live["native_run_ids"]
    assert p.ledger.snapshot("mission-test")["charged_tokens"] == 16000
    L.poll(p.store, p.order, result, p.eff, client=forbidden_client())
    assert Executions(p.store).get(job["job_id"])["resource_lease"] == "RELEASED"


def test_operator_epoch_refusal_before_effect_is_proven_without_starting(protocol, monkeypatch, tmp_path):
    from forge_factory.afo.operations import fenced_call

    p = protocol
    job = ready(p, monkeypatch)
    path = tmp_path / "operations" / "intent.json"
    path.parent.mkdir(mode=0o700)
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(path))
    intent = Intent(path)
    old = intent.set("RUNNING", actor="owner", reason="fixture", initialize=True)
    intent.set("STOPPED", actor="owner", reason="stop wins")
    job["operations_epoch"] = old["epoch"]
    monkeypatch.setattr(L, "_launch", lambda j, invoke: fenced_call(j["operations_epoch"], lambda: invoke(["unused"])))
    result = L.poll(p.store, p.order, job, p.eff, client=forbidden_client())
    assert result["state"] == "FAILED"
    assert Executions(p.store).get(job["job_id"])["resource_lease"] == "RELEASED"
    assert intent.read()["mode"] == "STOPPED"


@pytest.mark.parametrize("failure", [TimeoutError, FileNotFoundError, subprocess.SubprocessError])
def test_invoked_subprocess_error_retains_native_uncertainty(protocol, monkeypatch, failure):
    p = protocol
    job = ready(p, monkeypatch)

    def failed(*a, **kw):
        raise failure("not termination evidence")

    monkeypatch.setattr(L.subprocess, "run", failed)
    monkeypatch.setattr(L, "_launch", lambda j, invoke: invoke(["fabro", "run"]))
    result = L.poll(p.store, p.order, job, p.eff, client=forbidden_client())
    live = Executions(p.store).get(job["job_id"])
    assert result["state"] == "LAUNCHING" and result["error"].startswith("NATIVE_LAUNCH_UNCERTAIN:")
    assert live["resource_lease"] == "HELD" and live["execution_liveness"] == "POSSIBLY_LIVE"
    assert Executions(p.store)._evidence(job["job_id"], "LAUNCH_NOT_STARTED") is None


def test_restart_recovers_durable_non_dispatch_proof_after_publication_crash(protocol, monkeypatch):
    p = protocol
    job = ready(p, monkeypatch)
    ex = Executions(p.store)
    ex.reserve(job["job_id"], "mission-test", job["nonce"])
    ex.dispatch_intent(job["job_id"])
    original = ex._quiescent
    monkeypatch.setattr(ex, "_quiescent", lambda *a: (_ for _ in ()).throw(RuntimeError("crash")))
    with pytest.raises(RuntimeError, match="crash"):
        ex.not_dispatched(job["job_id"], failure_type="Refused")
    assert ex.get(job["job_id"])["resource_lease"] == "HELD"
    monkeypatch.setattr(ex, "_quiescent", original)
    recovered = Executions(p.store).reconcile(job["job_id"], forbidden_client())
    assert recovered["resource_lease"] == "RELEASED" and recovered["execution_liveness"] == "NOT_STARTED"
    with pytest.raises(Refused):
        ex.adopt(job["job_id"], ["cannot-resurrect"])


def test_non_dispatch_cannot_override_adopted_native_execution(protocol, monkeypatch):
    p = protocol
    job = ready(p, monkeypatch)
    ex = Executions(p.store)
    ex.reserve(job["job_id"], "mission-test", job["nonce"])
    ex.dispatch_intent(job["job_id"])
    ex.adopt(job["job_id"], ["real-native"])
    with pytest.raises(Refused, match="LAUNCH_NOT_STARTED_CONTRADICTED"):
        ex.not_dispatched(job["job_id"], failure_type="Refused")
    assert ex.get(job["job_id"])["resource_lease"] == "HELD"
