"""Reproduce the recorded overnight blockers without Qwen or live service effects."""
# ruff: noqa: F811

import json
import subprocess
import time
from types import SimpleNamespace

import pytest
from forge_factory import workorder
from forge_factory.afo import diagnosis_packet, dispatch, planner, policy, product_job, runtime
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.local_agent import LaunchNotStarted
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.inspection.engine import PHASES
from test_afo_m3_reconcile import admitted  # noqa: F401
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_protocol import protocol  # noqa: F401


@pytest.mark.parametrize("driver", ["RCC", "sensor_i2c", "usb_dma"])
def test_actual_top_level_author_gate_issues_form_primary_objectives(tmp_path, monkeypatch, driver):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws = tmp_path / "workspace"
    f = ws / ".forge-run/gates/gate-log.jsonl"
    f.parent.mkdir(parents=True)
    f.write_text(
        json.dumps(
            {
                "phase": "SWE.1",
                "step": "author",
                "result": "REJECTED",
                "issues": [
                    "MISSING_REQUIRED_OUTPUT:workproducts/SWE.1/software_requirements.md",
                f"LRTX_TASK_INVALID:requirements:{driver}:CALL_FAILED:HTTP429",
                ],
            }
        )
        + "\n"
        + json.dumps({"phase": "SWE.2", "result": "REJECTED", "issues": ["DOWNSTREAM_SECRET"]})
        + "\n"
    )
    bundle = dict(bundle_id="fixture", order_id="order", attempt_id="attempt", phase="SWE.1", fingerprint="failure")
    ref = diagnosis_packet.build(ws, bundle)
    packet = diagnosis_packet.load(ref)
    assert packet["complete"] and len(packet["findings"]) == 2 and len(packet["obligations"]) == 2
    assert "DOWNSTREAM_SECRET" not in json.dumps(packet)
    assert all(item["source_ref"].startswith(".forge-run/diagnosis-evidence/SWE.1/") for item in packet["findings"])
    path = planner.case(bundle, ws, {"remaining_tokens": 100}, mission_id="mission")
    before = path.read_bytes()
    assert planner.case(bundle, ws, {"remaining_tokens": 50}, mission_id="mission").read_bytes() == before


def test_greenfield_resume_with_no_accepted_phase_keeps_empty_git_commit_valid(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    source = tmp_path / "state/workorders/previous/workspace"
    source.mkdir(parents=True)
    ws = tmp_path / "new"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".gitignore").write_text(".forge-run/\n")
    subprocess.run(["git", "init", "-q", str(ws)], check=True)
    subprocess.run(["git", "-C", str(ws), "add", ".gitignore"], check=True)
    subprocess.run(
        ["git", "-C", str(ws), "-c", "user.name=Fixture", "-c", "user.email=fixture@localhost", "commit", "-qm", "initial"],
        check=True,
    )
    assert workorder.resume_from(ws, {"work_order": "new"}, "previous", "SWE.1") == PHASES
    assert subprocess.check_output(["git", "-C", str(ws), "rev-list", "--count", "HEAD"], text=True).strip() == "2"


@pytest.mark.parametrize("crossed", [False, True])
def test_runtime_distinguishes_local_failure_from_crossed_native_boundary(monkeypatch, crossed):
    def run(*args, **kw):
        if crossed:
            kw["before_native_launch"]()
        raise subprocess.CalledProcessError(1, ["git", "commit"])

    monkeypatch.setattr(workorder, "run", run)
    binding = {"job_id": "product", "nonce": "nonce"}
    with pytest.raises(subprocess.CalledProcessError if crossed else LaunchNotStarted):
        runtime.launcher({"example": "unused", "durable_binding": binding}, "new", {})


def product_setup(admitted, monkeypatch):
    store, oid, aid, epoch = admitted
    limits = dict(
        max_attempts=3, max_jobs=4, max_requests=8, max_tokens=64000, max_tools=32, max_corrections=1, deadline=time.time() + 600
    )
    ledger = MissionLedger(store)
    ledger.register("product", "qualification", limits, "fixture", authorize=lambda *a: True)
    ledger.link("product", oid)
    eff = SimpleNamespace(
        sha256="p",
        get=lambda k, default=None: {"budgets.max_model_tokens_per_order": 32000, "budgets.max_order_wall_seconds": 3600}.get(
            k, default
        ),
    )
    monkeypatch.setattr(policy, "load", lambda: eff)
    return store, oid, aid, ledger


