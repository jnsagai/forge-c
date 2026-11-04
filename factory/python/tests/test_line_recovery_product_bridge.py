"""CONTROL fixtures for the real outbox/mission/receipt bridge, never live qualification.

Only external authority, model transport and engineering-gate observations are
substituted. SQLite transitions, immutable payloads, nonce adoption, finite
accounting and semantic proposal admission use their production implementations.
"""

# ruff: noqa: F811 - imported pytest fixtures are used by name
import copy
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import line_recovery_control as C
from forge_factory.afo import line_recovery_coordination as K
from forge_factory.afo import line_recovery_product as P
from forge_factory.afo import line_recovery_worker as W
from forge_factory.afo import local_agent as L
from forge_factory.afo import operations, policy, recovery
from forge_factory.afo.durable import Refused, digest, immutable_json
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import Store
from forge_factory.common import sha256_file
from test_afo_m2_queue import _env
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_protocol import protocol  # noqa: F401


@pytest.fixture
def product(tmp_path, monkeypatch, request):
    from forge_factory import workorder
    from forge_factory.afo import line_launcher as LL
    from forge_factory.afo import line_orders as O
    from forge_factory.lrtx.profile import load

    state = tmp_path / "lrtx/state"
    monkeypatch.setenv("FORGE_STATE_DIR", str(state))
    monkeypatch.setenv("FORGE_AFO_QUEUE_SCOPE", "line-local")
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", str(tmp_path / "intent.json"))
    managed = getattr(request, "param", False)
    monkeypatch.setattr(operations, "configured", lambda: managed)
    if managed:
        operations.Intent().set("RUNNING", actor="private-fixture-owner", reason="isolated managed control", initialize=True)
    store = Store(state / "supervisor/line-queue.sqlite3")
    repo = tmp_path / "repo"
    (repo / "afo-manifests").mkdir(parents=True)
    wo = "WO-F014-SWE3-FIXTURE-20261104-L99"
    profile = load("local-rtx-v2-omniverse2")
    model = "qwen3.6:35b-a3b"
    eff = SimpleNamespace(
        mode="PILOT",
        sha256="c" * 64,
        get=lambda k, default=None: {"budgets.max_model_tokens_per_order": 120000, "budgets.max_order_wall_seconds": 600}.get(
            k, default
        ),
    )
    limits = dict(
        max_attempts=3,
        max_jobs=3,
        max_requests=20,
        max_tokens=500000,
        max_tools=50,
        max_corrections=2,
        deadline=time.time() + 600,
    )
    control = {
        "mission": {"mission_id": "fixture-mission", "lineage": "fixture-lineage", "limits": limits},
        "source_revision": "a" * 40,
        "policy_sha256": eff.sha256,
        "authorization_ref": "fixture-not-live",
        "profile": profile["id"],
        "profile_sha256": profile["_sha256"],
        "role_capabilities": {},
        "product_role_trial": None,
        "operations_intent": str(tmp_path / "intent.json"),
    }
    control_path = tmp_path / "control.json"
    immutable_json(control_path, control)
    ref = {"path": str(control_path), "sha256": sha256_file(control_path)}
    spec = {
        "schema": O.ORDER_SCHEMA,
        "wo": wo,
        "revision": "a" * 40,
        "profile": profile["id"],
        "run_model": model,
        "purpose": "ASPICE_ONLY",
        "example": "0014-crc-st",
        "driver_class": "STM32N6_CRC_HAL",
        "phase": "SWE.3",
        "stop_after": "SWE.3",
        "resume_from": None,
        "resume_upto": None,
        "provided_from": None,
        "quality": {"targets": {"test": 100}},
        "quality_via": "FLAG",
        "durable_control": ref,
    }
    spec["digest"] = O._digest(spec)
    oid, _ = store.submit(
        _env(
            repo,
            rid=wo,
            model=profile["id"],
            tenant_scope="line-local",
            payload_digest=spec["digest"],
            driver_class=spec["driver_class"],
            target=spec["example"],
        ),
        repo=repo,
        max_queued=10,
    )
    epoch = store.acquire_lease("line:local", "fixture", 600)
    aid = store.admit(
        oid, epoch=epoch, scope="line:local", policy_sha256="c" * 64, authorization_id="fixture-not-live", max_concurrent=1
    )
    path = O.supervisor_dir() / "line-orders" / (wo + ".json")
    immutable_json(path, spec)
    worker = {
        "schema": K.REQUEST_SCHEMA,
        "mode": "PRODUCT",
        "order_id": oid,
        "attempt_id": aid,
        "control_ref": ref,
        "spec_ref": {"path": str(path), "sha256": sha256_file(path)},
        "line_origin": {"campaign_path": str(tmp_path / "approved-campaign.yaml")},
    }
    cmd = store.commands("PENDING")[0]
    K._bind_command(store, cmd["command_id"], worker)
    cmd = K.command(store, cmd["command_id"])
    grant = SimpleNamespace(permit=lambda *a, **kw: SimpleNamespace(allow=True, code="AUTH_OK"))
    monkeypatch.setattr(W, "bound_order", lambda *a: {"grant": grant})
    monkeypatch.setattr(C, "configuration", lambda *a, **kw: copy.deepcopy(control))
    monkeypatch.setattr(policy, "load", lambda: eff)
    monkeypatch.setattr(workorder, "factory_revision", lambda: {"commit": "a" * 40, "dirty": False})
    client = SimpleNamespace(list_runs=lambda **kw: [])
    cfg = LL.LineConfig(stack_root=tmp_path / "lrtx")
    return SimpleNamespace(
        store=store, oid=oid, aid=aid, cmd=cmd, worker=worker, spec=spec, control=control, eff=eff, client=client, cfg=cfg
    )


