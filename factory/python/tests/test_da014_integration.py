"""Actual broker/gateway/controller integration with typed fixtures, never live Qwen."""
# ruff: noqa: F811  # imported pytest fixtures are also named function parameters

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from forge_factory.afo import local_agent as L
from forge_factory.afo.completion_receipt import Context, Receipts
from forge_factory.afo.durable import Refused, immutable_json
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.operations import Intent
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_protocol import protocol  # noqa: F401


def ready(p, monkeypatch):
    job = {
        **p.job,
        "model": "qwen-fixture",
        "profile": "local-fixture",
        "durable_protocol": "1.0",
        "policy_sha256": p.eff.sha256,
        "deadline_epoch": time.time() + 300,
        "state": "PREPARED",
        "created_epoch": time.time(),
        "run_id": None,
    }
    L.save(p.store, job)
    monkeypatch.setattr(L, "authorized", lambda *a: True)
    monkeypatch.setattr(L, "enabled", lambda *a: True)
    return job


def test_native_success_without_proposal_fails_protocol_and_releases_only_after_terminal(protocol, monkeypatch):
    p = protocol
    job = ready(p, monkeypatch)
    client = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "SUCCEEDED"}}}, usage=lambda _: {})
    job = L.poll(p.store, p.order, job, p.eff, client=client, launch_fn=lambda _: "native-A")
    assert job["state"] == "RUNNING"
    job = L.poll(p.store, p.order, job, p.eff, client=client)
    assert job["state"] == "FAILED" and job["error"] == "NO_ACCEPTED_SEMANTIC_PROPOSAL"
    assert job["execution"]["resource_lease"] == "RELEASED"


def test_receipt_survives_absent_model_final_and_restart(protocol, monkeypatch):
    p = protocol
    job = ready(p, monkeypatch)
    client = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "SUCCEEDED"}}}, usage=lambda _: {})
    L.poll(p.store, p.order, job, p.eff, client=client, launch_fn=lambda _: "native-A")
    rec = Receipts(p.store).submit(p.ctx, p.proposal)
    # Recreate controller job from SQL; no compact model output exists.
    job = L.records(p.store, p.order["order_id"])[0]
    job = L.poll(p.store, p.order, job, p.eff, client=client)
    assert job["state"] == "SUCCEEDED" and job["completion"]["status"] == "PASS"
    assert job["receipt_id"] == rec["receipt_id"]


def test_terminal_revoked_job_still_reconciles_late_native_identity(protocol, monkeypatch):
    p = protocol
    job = ready(p, monkeypatch)
    client = SimpleNamespace(
        list_runs=lambda **kw: [{"id": "late-native", "labels": {"afo_agent": job["job_id"], "afo_nonce": job["nonce"]}}],
        get_run=lambda _: {"lifecycle": {"status": {"kind": "RUNNING"}}},
        cancel=lambda _: 202,
        usage=lambda _: {},
    )

    def lost(_):
        raise TimeoutError

    job = L.poll(p.store, p.order, job, p.eff, client=client, launch_fn=lost)
    monkeypatch.setattr(L, "authorized", lambda *a: False)
    job = L.poll(p.store, p.order, job, p.eff, client=client)
    assert job["state"] == "REVOKED" and job["run_id"] == "late-native"
    assert Executions(p.store).get(job["job_id"])["resource_lease"] == "HELD"
    job = L.poll(p.store, p.order, job, p.eff, client=client)
    assert Executions(p.store).get(job["job_id"])["cancel_attempts"] >= 2


def test_registered_mcp_wire_exposes_semantic_not_admin_contract():
    from forge_factory.mcp.servers.afo import PlanIn, ReqIn

    s = PlanIn.model_json_schema()
    assert "SemanticProposal" in s["$defs"]
    assert "mission_id" not in s["$defs"]["SemanticProposal"]["properties"]
    assert ReqIn(artifact_ref="artifact:example").requirement_id is None


