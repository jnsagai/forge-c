"""Real queue/ledger/artifact recovery with typed native fixtures; no Qwen or deployment."""
# ruff: noqa: F811

import copy
import json
import shlex
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import authz, policy
from forge_factory.afo import local_agent as L
from forge_factory.afo import protocol_faults as F
from forge_factory.afo import qualification_state as R
from forge_factory.afo.durable import Refused, digest
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import QueueError, Store
from test_afo_local_autonomy import local  # noqa: F401
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_qualification_reservations import signed  # noqa: F401


@pytest.fixture
def wrapper(signed, tmp_path, request):
    p = signed
    # A second private fixture database exercises actual purpose-aware admission
    # instead of deleting the original product fixture's launch history.
    store = Store(tmp_path / "qualification-wrapper.sqlite3")
    env = json.loads(p.order["envelope"])
    oid, _ = store.submit(env, repo=tmp_path / "repo", max_queued=100)
    manifest = copy.deepcopy(p.manifest)
    binding = next(iter(manifest["jobs"].values()))
    manifest["jobs"] = {"obligation-counterexample:0": binding}
    p.grant["signed_runbook_ref"] = "qualification-014:" + digest(manifest)
    p.grant_path.write_text(json.dumps(p.grant))
    authz.sign(p.grant_path, p.key)
    ledger = MissionLedger(store)
    prior = p.ledger.snapshot("qualification-only")
    ledger.register("qualification-only", prior["lineage"], prior["limits"], "AUTH-QUAL", authorize=lambda *a: True)
    ledger.link("qualification-only", oid)
    epoch = store.acquire_lease("scheduler", "fixture-controller", 120)
    aid = store.admit(
        oid,
        epoch=epoch,
        scope="scheduler",
        policy_sha256=p.eff.sha256,
        authorization_id="AUTH-QUAL",
        max_concurrent=1,
        qualification_ref="qualification-014:" + digest(manifest),
    )
    assert aid == p.bundle["attempt_id"] and not store.commands("PENDING")
    store.transition(oid, "RUNNING", "qualification preparation; no product run claimed")
    job = L.prepare(store, store.order(oid), aid, "afo-recovery-planner", p.case, p.ws, p.eff, qualification_manifest=manifest)
    execution = Executions(store)
    execution.reserve(job["job_id"], job["mission_id"], job["nonce"])
    execution.dispatch_intent(job["job_id"])
    execution.adopt(job["job_id"], ["native-typed-fixture"])
    if getattr(request, "param", None) == "metered":
        job.update(state="RUNNING", run_id="native-typed-fixture")
        L.save(store, job)
        ledger.reserve_request(
            job["mission_id"],
            job["job_id"],
            "typed-gateway-request",
            body_sha256="a" * 64,
            input_tokens=10,
            output_cap=30,
            authorize=lambda: True,
        )
        ledger.start_request("typed-gateway-request", authorize=lambda: True)
        ledger.reconcile_request(
            "typed-gateway-request", input_tokens=10, output_tokens=7, quiescent=True, evidence_ref="typed-provider-completion"
        )
    # This declared positive case failed in the fixture. Recording it must not
    # fabricate qualification success, a product failure, or a READY package.
    job.update(state="FAILED", error="EMPTY_MODEL_OUTPUT", run_id="native-typed-fixture", reported_tokens=0)
    L.save(store, job)
    execution.outcome(job["job_id"], "FAILED_PROTOCOL", "EMPTY_MODEL_OUTPUT")
    return SimpleNamespace(store=store, ledger=ledger, job=job, ex=execution, manifest=manifest, epoch=epoch, p=p)


def quiesce(p):
    client = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "FAILED"}}})
    p.ex.reconcile(p.job["job_id"], client)
    assert p.ex.get(p.job["job_id"])["resource_lease"] == "RELEASED"


def test_result_snapshot_can_record_live_failure_but_cannot_release_wrapper_capacity(wrapper):
    p = wrapper
    result = R.record_completed(p.store, p.job)
    assert result["row"]["observed"] == "BLOCKED_LIVE_HELD"
    assert p.store.order(p.job["order_id"])["state"] == "RUNNING"
    with pytest.raises(QueueError, match="QUALIFICATION_RESULT_AND_QUIESCENCE_REQUIRED"):
        p.store.transition(p.job["order_id"], "QUALIFICATION_RECORDED", "an acknowledgement is insufficient")
    before = p.ledger.snapshot("qualification-only")
    quiesce(p)
    # Preserve the first live-failure snapshot; authoritative liveness converges
    # separately. An outcome alone never provided permission to release it.
    assert R.record_completed(p.store, p.job)["sha256"] == result["sha256"]
    assert p.store.order(p.job["order_id"])["state"] == "QUALIFICATION_RECORDED"
    assert p.store.attempts(p.job["order_id"])[0]["state"] == "CANCELLED"
    assert p.store.attempts(p.job["order_id"])[0]["record"]["fabro_run_id"] is None
    assert p.ledger.snapshot("qualification-only") == before
    assert p.ledger.snapshot("qualification-only")["attempts"] == 0
    assert not p.store.commands("PENDING")


