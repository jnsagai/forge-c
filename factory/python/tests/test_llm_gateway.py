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
    assert rec["tokens_output"] == 2 and rec["content_chars"] == 5 and rec["dropped_output"] is False


def test_dropped_output_flagged_without_logging_content(tmp_path):
    m = gw.Meter(tmp_path / "u.jsonl")
    m.record("m", {"prompt_tokens": 9000, "completion_tokens": 1905}, False, 1.0,
             {"content_chars": 0, "tool_calls": 0, "finish_reason": "stop"})
    m.record("m", {"prompt_tokens": 9000, "completion_tokens": 90}, False, 1.0,
             {"content_chars": 0, "tool_calls": 1, "finish_reason": "tool_calls"})
    a, b = [json.loads(x) for x in (tmp_path / "u.jsonl").read_text().splitlines()]
    assert a["dropped_output"] is True and b["dropped_output"] is False and "content" not in a


def test_dropped_upstream_answer_retried_bounded_and_metered(tmp_path):
    calls = {"n": 0}

    def flaky(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        body = json.loads(request.content)
        empty = calls["n"] == 1
        if body.get("stream"):
            delta = {} if empty else {"tool_calls": [{"index": 0, "function": {"name": "write_file", "arguments": "{}"}}]}
            text = "data: " + json.dumps({"choices": [{"delta": delta, "finish_reason": "stop"}],
                                          "usage": {"prompt_tokens": 9, "completion_tokens": 400}}) + "\n\ndata: [DONE]\n\n"
            return httpx.Response(200, text=text, headers={"content-type": "text/event-stream"})
        msg = {"role": "assistant", "content": ""} if empty else {"role": "assistant", "content": "ok"}
        return httpx.Response(200, json={"choices": [{"message": msg, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 9, "completion_tokens": 400}})

    for stream in (False, True):
        calls["n"] = 0
        meter = tmp_path / f"u{stream}.jsonl"
        c = TestClient(gw.create_app("http://up", meter, transport=httpx.MockTransport(flaky)))
        r = c.post("/v1/chat/completions", json={"model": "qwen3:8b", "stream": stream, "messages": []})
        assert r.status_code == 200 and calls["n"] == 2 and ("write_file" in r.text or "ok" in r.text)
        recs = [json.loads(x) for x in meter.read_text().splitlines()]
        assert [x["attempt"] for x in recs] == [0, 1] and [x["dropped_output"] for x in recs] == [True, False]

    def always_empty(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"choices": [{"message": {"content": ""}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 9, "completion_tokens": 400}})

    calls["n"] = 0
    c = TestClient(gw.create_app("http://up", tmp_path / "e.jsonl", transport=httpx.MockTransport(always_empty)))
    assert c.post("/v1/chat/completions", json={"model": "m", "messages": []}).status_code == 200
    assert calls["n"] == 1 + gw.DROP_RETRIES  # bounded


def test_paid_upstream_auth_forwarded_cache_metered_and_cost_capped(tmp_path, monkeypatch):
    seen_auth = []

    def paid(request: httpx.Request) -> httpx.Response:
        seen_auth.append(request.headers.get("authorization"))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                                         "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 10,
                                                   "prompt_cache_hit_tokens": 800_000}})

    monkeypatch.setattr(gw, "PRICES", {"miss": 0.14, "hit": 0.0028, "out": 0.28})
    monkeypatch.setattr(gw, "COST_CAP_USD", 0.03)
    meter = tmp_path / "paid.jsonl"
    c = TestClient(gw.create_app("http://up", meter, transport=httpx.MockTransport(paid)))
    r = c.post("/chat/completions", json={"model": "deepseek-flash", "messages": []},
               headers={"Authorization": "Bearer K"})
    assert r.status_code == 200 and seen_auth == ["Bearer K"]
    rec = json.loads(meter.read_text())
    assert rec["tokens_cache_hit"] == 800_000 and "Bearer" not in meter.read_text()  # credential never metered
    assert abs(gw.spent_usd(meter) - (0.2 * 0.14 + 0.8 * 0.0028 + 10 * 0.28 / 1e6)) < 1e-9
    blocked = c.post("/v1/chat/completions", json={"model": "deepseek-flash", "messages": []})
    assert blocked.status_code == 429 and "cost cap" in blocked.text and len(seen_auth) == 1  # cap stops spend


