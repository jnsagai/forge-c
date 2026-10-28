"""Finite configured workflow capacity; no implicit expansion of existing missions."""

# ruff: noqa: F811
import copy
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient
from forge_factory import llm_gateway as G
from forge_factory.afo import authz, policy
from forge_factory.afo import mission_admin as M
from forge_factory.afo.durable import Refused
from forge_factory.common import canonical_json, sha256_bytes
from forge_factory.lrtx import profile, stack
from test_afo_local_autonomy import local  # noqa: F401
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_protocol import protocol  # noqa: F401
from test_da014_qualification_reservations import signed  # noqa: F401


@pytest.mark.parametrize("configured,expected", [(None, 600), (3600, 3600)])
def test_actual_default_and_routed_http_requests_receive_the_finite_timeout(tmp_path, monkeypatch, configured, expected):
    observed = []
    monkeypatch.delenv("FORGE_GATEWAY_MAX_INFLIGHT", raising=False)
    monkeypatch.delenv("FORGE_GATEWAY_REQUEST_TIMEOUT_S", raising=False)
    monkeypatch.setenv("FORGE_GATEWAY_ROUTES", json.dumps({"routed": "http://other"}))
    if configured is not None:
        monkeypatch.setenv("FORGE_GATEWAY_REQUEST_TIMEOUT_S", str(configured))

    def upstream(request):
        observed.append((request.url.host, request.extensions["timeout"]))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]})

    with TestClient(G.create_app("http://default", tmp_path / "meter", transport=httpx.MockTransport(upstream))) as client:
        for model in ["default", "routed"]:
            assert client.post("/v1/chat/completions", json={"model": model, "messages": []}).status_code == 200
    assert [host for host, _ in observed] == ["default", "other"]
    assert all(t["read"] == expected and t["connect"] == 10 for _, t in observed)


@pytest.mark.parametrize("invalid", [True, 0, -1, 3601, float("nan"), float("inf"), "3600"])
def test_invalid_timeout_is_refused_without_starting_a_provider(tmp_path, invalid):
    with pytest.raises(ValueError, match="GATEWAY_REQUEST_TIMEOUT_INVALID"):
        G.create_app("http://unused", tmp_path / "meter", request_timeout_s=invalid)
    selected = profile.load("local-rtx-v2-omniverse2-q38-quality")
    selected["gateway"]["request_timeout_s"] = invalid
    with pytest.raises(ValueError, match="GATEWAY_REQUEST_TIMEOUT_INVALID"):
        stack.gateway_timeout(selected)


def test_quality_profile_has_explicit_finite_timeout_and_old_profiles_keep_defaults():
    assert stack.gateway_timeout(profile.load("local-rtx-v2-omniverse2-q38-quality")) == 3600
    assert stack.gateway_timeout(profile.load("local-rtx-v2-omniverse2")) == 600