def test_neutral_completion_requires_recorded_result_even_after_quiescence(wrapper):
    p = wrapper
    quiesce(p)
    with pytest.raises(QueueError, match="QUALIFICATION_RESULT_AND_QUIESCENCE_REQUIRED"):
        p.store.transition(p.job["order_id"], "QUALIFICATION_RECORDED", "native exit is not a durable row")
    result = R.record_completed(p.store, p.job)
    assert result["row"]["observed"] == "FAILED_PROTOCOL"
    assert result["product_acceptance"] == "NOT_REQUESTED"
    assert p.store.order(p.job["order_id"])["state"] == "QUALIFICATION_RECORDED"


def test_ordinary_product_order_cannot_use_qualification_terminal_state(signed):
    with pytest.raises(QueueError, match="QUALIFICATION_RESULT_AND_QUIESCENCE_REQUIRED"):
        signed.store.transition(signed.order["order_id"], "QUALIFICATION_RECORDED", "product gate bypass refused")


def test_supervision_collects_after_authority_expiry_without_model_or_new_budget(wrapper, monkeypatch):
    p = wrapper
    quiesce(p)
    before = p.ledger.snapshot("qualification-only")
    (p.p.grant_path.parent / "revoked.txt").write_text("AUTH-QUAL\n")
    monkeypatch.setattr(L, "poll", lambda *a, **kw: pytest.fail("completed job must not be redispatched or polled"))
    disabled = policy.Effective("DISABLED", "DISABLED", None, None)
    L.supervise(p.store, disabled)
    assert p.store.order(p.job["order_id"])["state"] == "QUALIFICATION_RECORDED"
    assert p.ledger.snapshot("qualification-only") == before
    L.supervise(p.store, disabled)
    with p.store.tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_execution_evidence WHERE kind=?", (R.RESULT_KIND,)).fetchone()[0] == 1


def test_crash_after_artifact_before_sql_adopts_original_snapshot(wrapper, monkeypatch):
    p = wrapper
    quiesce(p)
    with monkeypatch.context() as crash:
        crash.setattr(F, "_record", lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("crash before SQL publication")))
        with pytest.raises(RuntimeError, match="crash before SQL"):
            R.record_completed(p.store, p.job)
    with p.store.tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_execution_evidence WHERE kind=?", (R.RESULT_KIND,)).fetchone()[0] == 0
    p.job["reported_tokens"] = 900  # late command-only usage cannot rewrite the first observation
    L.save(p.store, p.job)
    result = R.record_completed(p.store, p.job)
    assert result["row"]["native_fabro_reported_tokens"] == 0
    assert p.store.order(p.job["order_id"])["state"] == "QUALIFICATION_RECORDED"


