"""Complete, model-free native measurement; context gates still decide admission."""
import asyncio
import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from forge_factory import llm_gateway as G
from forge_factory import workorder
from forge_factory.afo import local_agent as L
from forge_factory.afo import policy as P
from forge_factory.afo import provider_recovery, queue, request_admission
from forge_factory.afo.durable import Refused, canonical, digest
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.lrtx import profile
from forge_factory.lrtx import request_measurement as M
from forge_factory.lrtx import role_capability as C
from forge_factory.workflow import builder
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_integration import ready
from test_da014_protocol import protocol  # noqa: F401

MODEL = "qwen3.8:27b-q8_0"
PROFILE = "local-rtx-v2-omniverse2-q38-aspice-medium-author-xhigh-inspector"


def body():
    return {"model": MODEL, "max_tokens": 2048, "reasoning_effort": "xhigh",
            "messages": [{"role": "user", "content": "Complete primary evidence: Ω" * 1600}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "answer", "schema": {
                "type": "object", "properties": {"finding": {"enum": ["full-evidence-tail"]}}}}}}


def transport(seen, *, invalid=None):
    def handle(request):
        data = json.loads(request.content)
        seen.append((request.url.path, data))
        if invalid == "http":
            return httpx.Response(503, json={"error": "not-ready"})
        if request.url.path == "/apply-template":
            return httpx.Response(200, json={"prompt": "rendered-complete-native-template"} if invalid != "template" else {})
        assert request.url.path == "/tokenize", "measurement cannot request generation"
        assert data["add_special"] is True
        return httpx.Response(200, json={"tokens": [True]} if invalid == "tokens" else {"tokens": list(range(20))})
    return httpx.MockTransport(handle)


def test_complete_canonical_body_template_and_all_non_message_controls_are_measured():
    seen = []
    request = body()
    original = copy.deepcopy(request)

    async def run():
        async with httpx.AsyncClient(base_url="http://native", transport=transport(seen)) as client:
            return await M.measure(client, request)

    result = asyncio.run(run())
    assert request == original and result["sha256"] == digest(request)
    assert result["serialized_bytes"] == len(canonical(request))
    assert result["input_tokens"] == max(20, 20 + 20) + 128
    assert result["method"] == M.METHOD and result["native_measured"] is True
    assert seen[0] == ("/apply-template", original)
    assert seen[1][1]["content"] == canonical(original).decode()
    assert json.loads(seen[3][1]["content"]) == {k: v for k, v in original.items() if k != "messages"}
    assert "messages" not in json.dumps(result) and "Complete primary evidence" not in json.dumps(result)


@pytest.mark.parametrize("invalid,code", [("http", "UNAVAILABLE"), ("template", "TEMPLATE_INVALID"),
                                          ("tokens", "TOKENS_INVALID")])
def test_native_transport_or_protocol_failure_refuses(invalid, code):
    async def run():
        async with httpx.AsyncClient(base_url="http://native", transport=transport([], invalid=invalid)) as client:
            await M.measure(client, body())
    with pytest.raises(Refused, match="NATIVE_MEASUREMENT_" + code):
        asyncio.run(run())


@pytest.mark.parametrize("configured", [[MODEL], {"undeclared": M.METHOD}, {MODEL: "estimate"}])
def test_invalid_measurement_policy_cannot_defer_context(configured):
    selected = profile.load(PROFILE)
    selected["gateway"]["request_measurement"] = configured
    with pytest.raises(ValueError, match="PROFILE_REQUEST_MEASUREMENT_INVALID"):
        M.policy(selected)