def test_product_uses_original_outbox_mission_and_hash_bound_m2_payload(product):
    p = product
    seen = []

    def transport(order, cfg):
        order.validate()
        payload = P.validate_launch_order(order)
        assert payload["binding"]["mission_id"] == "fixture-mission"
        assert payload["labels"]["afo_attempt"] == p.aid
        assert payload["order"]["quality"] == p.spec["quality"]
        seen.append(payload)
        return {"outcome": "LAUNCHED", "fabro_run_id": "CONTROL-NATIVE"}

    out = P.dispatch(p.store, p.cmd, p.worker, p.spec, p.eff, p.client, cfg=p.cfg, launch=transport)
    assert out["actions"][0]["action"] == "launched" and len(seen) == 1
    job = P.registered(p.store, P.job_id(p.aid))
    assert job["factory_revision"] == {"commit": "a" * 40, "dirty": False}
    assert Executions(p.store).get(job["job_id"])["native_run_ids"] == ["CONTROL-NATIVE"]
    assert MissionLedger(p.store).snapshot("fixture-mission")["attempts"] == 1
    assert K.command(p.store, p.cmd["command_id"])["state"] == "ACKED"
    P.dispatch(
        p.store,
        K.command(p.store, p.cmd["command_id"]),
        p.worker,
        p.spec,
        p.eff,
        p.client,
        launch=lambda *a: pytest.fail("duplicate native invocation"),
    )
    # The substituted transport proves no model request, role competence or gate PASS.
    assert not Path(job["binding"]).exists()


@pytest.mark.parametrize("observation", ["unreachable", "empty", "one", "two"])
def test_lost_receipt_restart_preserves_nonce_and_never_blindly_relaunches(product, observation):
    p = product

    def crash(order, cfg):
        raise TimeoutError("CONTROL transport outcome unknown")

    P.dispatch(p.store, p.cmd, p.worker, p.spec, p.eff, p.client, launch=crash)
    cmd = K.command(p.store, p.cmd["command_id"])
    job = P.registered(p.store, P.job_id(p.aid))
    hits = [{"id": "CONTROL-NATIVE", "labels": {"afo_attempt": p.aid, "afo_nonce": job["nonce"]}}]
    if observation == "unreachable":

        def unavailable(**kw):
            raise OSError("ordinary stack turnover can briefly remove the API")

        p.client.list_runs = unavailable
    else:
        p.client.list_runs = lambda **kw: [] if observation == "empty" else hits * (1 if observation == "one" else 2)
    result = P.dispatch(
        p.store, cmd, p.worker, p.spec, p.eff, p.client, launch=lambda *a: pytest.fail("unknown dispatch relaunched")
    )
    assert len(result["actions"]) == 1
    live = Executions(p.store).get(job["job_id"])
    assert live["launch_nonce"] == job["nonce"] and live["resource_lease"] == "HELD"
    assert MissionLedger(p.store).snapshot("fixture-mission")["attempts"] == 1
    assert (
        K.command(p.store, cmd["command_id"])["state"]
        == {"unreachable": "UNKNOWN", "empty": "IN_FLIGHT", "one": "ACKED", "two": "QUARANTINED"}[observation]
    )