def test_captured_native_context_survives_a_scrubbed_command_process_without_credentials(signed, tmp_path, monkeypatch):
    import yaml
    from forge_factory.afo.operations import Intent
    from forge_factory.common import canonical_json, data_root, sha256_bytes
    from forge_factory.workflow.builder import _env

    p = signed
    context = {
        "FORGE_DATA_ROOT": str(data_root()),
        "FORGE_AFO_POLICY": str(tmp_path / "policy's file.yaml"),
        "FORGE_AFO_AUTH_DIR": str(tmp_path / "private authorizations"),
        "FORGE_AFO_ALLOWED_SIGNERS": str(tmp_path / "public allowed-signers"),
        "FORGE_OPERATIONS_INTENT": str(tmp_path / "intent.json"),
        "FORGE_EVENTS_DIR": str(tmp_path / "events"),
    }
    for key, value in context.items():
        monkeypatch.setenv(key, value)
    Intent(context["FORGE_OPERATIONS_INTENT"]).set(
        "RUNNING", actor="fixture-owner", reason="explicit unit-fixture intent", initialize=True
    )
    pol = copy.deepcopy(p.eff.policy)
    pol["mode"] = "PILOT"
    Path(context["FORGE_AFO_POLICY"]).write_text(yaml.safe_dump(pol))
    policy_sha = sha256_bytes(canonical_json(pol))
    auth_dir = Path(context["FORGE_AFO_AUTH_DIR"])
    auth_dir.mkdir(mode=0o700)
    Path(context["FORGE_AFO_ALLOWED_SIGNERS"]).write_text((p.grant_path.parent / "allowed-signers").read_text())
    record = {**p.grant, "policy_sha256": policy_sha}
    grant_path = auth_dir / "AUTH-QUAL.json"
    grant_path.write_text(json.dumps(record))
    authz.sign(grant_path, p.key)
    effective = policy.Effective("PILOT", "PILOT", policy_sha, pol)
    job = L.prepare(p.store, p.order, p.bundle["attempt_id"], "afo-recovery-planner", p.case, p.ws, effective)
    assert job["native_context"] == context
    contaminated = {**job, "native_context": {**job["native_context"], "API_KEY": "must-not-cross", "GH_TOKEN": "must-not-cross"}}
    program = (
        "import json,os; from forge_factory.afo.policy import load; p=load(); "
        "print(json.dumps({'env':dict(os.environ),'policy_mode':p.mode,'policy_sha256':p.sha256}))"
    )
    command = (
        _env() + " " + L.command_environment(contaminated) + " " + shlex.quote(sys.executable) + " -c " + shlex.quote(program)
    )
    child = subprocess.run(
        ["/bin/sh", "-c", command], env={}, cwd=tmp_path, capture_output=True, text=True, check=True, timeout=10
    )
    result = json.loads(child.stdout)
    observed = result["env"]
    assert result["policy_mode"] == "PILOT" and result["policy_sha256"] == policy_sha
    assert all(observed[key] == value for key, value in context.items())
    assert observed["FORGE_LRTX_PROFILE"] == job["profile"] and observed["FORGE_DURABLE_AUTONOMY"] == "1"
    assert "API_KEY" not in observed and "GH_TOKEN" not in observed
    import tomllib

    from forge_factory.fabro.runconfig import render_run_toml

    forwarded = L.execution_context(contaminated)
    config = tomllib.loads(
        render_run_toml(
            "graph.dot",
            "context serialization fixture",
            tmp_path / "binding.json",
            {"forge-afo-mcp": {"module": "forge_factory.mcp.servers.afo", "env": forwarded}},
            hook_env=forwarded,
        )
    )
    mcp = config["run"]["agent"]["mcps"]["forge_afo_mcp"]["env"]
    assert all(mcp[key] == value for key, value in context.items())
    assert "API_KEY" not in mcp and "GH_TOKEN" not in mcp
    assert all(
        "FORGE_AFO_POLICY=" + shlex.quote(context["FORGE_AFO_POLICY"]) in hook["script"] for hook in config["run"]["hooks"]
    )


def test_invalid_native_context_is_not_interpolated_into_commands():
    with pytest.raises(ValueError, match="LOCAL_AGENT_NATIVE_CONTEXT_INVALID"):
        L.command_environment({"profile": "local-fixture", "native_context": {"FORGE_AFO_POLICY": "bad\x00path"}})


@pytest.mark.parametrize("wrapper", ["metered"], indirect=True)
def test_provider_usage_is_not_replaced_by_zero_token_native_command_usage(wrapper):
    p = wrapper
    quiesce(p)
    result = R.record_completed(p.store, p.job)
    row = result["row"]
    assert row["reported_tokens"] == 17 and row["native_fabro_reported_tokens"] == 0
    assert row["request_count"] == 1 and row["usage_source"] == "GATEWAY_REQUEST_LEDGER"
    assert row["usage_unknown"] is False
    assert p.ledger.snapshot("qualification-only")["charged_tokens"] == 32768


def test_missing_case_records_uncertainty_without_claiming_product_failure_or_stranding_quiet_wrapper(wrapper):
    p = wrapper
    quiesce(p)
    p.p.case.unlink()
    result = R.record_completed(p.store, p.job)
    assert result["row"]["observed"] == "UNKNOWN" and result["row"]["case_binding_valid"] is False
    assert result["row"]["observation_blockers"] == ["FROZEN_CASE_CHANGED"]
    assert p.store.order(p.job["order_id"])["state"] == "QUALIFICATION_RECORDED"


def test_changed_archive_cannot_create_a_completion_record(wrapper):
    p = wrapper
    quiesce(p)
    path = R.state_dir() / p.job["qualification_manifest_ref"]["path"]
    path.chmod(0o600)
    path.write_text("{}")
    with pytest.raises(Refused, match="QUALIFICATION_ARCHIVED_MANIFEST_BINDING_CHANGED"):
        R.record_completed(p.store, p.job)
    assert p.store.order(p.job["order_id"])["state"] == "RUNNING"
