"""CAPA-052 (h001, OD-2026-10-20-03): Fabro's server-side run-title generation called the suspended DeepSeek through
the forge gateway once per run (06:53:12Z, outside the workflow graph that CAPA-051 guards). The gateway now refuses
every request to a suspended provider's upstream before any network call, and records the refusal."""
import json

import httpx
from fastapi.testclient import TestClient
from forge_factory import llm_gateway as gw
from forge_factory import workorder as W
from forge_factory.reliability.metrics import cloud_tokens

CALLS = []


def upstream(request: httpx.Request) -> httpx.Response:
    CALLS.append(request.url.path)
    return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "title"}}],
                                     "usage": {"prompt_tokens": 3, "completion_tokens": 1}})


def _client(tmp_path, up="https://api.deepseek.com"):
    return TestClient(gw.create_app(up, tmp_path / "usage.jsonl", transport=httpx.MockTransport(upstream)))


def test_capa052_suspended_upstream_is_never_called(tmp_path):
    CALLS.clear()
    c = _client(tmp_path)
    r = c.post("/v1/chat/completions", json={"model": "deepseek-flash", "messages": [{"role": "user", "content": "x"}],
                                             "response_format": {"type": "json_schema"}})
    assert r.status_code == 503 and r.json()["error"]["type"] == "model_suspended"
    assert "OD-2026-10-20-03" in r.json()["error"]["message"]
    assert c.get("/v1/models").status_code == 503
    assert CALLS == []
    recs = [json.loads(x) for x in (tmp_path / "usage.jsonl").read_text().splitlines()]
    assert len(recs) == 2 and all(x["upstream_called"] is False and x["refused"].startswith("MODEL_SUSPENDED:deepseek")
                                  for x in recs)
    assert gw.spent_usd(tmp_path / "usage.jsonl") == 0.0
    a = {"started": "2000-01-01", "finished": "2999-01-01"}
    assert cloud_tokens(a, tmp_path / "usage.jsonl") == {"status": "UNKNOWN"}  # refusals are not calls


def test_capa052_other_upstreams_and_lifted_suspension_pass_through(tmp_path, monkeypatch):
    CALLS.clear()
    r = _client(tmp_path, "http://127.0.0.1:11435").post(
        "/v1/chat/completions", json={"model": "qwen3:8b", "messages": [{"role": "user", "content": "x"}]})
    assert r.status_code == 200 and CALLS == ["/v1/chat/completions"]
    p = tmp_path / "s.yaml"
    p.write_text("schema_version: '1.0'\nsuspended: []\n")
    monkeypatch.setattr(W, "MODEL_SUSPENSIONS", p)  # the owner lifts the suspension: read per request, no restart
    r = _client(tmp_path / "b").post("/v1/chat/completions",
                                     json={"model": "deepseek-flash", "messages": [{"role": "user", "content": "x"}]})
    assert r.status_code == 200 and len(CALLS) == 2