def test_unknown_usage_labelled_unknown(tmp_path):
    m = gw.Meter(tmp_path / "u.jsonl")
    m.record("m", None, False, 1.0)
    assert json.loads((tmp_path / "u.jsonl").read_text())["basis"] == "unknown"


def test_tools_scoped_to_role_detected_from_skill_instruction():
    names = ["shell", "read_file", "write_file", "use_skill", "mcp__forge_build_mcp__compile",
             "mcp__forge_evidence_mcp__check_inspection", "web_fetch", "spawn_agent"]
    tools = [{"type": "function", "function": {"name": n}} for n in names]
    body = {"messages": [{"role": "user", "content": "Call use_skill with skill_name swe3-inspector and follow it."}],
            "tools": tools}
    kept = {t["function"]["name"] for t in gw.sanitize_request(body)["tools"]}
    assert kept == {"read_file", "use_skill", "mcp__forge_evidence_mcp__check_inspection"}
    body["messages"][0]["content"] = "Call use_skill with skill_name swe3-author"
    kept = {t["function"]["name"] for t in gw.sanitize_request(body)["tools"]}
    assert {"write_file", "mcp__forge_build_mcp__compile"} <= kept and "shell" not in kept
    body["messages"][0]["content"] = "no role here"
    assert len(gw.sanitize_request(body)["tools"]) == len(names)  # unknown role: unchanged, hook still enforces


def test_a_profile_named_model_reasons_at_its_fixed_effort_and_its_reasoning_is_still_stripped(tmp_path, monkeypatch):
    """Owner decision 2026-10-22 (ADR-0015 addendum): a model the profile names may reason at the profile's effort,
    with extra output tokens for it; every other model stays at 'none'; no reasoning text reaches the caller or the
    meter, in plain or streamed answers, for either."""
    monkeypatch.setenv("FORGE_GATEWAY_REASONING", json.dumps({"gpt-oss:20b": {"effort": "low",
                                                                             "extra_output_tokens": 4096}}))
    c = client(tmp_path)
    for stream in (False, True):
        r = c.post("/v1/chat/completions", json={"model": "gpt-oss:20b", "stream": stream, "max_tokens": 1000,
                                                 "reasoning_effort": "high", "messages": []})
        assert r.status_code == 200 and "SECRET-THOUGHT" not in r.text
        assert seen[-1]["reasoning_effort"] == "low" and seen[-1]["max_tokens"] == 5096  # caller's 'high' ignored
    r = c.post("/v1/chat/completions", json={"model": "qwen3:8b", "max_tokens": 1000, "messages": []})
    assert seen[-1]["reasoning_effort"] == "none" and seen[-1]["max_tokens"] == 1000
    assert "SECRET-THOUGHT" not in (tmp_path / "usage.jsonl").read_text()


def test_without_a_valid_policy_every_model_reasons_none(monkeypatch):
    for env in (None, "not json", '{"gpt-oss:20b": {"effort": "max"}}', '["gpt-oss:20b"]'):
        if env is None:
            monkeypatch.delenv("FORGE_GATEWAY_REASONING", raising=False)
        else:
            monkeypatch.setenv("FORGE_GATEWAY_REASONING", env)
        out = gw.sanitize_request({"model": "gpt-oss:20b", "max_tokens": 10, "messages": []})
        assert out["reasoning_effort"] == "none" and out["max_tokens"] == 10, env


def test_the_stack_passes_only_the_profile_policy():
    from forge_factory.lrtx.profile import load
    from forge_factory.lrtx.stack import gateway_reasoning

    assert json.loads(gateway_reasoning(load("local-rtx-v2"))) == {"gpt-oss:20b": {"effort": "low",
                                                                                   "extra_output_tokens": 4096}}
    assert gateway_reasoning(load("local-rtx-v1")) == "{}"  # the v1 line is unchanged