@pytest.mark.parametrize(
    "outcome,submitted,expected",
    [("SMOKE_FAIL", False, "item_blocked"), ("WORKORDER_LAUNCH_FAILED", True, "launch_outcome_unknown"),
     ("STACK_STARTUP_CLEANUP_UNKNOWN", False, "launch_outcome_unknown")],
)
def test_pre_native_proof_and_possible_native_effect_have_distinct_release_rules(product, outcome, submitted, expected):
    p = product

    def transport(order, cfg):
        if submitted:
            Executions(p.store)._save_evidence(P.job_id(p.aid), "PRODUCT_NATIVE_SUBMIT_INTENT", {"fixture": True})
        return {"outcome": outcome}

    result = P.dispatch(p.store, p.cmd, p.worker, p.spec, p.eff, p.client, launch=transport)
    assert result["actions"][0]["action"] == expected
    live = Executions(p.store).get(P.job_id(p.aid))
    assert live["resource_lease"] == ("HELD" if submitted or outcome == "STACK_STARTUP_CLEANUP_UNKNOWN" else "RELEASED")


def test_initial_mission_cannot_retroactively_import_a_native_execution(product):
    p = product
    p.store.attempt_transition(p.aid, "DISPATCH_PENDING")
    p.store.attempt_transition(p.aid, "RUNNING", fabro_run_id="UNACCOUNTED-HISTORY")
    with pytest.raises(Refused, match="HISTORICAL_ACCOUNTING_REQUIRED"):
        P.link_mission(p.store, p.store.order(p.oid), p.control, p.spec)
    with pytest.raises(Refused, match="MISSION_LINK_REQUIRED"):
        MissionLedger(p.store).for_order(p.oid)


def test_exhausted_finite_mission_refuses_before_external_model_or_m2_launch(product):
    p = product
    p.control["mission"]["limits"]["max_attempts"] = 0  # CONTROL authority input; no production policy edit
    result = P.dispatch(
        p.store,
        p.cmd,
        p.worker,
        p.spec,
        p.eff,
        p.client,
        launch=lambda *a: pytest.fail("exhausted mission reached external launcher"),
    )
    assert result["actions"][0]["code"] == "MISSION_ALLOWANCE_EXHAUSTED"
    assert MissionLedger(p.store).snapshot("fixture-mission")["attempts"] == 0


def test_fresh_phase_names_cannot_reset_strategy_variants_for_the_same_finite_driver(product, tmp_path):
    from forge_factory.afo import line_orders as O

    p = product
    P.link_mission(p.store, p.store.order(p.oid), p.control, p.spec)
    failure = {"order_id": p.oid, "attempt_id": p.aid, "phase": "SWE.3", "fingerprint": "CONTROL"}
    for n in (1, 2):
        plan = recovery._base(failure, "REWORK_LOCAL", "SWE.3", "CONTROL", material_difference_ref=f"CONTROL:{n}")
        recovery.record_plan(p.store, plan, source="PLANNER", status="EXECUTED", reasons=[], budget={})
    repo = tmp_path / "next-repo"
    (repo / "afo-manifests").mkdir(parents=True)
    spec = {**p.spec, "wo": p.spec["wo"] + "B"}
    spec["digest"] = O._digest(spec)
    oid, _ = p.store.submit(
        _env(
            repo,
            rid=spec["wo"],
            model=spec["profile"],
            tenant_scope="line-local",
            payload_digest=spec["digest"],
            driver_class=spec["driver_class"],
            target=spec["example"],
        ),
        repo=repo,
        max_queued=10,
    )
    immutable_json(O.supervisor_dir() / "line-orders" / (spec["wo"] + ".json"), spec)
    MissionLedger(p.store).link("fixture-mission", oid, continuation_of=p.oid)
    caps = {
        "budgets.max_order_attempts": 3,
        "budgets.max_retries_per_transient_operation": 2,
        "budgets.max_strategy_variants_per_phase": 2,
        "budgets.max_recovery_model_calls_per_order": 4,
        "budgets.max_order_wall_seconds": 86400,
    }
    eff = SimpleNamespace(get=lambda key, default=None: caps.get(key, default))
    assert len(recovery.strategy_history(p.store, oid)) == 2
    assert recovery.budget_snapshot(p.store, p.store.order(oid), eff)["variants_by_phase"]["SWE.3"] == 2


