"""Actual broker/gateway/controller integration with typed fixtures, never live Qwen."""

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
    original = A.reserve
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
        i.start(run["epoch"], probe=state, runner=lambda a: calls.append(a) or SimpleNamespace(returncode=0), now=100)["action"]
        == "START_REQUESTED"
    )
    assert Intent(i.path).start(run["epoch"], probe=state, now=101)["action"] == "COOLDOWN"
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
