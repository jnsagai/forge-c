"""Native QM measurement is separate from provider response/mission accounting."""
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from forge_factory import llm_gateway as G
from forge_factory.afo import queue
from forge_factory.afo.durable import digest
from forge_factory.lrtx.request_measurement import METHOD

MODEL = "qwen3.8:27b-q8_0"


@pytest.mark.parametrize("stream", [False, True])
def test_standalone_full_effective_body_is_measured_without_mission_binding(tmp_path, monkeypatch, stream):
    monkeypatch.setenv("FORGE_GATEWAY_ROUTES", json.dumps({MODEL: "http://native"}))
    monkeypatch.setenv("FORGE_GATEWAY_REQUEST_MEASUREMENT", json.dumps({MODEL: METHOD}))
    monkeypatch.setenv("FORGE_GATEWAY_MEASURE_UNBOUND", "1")
    monkeypatch.setenv("FORGE_GATEWAY_NATIVE_CONTEXT_LIMIT", "65536")
    monkeypatch.setattr(queue, "default_path", lambda: tmp_path / "absent-db")
    seen = []

    def handle(request):
        data = json.loads(request.content)
        seen.append((request.url.path, data))
        if request.url.path == "/apply-template":
            return httpx.Response(200, json={"prompt": "entire native template"})
        if request.url.path == "/tokenize":
            return httpx.Response(200, json={"tokens": list(range(20))})
        assert request.url.path == "/v1/chat/completions"
        if stream:
            return httpx.Response(200, text='data: {"choices":[{"delta":{"content":"OK"},"finish_reason":"stop"}],'
                                           '"usage":{"prompt_tokens":20,"completion_tokens":1}}\n\ndata: [DONE]\n\n',
                                  headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 20, "completion_tokens": 1}})

    meter = tmp_path / "usage.jsonl"
    app = G.create_app(upstream="http://native", meter_path=meter, transport=httpx.MockTransport(handle))
    body = {"model": MODEL, "max_tokens": 4096, "stream": stream,
            "messages": [{"role": "user", "content": "private primary text Ω"}],
            "tools": [{"type": "function", "function": {"name": "write_file", "parameters": {"type": "object"}}}]}
    with TestClient(app) as client:
        assert client.post("/v1/chat/completions", json=body).status_code == 200
    assert [x[0] for x in seen] == ["/apply-template", "/tokenize", "/tokenize", "/tokenize",
                                   "/v1/chat/completions"]
    rec = json.loads((tmp_path / "request-measurements.jsonl").read_text())
    assert rec["measurement"]["sha256"] == digest(seen[-1][1])
    assert rec["fits"] and rec["output_reserve_tokens"] == 4096
    assert rec["context_limit_tokens"] == 65536 and rec["generation_dispatched"] is False
    assert "private primary text" not in json.dumps(rec) and "tools" not in json.dumps(rec)
    rows = [json.loads(line) for line in meter.read_text().splitlines()]
    assert len(rows) == 1 and rows[0]["tokens_output"] == 1


@pytest.mark.parametrize("ceiling,invalid,expected", [
    ("100", False, "NATIVE_CONTEXT_DOES_NOT_FIT"),
    ("65536", True, "NATIVE_MEASUREMENT_TEMPLATE_INVALID"),
])
def test_unmeasurable_or_overflow_never_dispatches_or_truncates(tmp_path, monkeypatch, ceiling, invalid, expected):
    monkeypatch.setenv("FORGE_GATEWAY_ROUTES", json.dumps({MODEL: "http://native"}))
    monkeypatch.setenv("FORGE_GATEWAY_REQUEST_MEASUREMENT", json.dumps({MODEL: METHOD}))
    monkeypatch.setenv("FORGE_GATEWAY_MEASURE_UNBOUND", "1")
    monkeypatch.setenv("FORGE_GATEWAY_NATIVE_CONTEXT_LIMIT", ceiling)
    monkeypatch.setattr(queue, "default_path", lambda: tmp_path / "absent-db")
    seen = []

    def handle(request):
        seen.append(request.url.path)
        assert request.url.path != "/v1/chat/completions", "must refuse before inference"
        if request.url.path == "/apply-template":
            return httpx.Response(200, json={} if invalid else {"prompt": "complete"})
        return httpx.Response(200, json={"tokens": list(range(20))})

    app = G.create_app(upstream="http://native", meter_path=tmp_path / "usage.jsonl",
                       transport=httpx.MockTransport(handle))
    with TestClient(app) as client:
        r = client.post("/v1/chat/completions", json={"model": MODEL, "max_tokens": 4096,
                        "messages": [{"role": "user", "content": "retain this entire evidence"}]})
    assert r.status_code == 429 and r.json()["error"]["type"] == expected
    assert seen and all(p != "/v1/chat/completions" for p in seen)

