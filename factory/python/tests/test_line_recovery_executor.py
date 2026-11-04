"""Lifecycle controls only, zero inference; real M3 provenance/signatures are tested separately."""
import json
import time
from types import SimpleNamespace

import pytest
from forge_factory.afo import line_recovery as R
from forge_factory.afo import local_agent as L
from forge_factory.afo.queue import QueueError
from test_afo_local_autonomy import client, local, order  # noqa: F401

BASE_AUTHORIZED = L.authorized


@pytest.fixture
def bound(local, monkeypatch):  # noqa: F811
    from forge_factory import development_execution

    monkeypatch.setattr(development_execution, "selected", lambda _: True)
    state = {"status": "BOUND_CONTEXT_ONLY_NO_DISPATCH", "generation": 1}
    monkeypatch.setattr(R, "context", lambda *args: dict(state))
    s, o, b, eff, ws, case = local
    from forge_factory.afo import planner
    from forge_factory.afo.mission_ledger import MissionLedger

    ledger = MissionLedger(s)
    ledger.register("line-controller-fixture", "line-fixture", {
        "max_attempts": 0, "max_jobs": 2, "max_requests": 1, "max_tokens": 32768,
        "max_tools": 0, "max_corrections": 0, "deadline": time.time() + 600,
    }, "FIXTURE-NOT-PRODUCTION", authorize=lambda *a: True)
    ledger.link("line-controller-fixture", o["order_id"])
    case = planner.case(b, ws, {"attempts": 0}, mission_id="line-controller-fixture")
    origin = {"campaign_path": "/owner-approved/campaign.yaml"}
    return s, o, b, eff, ws, case, origin, state


def prepare(bound, **kw):
    s, o, b, eff, ws, case, origin, _ = bound
    return L.prepare(s, o, b["attempt_id"], "afo-recovery-planner", case, ws, eff, line_origin=origin, **kw)


def test_only_reverified_line_origin_lifts_development_deferral(bound):
    s, o, b, eff, ws, case, _, _ = bound
    with pytest.raises(QueueError, match="DEFERRED_BY_DEVELOPMENT_POLICY"):
        L.prepare(s, o, b["attempt_id"], "afo-recovery-planner", case, ws, eff)
    job = prepare(bound)
    assert job["state"] == "PREPARED" and job["line_context_sha256"]
    assert prepare(bound) == job


def test_origin_or_case_cannot_be_rebound_or_downgraded(bound):
    s, o, b, eff, ws, case, _, state = bound
    prepare(bound)
    state["generation"] = 2
    with pytest.raises(QueueError, match="LOCAL_AGENT_JOB_REBOUND"):
        prepare(bound)
    document = json.loads(case.read_text())
    document["bundle"]["attempt_id"] = "foreign"
    case.chmod(0o600)
    case.write_text(json.dumps(document))
    with pytest.raises(QueueError, match="LINE_RECOVERY_CASE_BINDING_MISMATCH"):
        prepare(bound)


def test_line_binding_does_not_bypass_existing_role_enable_or_capacity(bound):
    s, o, b, eff, ws, case, _, _ = bound
    eff.policy["engineering"]["enable_recovery_planner"] = False
    with pytest.raises(QueueError, match="LOCAL_AGENT_NOT_AUTHORIZED"):
        prepare(bound)
    assert L.records(s, o["order_id"]) == []


def test_current_line_binding_is_required_in_addition_to_generic_authority(bound, monkeypatch):
    from forge_factory.afo import authority

    job = prepare(bound)
    s, o, _, eff, _, _, _, state = bound
    monkeypatch.setattr(authority, "decide", lambda *a, **kw: SimpleNamespace(allow=True))
    monkeypatch.setattr(L, "authorized", BASE_AUTHORIZED)
    assert L.authorized_job(o, eff, job)
    state["generation"] = 2
    assert not L.authorized_job(o, eff, job)
    monkeypatch.setattr(authority, "decide", lambda *a, **kw: SimpleNamespace(allow=False))
    state["generation"] = 1
    assert not L.authorized_job(o, eff, job)