def test_actual_ticket_scopes_full_late_primary_evidence(protocol, monkeypatch):
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import afo
    from forge_factory.common import state_dir

    p = protocol
    case = state_dir() / "afo/cases/fixture/case.json"
    immutable_json(case, {"bundle": p.bundle, "workspace": str(p.ws), "packet_ref": p.ref})
    monkeypatch.setenv("FORGE_AFO_CASE", str(case))
    ctx = sdk.ToolContext("forge-afo-mcp", "read_requirement_excerpt", "afo-recovery-planner", None, p.ws, p.ctx.job_id)
    tool = "mcp__forge_afo_mcp__read_requirement_excerpt"
    args = {"artifact_ref": p.packet["artifacts"][0]["ref"]}
    sdk.issue_ticket(ctx.run_id, tool, args, ctx.role, "agent", None, str(p.ws))
    t = sdk.consume_ticket(ctx.run_id, tool, args)
    assert t["role"] == ctx.role
    text, offset = "", 0
    while True:
        r = afo.read_requirement_excerpt(ctx, afo.ReqIn(**args, offset=offset))
        text += r["metrics"]["data"]
        offset = r["metrics"]["next_offset"]
        if offset is None:
            break
    assert text.endswith("DECISIVE_LATE_FINDING")
    ctx.role = "swe1-author"
    with pytest.raises(sdk.ToolDenied):
        afo.read_requirement_excerpt(ctx, afo.ReqIn(**args))


