"""A signed role configuration cannot borrow a different intent or mission. No inference."""

import copy
import time

import pytest
from forge_factory.afo import line_recovery_control as C
from forge_factory.afo.durable import Refused
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import Store
from test_afo_m2_queue import _env


@pytest.fixture
def bound(tmp_path, monkeypatch):
    state = tmp_path / "state"
    monkeypatch.setenv("FORGE_STATE_DIR", str(state))
    store = Store(state / "supervisor/line-queue.sqlite3")
    repo = tmp_path / "repo"
    (repo / "afo-manifests").mkdir(parents=True)
    oid, _ = store.submit(_env(repo), repo=repo, max_queued=10)
    limits = {
        "max_attempts": 4,
        "max_jobs": 3,
        "max_requests": 8,
        "max_tokens": 1000000,
        "max_tools": 12,
        "max_corrections": 1,
        "deadline": time.time() + 300,
    }
    ledger = MissionLedger(store)
    ledger.register("finite", "lineage", limits, "fixture-not-live", authorize=lambda *a: True)
    ledger.link("finite", oid)
    control = {
        "operations_intent": str(tmp_path / "private/intent.json"),
        "profile": "profile",
        "profile_sha256": "a" * 64,
        "source_revision": "b" * 40,
        "policy_sha256": "c" * 64,
        "mission": {"mission_id": "finite", "lineage": "lineage", "limits": limits},
    }
    job = {
        "order_id": oid,
        "mission_id": "finite",
        "profile": "profile",
        "profile_sha256": "a" * 64,
        "factory_revision": {"commit": "b" * 40, "dirty": False},
        "policy_sha256": "c" * 64,
        "native_context": {"FORGE_OPERATIONS_INTENT": control["operations_intent"], "FORGE_AFO_QUEUE_SCOPE": "line-local"},
    }
    return store, control, job


def test_actual_linked_scope_replays_through_readonly_authorization(bound):
    store, control, job = bound
    assert C.require_job_binding(job, control, store=store)
    assert C.require_job_binding(job, control)


@pytest.mark.parametrize("mutation", ["intent", "mission", "lineage", "limit", "scope"])
def test_other_running_intent_or_larger_mission_cannot_be_substituted(bound, mutation):
    store, control, job = bound
    control, job = copy.deepcopy(control), copy.deepcopy(job)
    if mutation == "intent":
        job["native_context"]["FORGE_OPERATIONS_INTENT"] = "/other/RUNNING.json"
    elif mutation == "mission":
        job["mission_id"] = "other-finite"
    elif mutation == "lineage":
        control["mission"]["lineage"] = "other-lineage"
    elif mutation == "limit":
        control["mission"]["limits"]["max_tokens"] += 1
    else:
        job["native_context"]["FORGE_AFO_QUEUE_SCOPE"] = "generic"
    with pytest.raises(Refused):
        C.require_job_binding(job, control, store=store)