def test_revocation_before_dispatch_never_calls_fabro_and_preserves_reservation(bound, monkeypatch):
    from forge_factory.afo import authority

    s, o, _, eff, _, _, _, state = bound
    job = prepare(bound)
    monkeypatch.setattr(authority, "decide", lambda *a, **kw: SimpleNamespace(allow=True))
    monkeypatch.setattr(L, "authorized", BASE_AUTHORIZED)
    state["generation"] = 2
    result = L.poll(s, o, job, eff, client=client(), launch_fn=lambda _: pytest.fail("revoked job launched"))
    assert result["state"] == "REVOKED" and result["reserved_tokens"] == job["reserved_tokens"]


def test_binding_refusal_is_checked_before_native_launch_even_after_prepare(bound, monkeypatch):
    job = prepare(bound)
    monkeypatch.setattr(R, "valid_job", lambda _: False)
    with pytest.raises(L.LaunchNotStarted, match="LINE_RECOVERY_AUTHORITY_OR_PROVENANCE_CHANGED"):
        L.launch(job)


def test_line_origin_never_dispatches_the_legacy_unqualified_agent_protocol(bound):
    s, o, _, _, _, case, _, _ = bound
    document = json.loads(case.read_text())
    del document["packet_ref"]
    case.chmod(0o600)
    case.write_text(json.dumps(document))
    with pytest.raises(QueueError, match="DURABLE_PROTOCOL_REQUIRED"):
        prepare(bound)
    assert L.records(s, o["order_id"]) == []


def test_default_line_dispatch_uses_existing_host_interlocks_adapter(bound, monkeypatch):
    from forge_factory.afo import line_recovery_runtime

    s, o, _, eff, _, _, _, _ = bound
    job = prepare(bound)
    calls = []
    monkeypatch.setattr(line_recovery_runtime, "launch", lambda j: calls.append(j["job_id"]) or "RUN-LOCKED")
    result = L.poll(s, o, job, eff, client=client())
    assert result["state"] == "RUNNING" and result["run_id"] == "RUN-LOCKED"
    assert calls == [job["job_id"]]


def test_explicit_controller_role_inputs_are_bound_without_source_inference(bound, monkeypatch):
    from forge_factory.afo import line_recovery_control as control
    from forge_factory.lrtx.profile import load

    store, _, _, eff, _, _, _, context = bound
    profile = load("local-rtx-v2-omniverse2")
    context["source_revision"] = "1" * 40
    authority = {"path": "/controller/frozen.json", "sha256": "f" * 64}
    value = {"profile": profile["id"], "profile_sha256": profile["_sha256"], "source_revision": "1" * 40,
             "role_capabilities": {}, "product_role_trial": None}
    from forge_factory.afo import operations
    from forge_factory.afo.mission_ledger import MissionLedger

    mission = MissionLedger(store).snapshot("line-controller-fixture")
    value.update(operations_intent="/controller/frozen-intent.json", policy_sha256=eff.sha256,
                 mission={key: mission[key] for key in ("mission_id", "lineage", "limits")})
    monkeypatch.setenv("FORGE_OPERATIONS_INTENT", value["operations_intent"])
    monkeypatch.setattr(operations, "configured", lambda: False)  # metadata fixture; no live intent authority inferred
    seen = []
    monkeypatch.setattr(control, "configuration", lambda ref, eff, **kw: seen.append(ref) or value)
    job = prepare(bound, line_role_authority_ref=authority)
    assert job["line_role_authority_ref"] == authority and job["role_capabilities"] == {}
    assert seen == [authority]  # signed controller inputs cannot invent a capability receipt
    assert prepare(bound, line_role_authority_ref=authority) == job
    with pytest.raises(QueueError, match="LOCAL_AGENT_JOB_REBOUND"):
        prepare(bound, line_role_authority_ref=dict(authority, sha256="e" * 64))


def test_controller_role_authority_is_rechecked_before_dispatch(bound, monkeypatch):
    from forge_factory.afo import line_recovery_control as control
    from forge_factory.afo.durable import Refused

    job = prepare(bound)
    job["line_role_authority_ref"] = {"path": "/controller/frozen.json", "sha256": "f" * 64}
    def refuse(*args, **kwargs):
        raise Refused("AUTH_REVOKED")
    monkeypatch.setattr(control, "configuration", refuse)
    assert not L.authorized_job(bound[1], bound[3], job)