def test_gateway_reservation_replay_and_unknown_liveness(protocol, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    import httpx
    from forge_factory import llm_gateway as G
    from forge_factory.afo import request_admission as A

    p = protocol
    job = ready(p, monkeypatch)
    Executions(p.store).reserve(job["job_id"], "mission-test", job["nonce"])
    Executions(p.store).dispatch_intent(job["job_id"])
    from forge_factory.lrtx import role_capability

    monkeypatch.setattr(role_capability, "admit_job", lambda *a, **kw: {"qualified_fixture": True})
    original = A.reserve
    monkeypatch.setattr(A, "start", lambda store, rec, body: p.ledger.start_request(rec["request_id"], authorize=lambda: True))
    monkeypatch.setattr(A, "reserve", lambda store, binding, body: original(p.store, binding, body, eff=p.eff))
    monkeypatch.setattr(
        A,
        "reconcile",
        lambda store, rid, usage, completed=False: p.ledger.reconcile_request(
            rid, input_tokens=10, output_tokens=5, quiescent=completed, evidence_ref="provider-complete" if completed else None
        ),
    )
    sent = []

    def provider(request):
        sent.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    app = G.create_app("http://127.0.0.1:11455", tmp_path / "usage.jsonl", transport=httpx.MockTransport(provider))
    body = {
        "model": "qwen-fixture",
        "messages": [{"role": "user", "content": "x"}],
        "max_tokens": 32,
        "forge_execution": {"job_id": job["job_id"], "nonce": job["nonce"], "request_id": "req-integration"},
    }
    with TestClient(app) as client:
        assert client.post("/v1/chat/completions", json=body).status_code == 200
        assert client.post("/v1/chat/completions", json=body).status_code == 429
        assert client.post("/v1/chat/completions", json={"model": "qwen-fixture"}).status_code == 429
    assert len(sent) == 1 and "forge_execution" not in sent[0]
    assert p.ledger.snapshot("mission-test")["requests"] == 1


def test_operator_start_is_fenced_and_cooldown_survives_restart(tmp_path):
    tmp_path.chmod(0o700)
    i = Intent(tmp_path / "intent.json")
    assert i.read()["mode"] == "UNKNOWN"
    run = i.set("RUNNING", actor="owner", reason="fixture", initialize=True)
    stopped = i.set("STOPPED", actor="owner", reason="operator stop")
    with pytest.raises(Refused):
        i.start(run["epoch"], probe=lambda: {})
    run = i.set("RUNNING", actor="owner", reason="resume")
    state = lambda: {"UnitFileState": "enabled", "ActiveState": "failed", "Result": "start-limit-hit"}
    calls = []
    assert (
        i.start(
            run["epoch"],
            probe=state,
            authorize=lambda: True,
            runner=lambda a: calls.append(a) or SimpleNamespace(returncode=0),
            now=100,
        )["action"]
        == "START_REQUESTED"
    )
    assert Intent(i.path).start(run["epoch"], probe=state, authorize=lambda: True, now=101)["action"] == "COOLDOWN"
    assert len(calls) == 1 and not stopped["effective_stop"]


def test_start_stop_race_serializes_effect_before_effective_stop(tmp_path):
    tmp_path.chmod(0o700)
    i = Intent(tmp_path / "intent.json")
    run = i.set("RUNNING", actor="owner", reason="fixture", initialize=True)
    entered, release = threading.Event(), threading.Event()
    sequence = []

    def effect(args):
        sequence.append("start")
        entered.set()
        assert release.wait(3)
        return SimpleNamespace(returncode=0)

    with ThreadPoolExecutor(2) as pool:
        future = pool.submit(
            i.start,
            run["epoch"],
            probe=lambda: {"UnitFileState": "enabled", "ActiveState": "failed", "Result": "watchdog"},
            authorize=lambda: True,
            runner=effect,
        )
        assert entered.wait(3)
        stop = pool.submit(
            i.set, "STOPPED", actor="owner", reason="stop", settle=lambda: sequence.append("settled") or {"settled": True}
        )
        assert not stop.done()
        release.set()
        future.result()
        assert stop.result()["effective_stop"]
    assert sequence == ["start", "settled"]
    with pytest.raises(Refused):
        i.start(run["epoch"], probe=lambda: {})


def test_dependency_wait_persisted_and_recipe_model_free(protocol):
    from forge_factory.afo.dependency_wait import probe

    p = protocol
    observations = []
    first = probe(p.store, "gateway", "healthy", lambda: observations.append(1) or {"ok": False}, now=10)
    assert not probe(p.store, "gateway", "healthy", lambda: observations.append(1), now=11)["due"]
    restored = probe(p.store, "gateway", "healthy", lambda: {"ok": True}, now=first["next_probe"])
    assert restored["healthy"] and len(observations) == 1


def test_verifier_lost_spawn_reclaims_without_duplicating_live_worker(protocol):
    from forge_factory.afo.verification_job import VerificationJobs

    p = protocol
    q = VerificationJobs(p.store)
    q.ensure(p.ctx.job_id, p.ctx.case_sha256)
    attempts = []
    epoch = q.dispatch(p.ctx.job_id, lambda e: attempts.append(e), now=10)
    assert q.dispatch(p.ctx.job_id, lambda e: attempts.append(e), now=11) is None
    epoch = q.dispatch(p.ctx.job_id, lambda e: attempts.append(e), now=41)
    assert attempts == [1, 2]
    q.claim(p.ctx.job_id, epoch, now=42)
    # A lease timeout must not start a second process while this exact process identity is alive.
    assert q.dispatch(p.ctx.job_id, lambda e: attempts.append(e), now=1000) is None
    q.finish(p.ctx.job_id, epoch, {"status": "REJECTED", "reference": "independent-verifier-fixture"})
    assert q.dispatch(p.ctx.job_id, lambda e: attempts.append(e), now=1001) is None
    with pytest.raises(Refused):
        q.finish(p.ctx.job_id, 1, {"status": "PASS"})


def test_gross_timeline_keeps_unknown_and_operator_maintenance():
    from forge_factory.afo.continuous_metrics import timeline

    report = timeline(
        [
            {"at": 0, "control_plane": True, "worker_ready": False, "product_progress": "BLOCKED"},
            {
                "at": 120,
                "control_plane": False,
                "worker_ready": False,
                "desired_mode": "STOPPED",
                "cause": "OPERATOR_MAINTENANCE",
            },
        ],
        0,
        300,
        stale_after=60,
    )
    assert report["window_seconds"] == 300 and report["available_seconds"] == 60 and report["unavailable_seconds"] == 240
    assert sum(i["seconds"] for i in report["intervals"]) == 300
    assert report["worker_ready_seconds"] == 0 and report["rolling_30_day_status"] == "NOT_DEMONSTRATED"


def test_disposable_cleanup_retains_pins_and_refuses_unmarked_evidence(tmp_path):
    from forge_factory.afo.housekeeping import clean

    tmp_path.joinpath(".forge-disposable").write_text("forge-c-scratch-v1")
    a = tmp_path / "scratch"
    a.write_text("scratch")
    assert clean(tmp_path, pinned=[a], now=time.time() + 90000)["deleted_files"] == 0
    assert clean(tmp_path, now=time.time() + 90000)["deleted_files"] == 1
    tmp_path.joinpath(".forge-disposable").unlink()
    with pytest.raises(Refused):
        clean(tmp_path)


def test_crash_between_execution_intent_and_job_projection_never_relaunches(protocol, monkeypatch):
    p = protocol
    job = ready(p, monkeypatch)
    ex = Executions(p.store)
    ex.reserve(job["job_id"], "mission-test", job["nonce"])
    ex.dispatch_intent(job["job_id"])
    client = SimpleNamespace(list_runs=lambda **kw: [], usage=lambda _: {})
    launches = []
    job = L.poll(p.store, p.order, job, p.eff, client=client, launch_fn=lambda _: launches.append(1))
    assert not launches and job["state"] == "LAUNCHING"
    assert ex.get(job["job_id"])["resource_lease"] == "HELD"


def test_receipt_identity_and_fake_independent_verifier_are_rejected(protocol):
    p = protocol
    b = Receipts(p.store)
    r = b.submit(p.ctx, p.proposal)
    with pytest.raises(Refused):
        b._advance(r["receipt_id"], r["revision"], {"launch_nonce": "b" * 32})
    with pytest.raises(Refused):
        b._advance(r["receipt_id"], r["revision"], {"execution_state": "VERIFIED", "verification_receipt_ref": "model-says-pass"})
    assert b.latest(r["receipt_id"]) == r


def test_product_and_diagnosis_share_single_ledger_and_native_ownership(protocol, monkeypatch):
    from forge_factory.afo import product_job
    from forge_factory.afo.request_admission import reserve
    from forge_factory.lrtx import role_capability

    p = protocol
    monkeypatch.setattr(role_capability, "admit_job", lambda *a, **kw: {"fixture": True})
    monkeypatch.setattr(L, "authorized", lambda *a: True)
    eff = SimpleNamespace(
        sha256=p.eff.sha256, get=lambda k, *a: 32000 if k == "budgets.max_model_tokens_per_order" else p.eff.get(k, *a)
    )
    attempt = p.store.attempts(p.order["order_id"])[0]
    job = product_job.prepare(p.store, p.order, attempt, "c" * 32, {"model": "qwen-fixture"}, eff)
    ws = __import__("pathlib").Path(job["workspace"])
    ws.mkdir(parents=True, exist_ok=True)
    product_job.install(ws, {k: job[k] for k in ("job_id", "nonce", "mission_id", "order_id", "attempt_id")})
    ex = Executions(p.store)
    ex.dispatch_intent(job["job_id"])
    ex.adopt(job["job_id"], ["native-product"])
    assert product_job.from_native(p.store, "native-product")["job_id"] == job["job_id"]
    with pytest.raises(Refused):
        ex.reserve(p.ctx.job_id, "mission-test", p.ctx.launch_nonce)
    binding = {"job_id": job["job_id"], "nonce": job["nonce"], "request_id": "product-request", "role": "swe3-author"}
    reserve(p.store, binding, {"model": "qwen-fixture", "messages": [], "max_tokens": 16}, eff=p.eff)
    assert p.ledger.snapshot("mission-test")["attempts"] == 1 and p.ledger.snapshot("mission-test")["jobs"] == 1


def test_registered_semantic_wire_and_submission_ticket(protocol, monkeypatch):
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import afo
    from forge_factory.afo.durable import schema
    from forge_factory.common import state_dir

    p = protocol
    case = state_dir() / "afo/cases/semantic-wire/case.json"
    case.parent.mkdir(parents=True)
    case.write_bytes(__import__("pathlib").Path(p.job["case"]).read_bytes())
    job = {**p.job, "case": str(case), "state": "RUNNING"}
    L.save(p.store, job)
    monkeypatch.delenv("FORGE_MCP_TRUST", raising=False)
    monkeypatch.setenv("FORGE_AFO_CASE", str(case))
    monkeypatch.setenv("FORGE_BINDING_ID", job["job_id"])
    app = sdk.build_server("forge-afo-mcp", afo.OPERATIONS)
    wire = next(t.parameters for t in app._tool_manager.list_tools() if t.name == "submit_recovery_plan")
    assert wire["$defs"]["SemanticProposal"] == schema("semantic-proposal")
    args = {"semantic": p.proposal}
    tool = "mcp__forge_afo_mcp__submit_recovery_plan"
    sdk.issue_ticket(job["job_id"], tool, args, "afo-recovery-planner", "agent", None, str(p.ws))
    op = next(o for o in afo.OPERATIONS if o.name == "submit_recovery_plan")
    out = sdk.invoke("forge-afo-mcp", op, args)
    assert out["status"] == "PASS" and out["metrics"]["submission_state"] == "STORED"
    assert not (case.parent / "proposed-plan.json").exists()
    r = Receipts(p.store).for_job(Context.from_job(p.store, job["job_id"]))[0]
    assert r["admissibility_state"] == "PENDING" and r["execution_state"] == "NOT_REQUESTED"


def test_native_terminal_does_not_release_unknown_provider_generation(protocol):
    p = protocol
    ex = Executions(p.store)
    ex.reserve(p.ctx.job_id, "mission-test", p.ctx.launch_nonce)
    ex.dispatch_intent(p.ctx.job_id)
    ex.adopt(p.ctx.job_id, ["native-A"])
    p.ledger.reserve_request(
        "mission-test",
        p.ctx.job_id,
        "request-still-generating",
        body_sha256="a" * 64,
        input_tokens=100,
        output_cap=10,
        authorize=lambda: True,
    )
    p.ledger.start_request("request-still-generating", authorize=lambda: True)
    p.ledger.reconcile_request("request-still-generating", quiescent=False)
    terminal = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "FAILED"}}})
    rec = ex.reconcile(p.ctx.job_id, terminal)
    assert rec["execution_liveness"] == "UNKNOWN" and rec["resource_lease"] == "HELD"
    with pytest.raises(Refused):
        p.ledger.acquire_inference("another-job", "mission-test")
    # A complete provider response is independent termination evidence; usage can still remain UNKNOWN.
    p.ledger.reconcile_request("request-still-generating", quiescent=True, evidence_ref="gateway-finish:request-still-generating")
    rec = ex.reconcile(p.ctx.job_id, terminal)
    assert rec["resource_lease"] == "RELEASED" and rec["execution_liveness"] == "QUIESCENT"
    assert p.ledger.snapshot("mission-test")["usage_unknown"]


