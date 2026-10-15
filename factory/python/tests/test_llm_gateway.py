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
