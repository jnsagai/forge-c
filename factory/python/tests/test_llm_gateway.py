"""FR-025 / T036: gateway never requests reasoning and strips any returned reasoning (mock upstream)."""
import json

import httpx
from fastapi.testclient import TestClient
from forge_factory import llm_gateway as gw

seen = []


def upstream(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    seen.append(body)
    if body.get("stream"):
        lines = [
            {"choices": [{"delta": {"reasoning": "SECRET-THOUGHT", "content": "Hel"}}]},
            {"choices": [{"delta": {"content": "lo"}}], "usage": {"prompt_tokens": 5, "completion_tokens": 2}},
        ]
        text = "".join("data: " + json.dumps(x) + "\n\n" for x in lines) + "data: [DONE]\n\n"
        return httpx.Response(200, text=text, headers={"content-type": "text/event-stream"})
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "OK",
                                                              "reasoning": "SECRET-THOUGHT"}}],
                                     "usage": {"prompt_tokens": 7, "completion_tokens": 1}})


def client(tmp_path):
    app = gw.create_app("http://up", tmp_path / "usage.jsonl", transport=httpx.MockTransport(upstream))
    return TestClient(app)


def test_request_forces_no_reasoning_and_response_stripped(tmp_path):
    c = client(tmp_path)
    r = c.post("/v1/chat/completions", json={"model": "qwen3:8b", "reasoning_effort": "high", "think": True,
                                             "messages": [{"role": "assistant", "content": "x",
                                                           "reasoning": "old"}]})
    assert r.status_code == 200
    assert "SECRET-THOUGHT" not in r.text and r.json()["choices"][0]["message"]["content"] == "OK"
    sent = seen[-1]
    assert sent["reasoning_effort"] == "none" and "think" not in sent
    assert "reasoning" not in sent["messages"][0]
    rec = json.loads((tmp_path / "usage.jsonl").read_text().splitlines()[-1])
    assert rec["basis"] == "reported" and rec["tokens_input"] == 7 and rec["reasoning_stripped"] is True


def test_stream_deltas_stripped(tmp_path):
    c = client(tmp_path)
    r = c.post("/v1/chat/completions", json={"model": "qwen3:8b", "stream": True, "messages": []})
    assert "SECRET-THOUGHT" not in r.text and "Hel" in r.text and "[DONE]" in r.text
    rec = json.loads((tmp_path / "usage.jsonl").read_text().splitlines()[-1])
    assert rec["tokens_output"] == 2


def test_unknown_usage_labelled_unknown(tmp_path):
    m = gw.Meter(tmp_path / "u.jsonl")
    m.record("m", None, False, 1.0)
    assert json.loads((tmp_path / "u.jsonl").read_text())["basis"] == "unknown"