def test_provider_send_after_native_quiescence_is_fenced(protocol):
    p = protocol
    ex = Executions(p.store)
    ex.reserve(p.ctx.job_id, "mission-test", p.ctx.launch_nonce)
    ex.dispatch_intent(p.ctx.job_id)
    ex.adopt(p.ctx.job_id, ["native-A"])
    p.ledger.reserve_request(
        "mission-test",
        p.ctx.job_id,
        "reserved-not-sent",
        body_sha256="a" * 64,
        input_tokens=100,
        output_cap=10,
        authorize=lambda: True,
    )
    terminal = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "FAILED"}}})
    assert ex.reconcile(p.ctx.job_id, terminal)["resource_lease"] == "RELEASED"
    with pytest.raises(Refused):
        p.ledger.start_request("reserved-not-sent", authorize=lambda: True)


def test_hung_owned_verifier_group_is_killed_then_safely_reclaimed(protocol, tmp_path):
    import os, signal, subprocess, sys
    from forge_factory.afo.verification_job import VerificationJobs, identity
    from forge_factory.common import REPO_ROOT

    p = protocol
    q = VerificationJobs(p.store)
    q.ensure(p.ctx.job_id, p.ctx.case_sha256)
    process = None

    def spawn(epoch):
        nonlocal process
        script = tmp_path / "worker.py"
        script.write_text(
            "import sys,time\nfrom forge_factory.afo.queue import Store\nfrom forge_factory.afo.verification_job import VerificationJobs\nVerificationJobs(Store()).claim(sys.argv[1],int(sys.argv[2]))\ntime.sleep(60)\n"
        )
        process = subprocess.Popen(
            [sys.executable, str(script), p.ctx.job_id, str(epoch)],
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT / "factory/python")},
            start_new_session=True,
        )

    epoch = q.dispatch(p.ctx.job_id, spawn)
    try:
        until = time.monotonic() + 5
        while q.get(p.ctx.job_id)["state"] != "RUNNING" and time.monotonic() < until:
            time.sleep(0.05)
        owner = q.get(p.ctx.job_id)["record"]["owner"]
        assert owner == identity(process.pid)
        os.kill(process.pid, signal.SIGSTOP)
        assert q.dispatch(p.ctx.job_id, lambda _: None, now=time.time() + 61) is None
        process.wait(timeout=5)
        assert process.returncode == -signal.SIGKILL
        assert q.get(p.ctx.job_id)["state"] == "CANCELLING"
        reclaimed = q.dispatch(p.ctx.job_id, lambda _: None, now=time.time() + 62)
        assert reclaimed == epoch + 1
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)