def test_gateway_measures_effective_role_body_before_reservation_with_no_generation(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_GATEWAY_ROUTES", json.dumps({MODEL: "http://native"}))
    monkeypatch.setenv("FORGE_GATEWAY_REQUEST_MEASUREMENT", json.dumps({MODEL: M.METHOD}))
    monkeypatch.setenv("FORGE_GATEWAY_REASONING", json.dumps(profile.load(PROFILE)["gateway"]["reasoning"]))
    monkeypatch.setattr(queue, "Store", lambda: object())
    monkeypatch.setattr(provider_recovery, "current_instance", lambda: None)
    seen, reservations = [], []

    def reserve(store, binding, request, *, measurement):
        reservations.append((request, measurement))
        assert request["reasoning_effort"] == "xhigh" and request["max_tokens"] == 34816
        assert measurement["sha256"] == digest(request)
        assert measurement["provider_instance_sha256"] == digest(None)
        raise Refused("MEASUREMENT_PROBE_NO_GENERATION")

    monkeypatch.setattr(request_admission, "reserve", reserve)
    request = body()
    request["reasoning_effort"] = "none"
    request["forge_execution"] = {"job_id": "fixture", "nonce": "n", "request_id": "r", "role": "swe1-inspector"}
    with TestClient(G.create_app("http://ollama", tmp_path / "meter", transport=transport(seen))) as client:
        response = client.post("/chat/completions", json=request)
    assert response.status_code == 429 and response.json()["error"]["type"] == "MEASUREMENT_PROBE_NO_GENERATION"
    assert len(reservations) == 1 and len(seen) == 4
    assert all(p != "/chat/completions" for p, _ in seen)
    assert "forge_execution" not in seen[0][1]


def test_changed_provider_during_measurement_refuses_before_reservation(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_GATEWAY_ROUTES", json.dumps({MODEL: "http://native"}))
    monkeypatch.setenv("FORGE_GATEWAY_REQUEST_MEASUREMENT", json.dumps({MODEL: M.METHOD}))
    monkeypatch.setattr(queue, "Store", lambda: object())
    states = iter([None, {"changed": True}])
    monkeypatch.setattr(provider_recovery, "current_instance", lambda: next(states))
    monkeypatch.setattr(request_admission, "reserve", lambda *a, **kw: pytest.fail("changed provider cannot reserve"))
    request = body()
    request["forge_execution"] = {"job_id": "fixture", "nonce": "n", "request_id": "r", "role": "swe1-author"}
    with TestClient(G.create_app("http://ollama", tmp_path / "meter", transport=transport([]))) as client:
        response = client.post("/chat/completions", json=request)
    assert response.status_code == 429 and response.json()["error"]["type"] == "NATIVE_MEASUREMENT_PROVIDER_CHANGED"


def test_profile_uses_short_checkpointed_visits_not_the_1800_second_watchdog_window():
    selected = profile.load(PROFILE)
    structured = workorder.local_profile_structured({"id": PROFILE}, {"layer": "LL"}, MODEL)
    assert selected["version"] == 2 and structured["visit_time_s"] == 600
    graph, _ = builder.build("WO-VISIT-CONTEXT", layer="LL", structured=structured)
    assert "--time-budget 600" in graph and "--time-budget 21600" not in graph
    assert "continue-check" in graph and "--resume" in graph
    assert M.policy(selected) == {MODEL: M.METHOD}


@pytest.mark.parametrize("context_tokens", [188, 187])
def test_real_role_context_and_mission_admission_use_native_count_with_exact_boundary(protocol, monkeypatch, context_tokens):  # noqa: F811
    p = protocol
    job = ready(p, monkeypatch)
    job.update(role=None, model_digest="a" * 64, precision="Q8_0", semantic_obligations=1,
               work_class="PRODUCT_DIAGNOSIS", factory_revision={"commit": "b" * 40})
    identity = dict(role="swe2-author", model_digest=job["model_digest"], precision="Q8_0", reasoning="none",
                    schema_mode="unconstrained", adapter_revision="b" * 40, context_tokens=context_tokens,
                    sampling={"temperature": 0}, task_class="PRODUCT_DIAGNOSIS")
    job["role_capabilities"] = {"swe2-author": {"identity": identity, "ref": {}}}
    L.save(p.store, job)
    monkeypatch.setattr(P, "load", lambda **kw: p.eff)
    monkeypatch.setattr(C, "require", lambda *a, **kw: {"qualified_fixture": True})
    monkeypatch.setattr(provider_recovery, "current_instance", lambda: None)
    Executions(p.store).reserve(job["job_id"], job["mission_id"], job["nonce"])
    request = {"model": job["model"], "temperature": 0, "max_tokens": 20,
               "messages": [{"role": "user", "content": "Complete evidence\n" * 2000}]}

    async def run():
        async with httpx.AsyncClient(base_url="http://native", transport=transport([])) as client:
            return await M.measure(client, request)

    measured = asyncio.run(run())
    measured["provider_instance_sha256"] = digest(None)
    assert measured["input_tokens"] == 168 and measured["serialized_bytes"] > job["reserved_tokens"]
    binding = {"job_id": job["job_id"], "nonce": job["nonce"], "request_id": "native-measurement",
               "role": "swe2-author"}
    before = p.ledger.snapshot(job["mission_id"])
    with pytest.raises(Refused, match="REQUEST_MEASUREMENT_BINDING_INVALID"):
        request_admission.reserve(p.store, binding, request, eff=p.eff, measurement={**measured, "sha256": "f" * 64})
    with pytest.raises(Refused, match="NATIVE_MEASUREMENT_PROVIDER_CHANGED"):
        request_admission.reserve(p.store, binding, request, eff=p.eff,
                                  measurement={**measured, "provider_instance_sha256": "f" * 64})
    assert p.ledger.snapshot(job["mission_id"]) == before
    if context_tokens == 187:
        with pytest.raises(Refused, match="CAPABILITY_LIMIT"):
            request_admission.reserve(p.store, binding, request, eff=p.eff, measurement=measured)
        assert p.ledger.snapshot(job["mission_id"]) == before
    else:
        rec = request_admission.reserve(p.store, binding, request, eff=p.eff, measurement=measured)
        assert rec["state"] == "RESERVED"
        evidence = Executions(p.store)._evidence(job["job_id"], "REQUEST_METADATA:" + rec["request_id"])
        assert evidence["measurement"] == measured
        assert p.ledger.snapshot(job["mission_id"])["requests"] == before["requests"] + 1