def test_repeated_mission_registration_never_resets_spent_capacity(product):
    p = product
    P.link_mission(p.store, p.store.order(p.oid), p.control, p.spec)
    ledger = MissionLedger(p.store)
    ledger.execution("fixture-mission", "already-spent", "DIAGNOSIS", reserved_tokens=1000)
    before = ledger.snapshot("fixture-mission")
    P.link_mission(p.store, p.store.order(p.oid), p.control, p.spec)
    assert ledger.snapshot("fixture-mission") == before
    changed = copy.deepcopy(p.control)
    changed["mission"]["limits"]["max_tokens"] += 1
    with pytest.raises(Refused, match="SIGNED_MISSION_LIMITS_MISMATCH"):
        P.link_mission(p.store, p.store.order(p.oid), changed, p.spec)


def test_held_product_is_supervised_after_grant_expiry_without_new_placement(product, tmp_path, monkeypatch):
    p = product
    P.dispatch(
        p.store, p.cmd, p.worker, p.spec, p.eff, p.client, launch=lambda *a: {"outcome": "LAUNCHED", "fabro_run_id": "ACTIVE"}
    )
    calls = []
    line = SimpleNamespace(
        spawn_recovery_worker=lambda *a, **kw: calls.append((a, kw)) or {"pid": 1, "start": "fixture"}, alive=lambda *a: False
    )
    placer = SimpleNamespace(queue_path=p.store.path, line=line, durable_control=p.worker["control_ref"])
    actions = K.coordinate(placer, [], None, SimpleNamespace(allow=False), [], time.time(), execute=True)
    assert actions[0]["action"] == "DURABLE_SUPERVISION"
    assert calls[0][1] == {"quiesce": True}
    assert K.command(p.store, p.cmd["command_id"])["state"] == "ACKED"
    assert Executions(p.store).get(P.job_id(p.aid))["resource_lease"] == "HELD"


def test_quiesce_keeps_unknown_provider_lease_even_when_native_is_terminal(product, monkeypatch):
    p = product
    P.dispatch(
        p.store, p.cmd, p.worker, p.spec, p.eff, p.client, launch=lambda *a: {"outcome": "LAUNCHED", "fabro_run_id": "ACTIVE"}
    )
    jid = P.job_id(p.aid)
    ledger = MissionLedger(p.store)
    ledger.reserve_request(
        "fixture-mission", jid, "provider-unknown", body_sha256="b" * 64, input_tokens=1, output_cap=1, authorize=lambda: True
    )
    ledger.start_request("provider-unknown", authorize=lambda: True)
    ledger.reconcile_request("provider-unknown", quiescent=False)
    client = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "FAILED"}}}, cancel=lambda _: 202)
    monkeypatch.setattr(L, "authorized_job", lambda *a: False)
    P.supervise_existing(p.store, p.cmd, p.worker, p.eff, client, quiesce=True)
    live = Executions(p.store).get(jid)
    assert live["authorization_state"] == "REVOKED" and live["resource_lease"] == "HELD"
    ledger.reconcile_request("provider-unknown", quiescent=True, evidence_ref="CONTROL-provider-quiescence")
    P.supervise_existing(p.store, p.cmd, p.worker, p.eff, client, quiesce=True)
    assert Executions(p.store).get(jid)["resource_lease"] == "RELEASED"


def test_worker_lock_refusal_cannot_quarantine_another_running_worker(product):
    p = product
    before = p.store.order(p.oid), p.store.commands()
    assert (
        W.record_refusal(p.cmd["command_id"], Refused("LINE_RECOVERY_WORKER_LOCK_HELD"))["action"]
        == "existing_worker_owns_command"
    )
    assert before == (p.store.order(p.oid), p.store.commands())