def test_continuous_service_render_uses_actual_local_namespace_and_shared_state(tmp_path, monkeypatch):
    from forge_factory.afo import services

    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(tmp_path / "intent.json"))
    monkeypatch.setenv("FORGE_OPERATIONS_PROFILE", "local-rtx-v2-omniverse2")
    monkeypatch.setenv("FORGE_CONDUCTOR_UNIT", "forge-conductor-local-omniverse2.service")
    monkeypatch.setenv("FORGE_CONDUCTOR_FABRO_UNIT", "external-local-profile")
    monkeypatch.setenv("FORGE_LRTX_ROOT", str(tmp_path / "profile"))
    units = services.render()
    conductor = units["forge-conductor-local-omniverse2.service"]
    assert "Restart=always" in conductor and "StartLimitBurst=5" in conductor
    assert "forge_factory.lrtx.stack exec --profile local-rtx-v2-omniverse2" in conductor
    assert str(tmp_path / "profile/state") in conductor and "forge-fabro-cloud.service" not in conductor
    assert "FORGE_CONDUCTOR_UNIT=forge-conductor-local-omniverse2.service" in units["forge-afo-watchdog.service"]
    assert "--max-cycles" not in conductor


def test_systemd_restart_recipe_requires_existing_cre_operational_authority(tmp_path):
    tmp_path.chmod(0o700)
    intent = Intent(tmp_path / "intent.json")
    rec = intent.set("RUNNING", actor="owner", reason="fixture", initialize=True)
    calls = []
    result = intent.start(
        rec["epoch"],
        probe=lambda: {"UnitFileState": "enabled", "ActiveState": "failed", "Result": "watchdog"},
        runner=lambda argv: calls.append(argv),
        authorize=lambda: False,
    )
    assert result["action"] == "WAITING_FOR_PREAUTHORIZED_OPERATIONAL_RECIPE" and calls == []