def test_timeout_keeps_uncertain_usage_and_capacity_without_replaying_generation(protocol, monkeypatch, tmp_path):
    from types import SimpleNamespace

    from forge_factory.afo import request_admission as A
    from forge_factory.afo.execution_lifecycle import Executions
    from forge_factory.lrtx import role_capability
    from test_da014_integration import ready

    p = protocol
    job = ready(p, monkeypatch)
    ex = Executions(p.store)
    ex.reserve(job["job_id"], "mission-test", job["nonce"])
    ex.dispatch_intent(job["job_id"])
    ex.adopt(job["job_id"], ["native-timeout"])
    monkeypatch.setattr(role_capability, "admit_job", lambda *a, **kw: {"qualified_fixture": True})
    reserve = A.reserve
    monkeypatch.setattr(A, "reserve", lambda store, binding, body: reserve(p.store, binding, body, eff=p.eff))
    monkeypatch.setattr(A, "start", lambda store, rec, body: p.ledger.start_request(rec["request_id"], authorize=lambda: True))
    monkeypatch.setattr(
        A, "reconcile", lambda store, rid, usage, completed=False: p.ledger.reconcile_request(rid, quiescent=completed)
    )
    calls = []

    def provider(request):
        calls.append(1)
        raise httpx.ReadTimeout("PRIVATE_TRANSPORT_ERROR", request=request)

    meter = tmp_path / "usage.jsonl"
    app = G.create_app("http://127.0.0.1:11455", meter, transport=httpx.MockTransport(provider), request_timeout_s=3600)
    body = {
        "model": "qwen-fixture",
        "messages": [{"role": "user", "content": "x"}],
        "max_tokens": 32,
        "forge_execution": {"job_id": job["job_id"], "nonce": job["nonce"], "request_id": "bounded-timeout"},
    }
    with TestClient(app) as client:
        response = client.post("/v1/chat/completions", json=body)
        assert response.status_code == 502
        assert response.json()["error"]["type"] == "PROVIDER_READ_TIMEOUT_OUTCOME_UNKNOWN"
        assert client.post("/v1/chat/completions", json=body).status_code == 429
    assert calls == [1]
    with p.store.tx() as c:
        rec = json.loads(
            c.execute("SELECT record FROM afo_request_ledger WHERE request_id=?", ("bounded-timeout",)).fetchone()[0]
        )
    assert rec["state"] == "UNKNOWN" and rec["reported_tokens"] is None and rec["charge"] > 0
    terminal = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "SUCCEEDED"}}})
    assert ex.reconcile(job["job_id"], terminal)["resource_lease"] == "HELD"
    row = json.loads(meter.read_text().splitlines()[0])
    assert row["basis"] == "unknown" and row["upstream_called"] is None
    assert "PRIVATE_TRANSPORT_ERROR" not in meter.read_text()


def setup_policy(p, **caps):
    value = copy.deepcopy(p.eff.policy)
    value["mode"] = "PILOT"
    value["budgets"].update(caps)
    sha = sha256_bytes(canonical_json(value))
    p.grant["policy_sha256"] = sha
    p.grant_path.write_text(json.dumps(p.grant))
    authz.sign(p.grant_path, p.key)
    return policy.Effective("PILOT", "PILOT", sha, value)


def document(p, *, requests=32, tools=32, mission="independent-workflow-capacity"):
    return {
        "mission_id": mission,
        "lineage": "unit-fixture:" + mission,
        "authorization_ref": "AUTH-QUAL",
        "request": {"model": "qwen3.6:35b-a3b"},
        "orders": [],
        "limits": {
            "max_attempts": 1,
            "max_jobs": 4,
            "max_requests": requests,
            "max_tokens": 32768,
            "max_tools": tools,
            "max_corrections": 1,
            "deadline": time.time() + 300,
        },
    }


def test_explicit_request_capacity_does_not_require_more_recovery_jobs(signed):
    p = signed
    eff = setup_policy(p, max_inference_requests_per_order=256, max_tool_calls_per_order=512)
    assert policy.schema_errors(eff.policy) == [] and policy.floor_violations(eff.policy) == []
    registered = M.register(p.store, document(p, requests=256, tools=512), eff)
    assert registered["limits"]["max_jobs"] == 4 and registered["limits"]["max_requests"] == 256


def test_defaults_and_existing_mission_limits_stay_frozen(signed):
    p = signed
    eff = setup_policy(p)
    original = document(p)
    before = M.register(p.store, original, eff)
    with pytest.raises(Refused, match="MISSION_LIMIT_EXCEEDS_CURRENT_AUTHORITY_OR_POLICY"):
        M.register(p.store, document(p, requests=33, mission="outside-default"), eff)
    larger = setup_policy(p, max_inference_requests_per_order=256, max_tool_calls_per_order=512)
    assert M.register(p.store, original, larger) == before
    with pytest.raises(Refused, match="MISSION_ALLOWANCE_RESET_FORBIDDEN"):
        M.register(p.store, {**original, "limits": {**original["limits"], "max_requests": 256}}, larger)


@pytest.mark.parametrize("bad", [True, 0, -1, 1.5, "256"])
def test_signed_policy_schema_rejects_unbounded_or_coerced_request_caps(signed, bad):
    value = copy.deepcopy(signed.eff.policy)
    value["budgets"]["max_inference_requests_per_order"] = bad
    assert policy.schema_errors(value)