def test_unchanged_hard_refusal_does_not_allocate_a_fresh_order_identity(product):

    p = product
    W.record_refusal(p.cmd["command_id"], Refused("LINE_NATIVE_TRANSPORT_MEASUREMENT_REQUIRED"))
    a = SimpleNamespace(
        status="CLOSED",
        spec={"durable_control": p.worker["control_ref"], "lineage_sha": "same"},
        queue={"terminal_reason": "LINE_NATIVE_TRANSPORT_MEASUREMENT_REQUIRED"},
    )
    plan = SimpleNamespace(
        atts={"SWE.3": [a]}, lineage=SimpleNamespace(sha256="same"), order={"wo": "WO-WOULD-ALLOCATE"}, action="PLACE"
    )
    placer = SimpleNamespace(queue_path=p.store.path, durable_control=p.worker["control_ref"])
    assert K.coordinate(placer, [plan], None, SimpleNamespace(allow=True), [], time.time(), execute=True) == []
    assert plan.action is None and plan.order is None
    assert plan.reason == "DURABLE_SOURCE_CLOSED_REQUIRES_OWNER_CHANGE"


def test_external_worker_execs_exact_run_checkout_with_the_actual_fixed_line_configuration(product, tmp_path, monkeypatch):
    from forge_factory.afo import line_launcher as LL

    p = product
    p.cfg.runs_root = tmp_path / "runs"
    p.cfg.repo = tmp_path / "repo"
    p.cfg.launch_dir = tmp_path / "launch"
    p.cfg.fabro_host_port = 45678
    p.cfg.guard = ("bash", str(tmp_path / "reviewed guard.sh"))
    wt = p.cfg.runs_root / p.spec["wo"]
    source = wt / "factory/python/forge_factory/afo/line_recovery_worker.py"
    source.parent.mkdir(parents=True)
    source.write_text("# CONTROL source existence; no execution\n")
    monkeypatch.setattr(C, "controller_configuration", lambda *a, **kw: p.control)
    monkeypatch.setattr(LL, "resolve_rev", lambda root, rev: p.control["source_revision"])
    monkeypatch.setattr(LL, "worktree_clean", lambda root: [])
    captured = []
    W.bootstrap(p.cmd["command_id"], cfg=p.cfg, execute=lambda *args: captured.append(args))
    executable, argv, env = captured[0]
    assert argv[-1] == p.cmd["command_id"]
    assert env["PYTHONPATH"].split(":")[0] == str(wt / "factory/python")
    assert env["FORGE_LINE_REPO"] == str(p.cfg.repo)
    assert env["FORGE_LINE_FABRO_PORT"] == "45678"
    assert env["FORGE_LINE_GUARD"] == str(tmp_path / "reviewed guard.sh")
    assert env["FORGE_AFO_QUEUE_SCOPE"] == "line-local"
    assert env["FORGE_OPERATIONS_INTENT"] == p.control["operations_intent"]
    assert env["FORGE_FABRO_URL"] == "http://127.0.0.1:45678/api/v1"


def test_bootstrap_never_prepares_a_new_worktree_for_revoked_or_changed_source(product, monkeypatch):
    from forge_factory.afo import line_launcher as LL

    p = product
    monkeypatch.setattr(LL, "resolve_rev", lambda *a: p.control["source_revision"])
    monkeypatch.setattr(C, "controller_configuration", lambda *a, **kw: (_ for _ in ()).throw(Refused("AUTH_REVOKED")))
    monkeypatch.setattr(LL, "ensure_worktree", lambda *a: pytest.fail("revoked control created a checkout"))
    with pytest.raises(Refused, match="AUTH_REVOKED"):
        W.bootstrap(p.cmd["command_id"], cfg=p.cfg, execute=lambda *a: pytest.fail("revoked source executed"))