def test_pending_service_manager_start_is_settled_before_effective_shutdown(protocol, tmp_path, monkeypatch):
    from forge_factory.afo.operations import settle_shutdown

    tmp_path.chmod(0o700)
    intent = Intent(tmp_path / "intent.json")
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(intent.path))
    intent.set("RUNNING", actor="owner", reason="fixture", initialize=True)
    with intent.lock():
        rec = intent.read()
        intent._write({**rec, "pending_start": True})
    intent.set("STOPPED", actor="owner", reason="newer stop")
    calls = []
    result = settle_shutdown(
        protocol.store,
        client=SimpleNamespace(),
        stop_runner=lambda args: calls.append(args) or SimpleNamespace(returncode=0),
        probe=lambda: {"ActiveState": "inactive", "Job": "17"},
    )
    assert not result["settled"] and not intent.read()["effective_stop"]
    assert intent.read()["pending_start"]
    result = settle_shutdown(
        protocol.store,
        client=SimpleNamespace(),
        stop_runner=lambda args: calls.append(args) or SimpleNamespace(returncode=0),
        probe=lambda: {"ActiveState": "inactive", "Job": "0"},
    )
    assert result["settled"] and intent.read()["effective_stop"]
    assert not intent.read()["pending_start"] and len(calls) == 2


