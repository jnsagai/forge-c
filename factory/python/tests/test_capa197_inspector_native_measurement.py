"""CAPA-197 (WO-F014-SWE1-GPIOL-20261107-L40J): every SWE.1 inspection was refused CAPABILITY_LIMIT before any model call.

The inspector packet carries the whole assembly (~241 kB). The trial profile measured only the author natively, so the
inspector request was bounded by bytes: 241654 + 34816 output tokens > the 262144 qualified context. The inspector is the
stack's primary llama-server model, so the gateway now measures it natively on its own route.
"""
import json

import httpx
from fastapi.testclient import TestClient
from forge_factory import llm_gateway as G
from forge_factory.afo import provider_recovery, queue, request_admission
from forge_factory.afo.diagnosis_packet import measure_request
from forge_factory.afo.durable import Refused
from forge_factory.lrtx import profile, stack
from forge_factory.lrtx import request_measurement as M

TRIAL_PROFILE = "local-rtx-v2-omniverse2-ornith-think-afo-finite-review-20261104"
INSPECTOR = "qwen3.8:27b-q8_0"
CONTEXT = 262144
OUTPUT_CAP = 2048 + 32768  # inspector answer reserve + the profile's extra output tokens


def inspector_body(size=241_000):
    return {"model": INSPECTOR, "max_tokens": OUTPUT_CAP, "reasoning_effort": "medium", "temperature": 0, "seed": 1,
            "messages": [{"role": "user", "content": "requirement assembly " * (size // 21)}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": "finding", "schema": {"type": "object"}}}}


def test_symptom_the_byte_bound_of_a_whole_assembly_inspection_exceeds_the_context():
    bound = measure_request(inspector_body())
    assert bound["method"] == "utf8_byte_upper_bound"
    assert bound["input_tokens"] + OUTPUT_CAP > CONTEXT


def test_the_trial_profile_measures_the_inspector_natively_on_a_route_the_stack_serves():
    prof = profile.load(TRIAL_PROFILE)
    policy = M.policy(prof)
    assert policy.get(INSPECTOR) == M.METHOD
    assert set(policy) <= set(stack.served_models(prof))  # the gateway refuses to start on an unrouted measured model
    assert prof["runtime"]["llama_server"]["model"] == INSPECTOR


def test_gateway_reserves_the_inspector_request_with_its_native_count(tmp_path, monkeypatch):
    prof = profile.load(TRIAL_PROFILE)
    monkeypatch.setenv("FORGE_GATEWAY_ROUTES", json.dumps({m: "http://native" for m in stack.served_models(prof)}))
    monkeypatch.setenv("FORGE_GATEWAY_REQUEST_MEASUREMENT", json.dumps(M.policy(prof)))
    monkeypatch.setattr(queue, "Store", lambda: object())
    monkeypatch.setattr(provider_recovery, "current_instance", lambda: None)
    seen, reserved = [], []

    def handle(request):
        seen.append(request.url.path)
        if request.url.path == "/apply-template":
            return httpx.Response(200, json={"prompt": "rendered"})
        assert request.url.path == "/tokenize", "measurement cannot request generation"
        n = len(json.loads(request.content)["content"]) // 4  # a native tokenizer: about 4 bytes per token
        return httpx.Response(200, json={"tokens": list(range(max(n, 1)))})

    def reserve(_store, _binding, _body, measurement=None):
        reserved.append(measurement)
        raise Refused("STOP_AFTER_RESERVE_FIXTURE")

    monkeypatch.setattr(request_admission, "reserve", reserve)
    request = inspector_body()
    request["forge_execution"] = {"job_id": "fixture", "nonce": "n", "request_id": "r", "role": "swe1-inspector"}
    with TestClient(G.create_app("http://ollama", tmp_path / "meter", transport=httpx.MockTransport(handle))) as client:
        client.post("/chat/completions", json=request)
    assert reserved and reserved[0]["native_measured"] is True and reserved[0]["method"] == M.METHOD
    assert reserved[0]["input_tokens"] + OUTPUT_CAP <= CONTEXT
    assert "/chat/completions" not in seen