def test_accepted_semantic_receipt_creates_fresh_attempt_then_requires_independent_product_gates(protocol, tmp_path, monkeypatch):
    import zipfile

    from forge_factory.afo.completion_receipt import Receipts, verified_attempt
    from forge_factory.inspection.engine import Store as PhaseStore

    p = protocol
    broker = Receipts(p.store)
    stored = broker.submit(p.ctx, p.proposal)
    accepted = broker.admit(stored["receipt_id"], packet=p.packet, bundle=p.bundle, eff=p.eff, authorize=lambda: True)
    assert accepted["admissibility_state"] == "ACCEPTED"
    plan = broker.bound_plan(accepted)
    recovery.record_plan(p.store, plan, source="PLANNER", status="VALIDATED", reasons=[], budget={})
    source_aid = p.bundle["attempt_id"]
    jid = P.job_id(source_aid)
    p.ledger.execution("mission-test", jid, "PRODUCT", reserved_tokens=12000)
    ex = Executions(p.store)
    ex.reserve(jid, "mission-test", "b" * 32)
    ex.dispatch_intent(jid)
    ex.adopt(jid, ["SOURCE"])
    terminal = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "FAILED"}}})
    assert ex.reconcile(jid, terminal)["resource_lease"] == "RELEASED"
    p.store.attempt_transition(source_aid, "FAILED")
    p.store.transition(p.order["order_id"], "WAITING_RECOVERY", "CONTROL phase failed")
    value = {
        "source_order_id": p.order["order_id"],
        "source_attempt_id": source_aid,
        "source_work_order": p.order["request_id"],
        "plan_id": plan["plan_id"],
        "plan_sha256": digest(plan),
        "receipt_id": accepted["receipt_id"],
    }
    spec = {
        "wo": "WO-F014-SWE3-FIXTURE-20261104-L99B",
        "phase": "SWE.3",
        "revision": "a" * 40,
        "driver_class": "STM32N6_RCC_HAL",
        "profile": "fixture",
        "durable_control": {"fixture": True},
        "durable_recovery": value,
    }
    grant = SimpleNamespace(permit=lambda *a: SimpleNamespace(allow=True))
    placer = SimpleNamespace(line=SimpleNamespace(resolve=lambda _: "a" * 40))
    monkeypatch.setattr(C, "controller_configuration", lambda *a, **kw: {"fixture_authority": True})
    monkeypatch.setattr(policy, "load", lambda: p.eff)
    K.prepare_continuation(placer, p.store, spec, grant)
    assert p.store.order(p.order["order_id"])["terminal_reason"] == "CONTINUED_AS:" + spec["wo"]
    repo = tmp_path / "next-repo"
    (repo / "afo-manifests").mkdir(parents=True)
    oid, _ = p.store.submit(_env(repo, rid=spec["wo"]), repo=repo, max_queued=10)
    epoch = p.store.acquire_lease("line:fixture", "fixture", 600)
    aid = p.store.admit(
        oid,
        epoch=epoch,
        scope="line:fixture",
        policy_sha256=p.eff.sha256,
        authorization_id="CONTROL",
        max_concurrent=1,
        recovery_plan_id=plan["plan_id"],
    )
    p.ledger.link("mission-test", oid, continuation_of=p.order["order_id"])
    K.bind_continuation(p.store, spec, oid, aid)
    assert broker.latest(accepted["receipt_id"])["execution_state"] == "APPLYING"
    assert p.ledger.for_order(oid) == p.ledger.for_order(p.order["order_id"])
    # A native SUCCEEDED/phase PASS cannot supply a release-gate verification.
    ws = tmp_path / "product"
    (ws / ".forge-run").mkdir(parents=True)
    attempt = p.store.attempts(oid)[0]
    assert verified_attempt(p.store, attempt, ws)["execution_state"] == "VERIFYING"
    archive = ws / ".forge-run/review.zip"
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("manifest.json", json.dumps({"status": "READY_FOR_OFFLINE_REVIEW", "gaps": []}))
    (ws / ".forge-run/package.json").write_text(
        json.dumps(
            {
                "archive": str(archive),
                "archive_sha256": sha256_file(archive),
                "package_status": "READY_FOR_OFFLINE_REVIEW",
                "gaps": [],
            }
        )
    )
    # Separate deterministic authority fixture, not a model's self-reported success.
    monkeypatch.setattr(PhaseStore, "gate", lambda self, ph: {"decision": "PASS", "reason": "CONTROL independent gate"})
    assert verified_attempt(p.store, attempt, ws)["execution_state"] == "VERIFIED"
    assert broker.verify_chain(accepted["receipt_id"])
    with p.store.tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_durable_effects").fetchone()[0] == 1
    assert len(L.records(p.store, p.order["order_id"])) == 1  # one durable planner identity