def test_profile_recovery_preserves_uncertain_inference_owner(protocol, tmp_path, monkeypatch):
    from forge_factory.afo import operations
    from forge_factory.lrtx import stack

    tmp_path.chmod(0o700)
    intent = Intent(tmp_path / "intent.json")
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(intent.path))
    monkeypatch.setenv("FORGE_OPERATIONS_PROFILE", "local-fixture")
    intent.set("RUNNING", actor="owner", reason="fixture", initialize=True)
    monkeypatch.setattr(operations, "operational_authorized", lambda *a: True)
    calls = []
    monkeypatch.setattr(stack, "_start", lambda *a, **kw: calls.append(a) or {"health": {}})
    Executions(protocol.store).reserve(protocol.ctx.job_id, "mission-test", protocol.ctx.launch_nonce)
    assert operations.recover_profile(protocol.store)["result"]["code"] == "NATIVE_QUIESCENCE_UNPROVEN"
    assert not calls


def test_dependency_wait_survives_process_restart_and_clock_regression(protocol):
    from forge_factory.afo.dependency_wait import probe

    calls = []
    observe = lambda: calls.append(True) or {"ok": False}
    first = probe(protocol.store, "gateway", "profile-a", observe, now=1000)
    second = probe(protocol.store, "gateway", "profile-a", observe, now=1001)
    assert first["failures"] == 1 and not second["due"] and len(calls) == 1
    regressed = probe(protocol.store, "gateway", "profile-a", observe, now=1)
    assert regressed["clock_regression"] and regressed["next_probe"] == 601
    restored = probe(protocol.store, "gateway", "profile-a", lambda: {"ok": True}, now=602)
    assert restored["healthy"] and restored["failures"] == 0


def test_automatic_stack_recovery_refuses_live_legacy_pid_without_identity(tmp_path, monkeypatch):
    import os
    from forge_factory.lrtx import stack

    (tmp_path / "venv/bin").mkdir(parents=True)
    (tmp_path / "venv/bin/python").touch()
    (tmp_path / "run").mkdir()
    (tmp_path / "run/services.json").write_text(json.dumps({"processes": {}}))
    monkeypatch.setattr(stack, "_holder", lambda s: os.getpid())
    monkeypatch.setattr(stack, "envmap", lambda s: {})
    with pytest.raises(ValueError, match="LOCAL_NAMESPACE_OWNERSHIP_UNPROVEN"):
        stack._start({"root": tmp_path, "ports": {}, "profile": {}}, recovery=True)


def test_gateway_adopts_authoritative_native_nonce_before_detach_ack(protocol):
    from forge_factory.afo.product_job import from_native

    p = protocol
    ex = Executions(p.store)
    ex.reserve(p.ctx.job_id, "mission-test", p.ctx.launch_nonce)
    ex.dispatch_intent(p.ctx.job_id)
    native = {"labels": {"afo_agent": p.ctx.job_id, "afo_nonce": p.ctx.launch_nonce}}
    binding = from_native(p.store, "early-native", client=SimpleNamespace(get_run=lambda _: native))
    assert binding == {"job_id": p.ctx.job_id, "nonce": p.ctx.launch_nonce}
    assert ex.get(p.ctx.job_id)["native_run_ids"] == ["early-native"]
    assert ex.get(p.ctx.job_id)["resource_lease"] == "HELD"


def test_continuous_native_probes_and_cancel_ack_are_backed_off_durably(protocol, monkeypatch):
    from forge_factory.afo import dependency_wait

    p = protocol
    ex = Executions(p.store)
    ex.reserve(p.ctx.job_id, "mission-test", p.ctx.launch_nonce)
    ex.dispatch_intent(p.ctx.job_id)
    ex.adopt(p.ctx.job_id, ["native-probe"])
    monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "1")
    now = [1000]
    monkeypatch.setattr(dependency_wait.time, "time", lambda: now[0])
    calls = []
    status = ["RUNNING"]
    client = SimpleNamespace(
        get_run=lambda _: calls.append("status") or {"lifecycle": {"status": {"kind": status[0]}}},
        cancel=lambda _: calls.append("cancel") or 202,
    )
    first = ex.reconcile(p.ctx.job_id, client, cancel=True)
    assert first["resource_lease"] == "HELD" and calls == ["status", "cancel"]
    now[0] = 1001
    ex.reconcile(p.ctx.job_id, client, cancel=True)
    assert calls == ["status", "cancel"]
    now[0] = 1016
    status[0] = "CANCELLED"
    settled = ex.reconcile(p.ctx.job_id, client, cancel=True)
    assert settled["resource_lease"] == "RELEASED" and calls == ["status", "cancel", "status"]