@pytest.mark.parametrize("crossed", [False, True])
def test_product_dispatch_uses_proven_boundary_instead_of_terminal_or_listing_gap(admitted, monkeypatch, crossed):
    store, oid, aid, ledger = product_setup(admitted, monkeypatch)

    def fail(*a, **kw):
        if crossed:
            kw["before_native_launch"]()
        raise TimeoutError("fixture")

    monkeypatch.setattr(workorder, "run", fail)
    dispatch.dispatch_pending(store, runtime.launcher, decide=lambda _: SimpleNamespace(allow=True))
    with store.tx() as c:
        job = json.loads(c.execute("SELECT record FROM afo_product_jobs").fetchone()[0])
    ex = Executions(store)
    assert ledger.snapshot("product")["charged_tokens"] == 32000
    if crossed:
        assert ex.get(job["job_id"])["resource_lease"] == "HELD"
        dispatch.reconcile_inflight(store, lambda: [], now=time.time() + 1000)
        assert ex.get(job["job_id"])["resource_lease"] == "HELD"
        assert store.commands()[0]["state"] == "UNKNOWN"
    else:
        assert ex.get(job["job_id"])["resource_lease"] == "RELEASED"
        assert ex.get(job["job_id"])["execution_liveness"] == "NOT_STARTED"
        assert store.order(oid)["state"] == "BLOCKED"
        assert store.attempts(oid)[0]["state"] == "FAILED"
        assert store.commands()[0]["state"] == "QUARANTINED"


def test_crash_after_product_non_dispatch_proof_recovers_without_listing_or_relaunch(admitted, monkeypatch):
    store, oid, aid, ledger = product_setup(admitted, monkeypatch)
    monkeypatch.setattr(workorder, "run", lambda *a, **kw: (_ for _ in ()).throw(ValueError("preflight")))
    settle = dispatch._settle_local_refusal
    monkeypatch.setattr(dispatch, "_settle_local_refusal", lambda *a: (_ for _ in ()).throw(RuntimeError("crash")))
    with pytest.raises(RuntimeError, match="crash"):
        dispatch.dispatch_pending(store, runtime.launcher, decide=lambda _: SimpleNamespace(allow=True))
    monkeypatch.setattr(dispatch, "_settle_local_refusal", settle)

    def listing():
        pytest.fail("local proof must not depend on native availability")

    dispatch.reconcile_inflight(store, listing)
    assert store.order(oid)["state"] == "BLOCKED"
    assert store.commands()[0]["state"] == "QUARANTINED"
    assert ledger.snapshot("product")["charged_tokens"] == 32000
    assert not Executions(store).pending()


def test_expired_waiting_dispatch_blocks_task_but_retains_unknown_native_owner(protocol, monkeypatch):
    from forge_factory.afo import authority

    p = protocol
    attempt = p.store.attempts(p.order["order_id"])[0]
    eff = SimpleNamespace(
        sha256=p.eff.sha256, get=lambda k, *a: 32000 if k == "budgets.max_model_tokens_per_order" else p.eff.get(k, *a)
    )
    job = product_job.prepare(p.store, p.order, attempt, "c" * 32, {"model": "fixture"}, eff)
    ex = Executions(p.store)
    ex.dispatch_intent(job["job_id"])
    p.store.transition(p.order["order_id"], "RUNNING", "fixture")
    p.store.transition(p.order["order_id"], "WAITING_RECOVERY", "uncertain dispatch")
    monkeypatch.setattr(authority, "decide", lambda *a, **kw: SimpleNamespace(allow=True))
    before = p.ledger.snapshot("mission-test")
    dispatch.enforce_deadlines(p.store, eff, now=before["limits"]["deadline"] + 1)
    assert p.store.order(p.order["order_id"])["state"] == "BLOCKED"
    assert ex.get(job["job_id"])["resource_lease"] == "HELD"
    assert p.ledger.snapshot("mission-test")["charged_tokens"] == before["charged_tokens"]
    assert not p.store.commands("PENDING")
