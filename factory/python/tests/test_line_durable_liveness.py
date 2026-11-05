"""Real ledger controls, zero inference. API emptiness never proves provider quiescence."""

import time
from types import SimpleNamespace

import pytest
from forge_factory.afo import line_launcher as LL
from forge_factory.afo import line_liveness as L
from forge_factory.afo import policy, product_job
from forge_factory.afo.durable import Refused
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import Store
from test_afo_m2_queue import _env


@pytest.fixture
def execution(tmp_path, monkeypatch):
    root = tmp_path / "runtime"
    state = root / "state"
    monkeypatch.setenv("FORGE_STATE_DIR", str(state))
    repo = tmp_path / "repo"
    (repo / "afo-manifests").mkdir(parents=True)
    cfg = LL.LineConfig(stack_root=root, gpu_lock=tmp_path / "gpu.lock")
    store = Store(L.path(cfg))
    oid, _ = store.submit(_env(repo), repo=repo, max_queued=10)
    epoch = store.acquire_lease("line:local", "fixture", 120)
    aid = store.admit(oid, epoch=epoch, scope="line:local", policy_sha256="fixture", authorization_id="fixture", max_concurrent=1)
    store.attempt_transition(aid, "DISPATCH_PENDING", workspace_ref="workorder:WO-FIXTURE")
    ledger = MissionLedger(store)
    ledger.register(
        "fixture",
        "fixture",
        {
            "max_attempts": 3,
            "max_jobs": 2,
            "max_requests": 4,
            "max_tokens": 1000000,
            "max_tools": 12,
            "max_corrections": 1,
            "deadline": time.time() + 300,
        },
        "FIXTURE_NOT_LIVE_AUTHORITY",
        authorize=lambda *a: True,
    )
    ledger.link("fixture", oid)
    job = product_job.prepare(store, store.order(oid), store.attempts(oid)[0], "a" * 32, {"model": "fixture"}, policy.load())
    ex = Executions(store)
    ex.dispatch_intent(job["job_id"])
    return cfg, store, job, ex, ledger


def test_held_unknown_execution_blocks_ordinary_m2_even_with_empty_fabro(execution):
    cfg, store, job, ex, ledger = execution
    host = SimpleNamespace(fabro_runs=lambda: [])
    with pytest.raises(LL.LaunchError, match="DURABLE_EXECUTION_BUSY"):
        LL.live_runs(cfg, host)
    assert ex.get(job["job_id"])["resource_lease"] == "HELD"


def test_only_original_nonce_fresh_local_launch_claim_excludes_its_own_unsubmitted_slot(execution):
    cfg, store, job, ex, ledger = execution
    exclusion = L.claim(cfg, job)
    L.clear(cfg, exclusion=exclusion)
    with pytest.raises(L.ClaimUncertain, match="ALREADY_CLAIMED"):
        L.claim(cfg, job)
    with pytest.raises(Refused):
        L.clear(cfg, exclusion=dict(exclusion, nonce="different"))
    assert ex.get(job["job_id"])["resource_lease"] == "HELD"


def test_unknown_provider_is_busy_even_for_own_nonce_and_native_has_ended(execution):
    cfg, store, job, ex, ledger = execution
    exclusion = L.claim(cfg, job)
    ledger.reserve_request(
        "fixture", job["job_id"], "request", body_sha256="b" * 64, input_tokens=1, output_cap=1, authorize=lambda: True
    )
    ledger.start_request("request", authorize=lambda: True)
    ledger.reconcile_request("request", quiescent=False)
    with pytest.raises(Refused, match="PROVIDER_REQUEST_NOT_QUIESCENT"):
        L.clear(cfg, exclusion=exclusion)
    assert ex.get(job["job_id"])["resource_lease"] == "HELD"


def test_old_native_id_never_gets_fresh_launch_exclusion(execution):
    cfg, store, job, ex, ledger = execution
    ex.adopt(job["job_id"], ["old-native"])
    with pytest.raises(L.ClaimUncertain, match="ALREADY_OR_POSSIBLY_DISPATCHED"):
        L.claim(cfg, job)


def test_model_free_guard_does_not_create_missing_store(tmp_path):
    cfg = LL.LineConfig(stack_root=tmp_path / "missing")
    L.clear(cfg)
    assert not L.path(cfg).exists()
