"""Owner 2026-11-02: the Claude/Codex comparison line answers the same structured tasks through a bridge behind the
unchanged gateway. Fake backends only (no paid call, no CLI): SSE shape the structured runner reads, schema handling,
Codex strict-schema rule, metering without prompts, unix-socket gateway route."""
import json
import threading
from types import SimpleNamespace

import httpx
import pytest
from forge_factory.lrtx import cloud_bridge as CB

SCHEMA = {"type": "object", "additionalProperties": False, "required": ["code"],
          "properties": {"code": {"type": "string", "minLength": 3}}}
LOOSE = {"type": "object", "properties": {"code": {"type": "string"}, "note": {"type": "string"}}, "required": ["code"]}


def _body(schema=SCHEMA, model="claude-opus-5-5"):
    return {"model": model, "stream": True, "max_tokens": 1000, "stream_options": {"include_usage": True},
            "messages": [{"role": "system", "content": "SECRET-SYSTEM"}, {"role": "user", "content": "SECRET-USER"}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "packet_output", "strict": True,
                                                                        "schema": schema}}}


class FakeStream:
    def __init__(self, msg):
        self.msg = msg

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def get_final_message(self):
        return self.msg


class FakeClient:
    def __init__(self, fail_schema=False):
        self.calls, self.fail_schema = [], fail_schema
        self.messages = SimpleNamespace(stream=self.stream)

    def stream(self, **kw):
        self.calls.append(kw)
        if self.fail_schema and "format" in kw["output_config"]:
            raise type("BadRequest", (Exception,), {"status_code": 400})("schema keyword not supported")
        usage = SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=5, cache_creation_input_tokens=0)
        return FakeStream(SimpleNamespace(content=[SimpleNamespace(type="text", text='{"code": "abc"}')],
                                          stop_reason="end_turn", usage=usage))


def test_anthropic_backend_maps_the_runner_request():
    fc = FakeClient()
    res = CB.AnthropicBackend("k", client=fc).answer(_body(), {"backend": "anthropic", "extra_output_tokens": 8000,
                                                               "effort": "medium"})
    kw = fc.calls[0]
    assert kw["model"] == "claude-opus-5-5" and kw["max_tokens"] == 9000 and kw["system"] == "SECRET-SYSTEM"
    assert kw["messages"] == [{"role": "user", "content": [{"type": "text", "text": "SECRET-USER"}]}]
    assert kw["output_config"] == {"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}}
    assert res["text"] == '{"code": "abc"}' and res["finish"] == "stop" and res["usage"]["prompt_tokens"] == 105


def test_a_rejected_schema_falls_back_to_a_plain_json_instruction():
    fc = FakeClient(fail_schema=True)
    res = CB.AnthropicBackend("k", client=fc).answer(_body(), {"backend": "anthropic"})
    assert res["schema_mode"] == "prompt_schema_fallback" and "format" not in fc.calls[-1]["output_config"]
    assert '"minLength": 3' in fc.calls[-1]["system"]


def test_codex_uses_output_schema_only_for_strict_schemas(tmp_path):
    seen = []

    def run(argv, **kw):
        seen.append((argv, kw))
        out = argv[argv.index("-o") + 1]
        with open(out, "w") as f:
            f.write('{"code": "xyz"}')
        ev = {"type": "turn.completed", "usage": {"input_tokens": 1200, "cached_input_tokens": 900, "output_tokens": 34,
                                                  "reasoning_output_tokens": 0}}
        return SimpleNamespace(returncode=0, stdout='{"type": "thread.started"}\n' + json.dumps(ev) + "\n", stderr="")

    be = CB.CodexBackend(str(tmp_path), run=run)
    r1 = be.answer(_body(model="codex"), {"backend": "codex", "model": "m1"})
    r2 = be.answer(_body(LOOSE, model="codex"), {"backend": "codex"})
    a1, k1 = seen[0]
    assert "--output-schema" in a1 and r1["schema_mode"] == "output_schema" and r1["usage"]["total_tokens"] == 1234 and r1["usage"]["cached_prompt_tokens"] == 900
    assert "--sandbox" in a1 and a1[a1.index("--sandbox") + 1] == "read-only" and "--ephemeral" in a1
    assert ["-m", "m1"] == a1[a1.index("-m"):a1.index("-m") + 2] and k1["env"]["CODEX_HOME"] == str(tmp_path)
    assert "--output-schema" not in seen[1][0] and r2["schema_mode"] == "prompt_schema"
    assert CB.strict_ok(SCHEMA) and not CB.strict_ok(LOOSE)


def test_the_bridge_answers_over_its_socket_and_meters_without_prompts(tmp_path):
    meter = tmp_path / "meter.jsonl"
    (tmp_path / "mode.json").write_text('{"mode": "api"}')  # the API only when a mode file says so
    bridge = CB.Bridge({"claude-opus-5-5": {"backend": "anthropic"}}, {"anthropic": CB.AnthropicBackend("k", client=FakeClient())},
                       meter, tmp_path / "mode.json")
    sock = tmp_path / "bridge.sock"
    srv = CB.serve(sock, bridge)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = httpx.Client(transport=httpx.HTTPTransport(uds=str(sock)), base_url="http://cloud-bridge")
        assert c.get("/v1/models").json()["data"] == [{"id": "claude-opus-5-5", "object": "model"}]
        r = c.post("/v1/chat/completions", json=_body())
        events = [json.loads(x[6:]) for x in r.text.splitlines() if x.startswith("data: ") and x[6:] != "[DONE]"]
        content = "".join((ch.get("delta") or {}).get("content") or "" for e in events for ch in e.get("choices") or [])
        assert content == '{"code": "abc"}' and events[-1]["usage"]["completion_tokens"] == 20
        assert c.post("/v1/chat/completions", json=_body(model="nope")).status_code == 400
    finally:
        srv.shutdown()
        srv.server_close()
    rows = [json.loads(x) for x in meter.read_text().splitlines()]
    assert rows[0]["ok"] and rows[0]["usage"]["completion_tokens"] == 20 and rows[1]["ok"] is False
    assert "SECRET" not in meter.read_text()


def test_the_gateway_routes_a_model_to_a_unix_socket(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from forge_factory import llm_gateway

    meter = tmp_path / "meter.jsonl"
    (tmp_path / "mode.json").write_text('{"mode": "api"}')  # the API only when a mode file says so
    bridge = CB.Bridge({"claude-opus-5-5": {"backend": "anthropic"}}, {"anthropic": CB.AnthropicBackend("k", client=FakeClient())},
                       meter, tmp_path / "mode.json")
    sock = tmp_path / "bridge.sock"
    srv = CB.serve(sock, bridge)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("FORGE_GATEWAY_ROUTES", json.dumps({"claude-opus-5-5": f"unix:{sock}"}))
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    try:
        app = llm_gateway.create_app("http://127.0.0.1:9", meter_path=tmp_path / "gw.jsonl")
        with TestClient(app) as tc:
            r = tc.post("/v1/chat/completions", json=_body())
            assert r.status_code == 200 and '{\\"code\\": \\"abc\\"}' in r.text
    finally:
        srv.shutdown()
        srv.server_close()


def test_native_agent_tool_calls_translate_both_ways():
    hist = [{"role": "system", "content": "sys"}, {"role": "user", "content": "do it"},
            {"role": "assistant", "content": None, "tool_calls": [
                {"id": "call_1", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "a"}'}}]},
            {"role": "tool", "tool_call_id": "call_1", "content": "file text"},
            {"role": "user", "content": "go on"}]
    system, msgs = CB.anthropic_messages(hist)
    assert system == "sys" and [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[1]["content"] == [{"type": "tool_use", "id": "call_1", "name": "read_file", "input": {"path": "a"}}]
    assert msgs[2]["content"][0] == {"type": "tool_result", "tool_use_id": "call_1", "content": "file text"}
    assert not any(b.get("type") == "thinking" for m in msgs for b in m["content"])  # never replayed

    class ToolClient(FakeClient):
        def stream(self, **kw):
            self.calls.append(kw)
            usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0, cache_creation_input_tokens=0)
            block = SimpleNamespace(type="tool_use", id="toolu_9", name="write_file", input={"path": "b", "text": "x"})
            return FakeStream(SimpleNamespace(content=[block], stop_reason="tool_use", usage=usage))

    tc = ToolClient()
    body = {"model": "claude-opus-5-5", "messages": hist, "max_tokens": 100, "tool_choice": "auto",
            "tools": [{"type": "function", "function": {"name": "write_file", "description": "w",
                                                        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}}]}
    res = CB.AnthropicBackend("k", client=tc).answer(body, {"backend": "anthropic"})
    assert tc.calls[0]["tools"] == [{"name": "write_file", "description": "w", "input_schema":
                                     {"type": "object", "properties": {"path": {"type": "string"}}}}]
    assert "tool_choice" not in tc.calls[0] and res["finish"] == "tool_calls"
    assert res["tool_calls"] == [{"id": "toolu_9", "type": "function",
                                  "function": {"name": "write_file", "arguments": '{"path": "b", "text": "x"}'}}]


def test_openai_backend_passes_the_request_through_with_reasoning_headroom():
    seen = []

    def create(**kw):
        seen.append(kw)
        if kw["response_format"]["type"] == "json_schema" and len(seen) == 1 and kw["model"] == "reject":
            raise type("BadRequest", (Exception,), {"status_code": 400})("unsupported keyword")
        msg = SimpleNamespace(content='{"code": "abc"}', tool_calls=None)
        usage = SimpleNamespace(prompt_tokens=50, completion_tokens=20, total_tokens=70,
                                prompt_tokens_details=SimpleNamespace(cached_tokens=10),
                                completion_tokens_details=SimpleNamespace(reasoning_tokens=12))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")], usage=usage)

    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    be = CB.OpenAIBackend("k", client=fake)
    res = be.answer(_body(model="gpt-6.1-sol"), {"backend": "openai", "model": "gpt-6.1-sol", "reasoning_effort": "high",
                                                 "extra_output_tokens": 32768})
    kw = seen[0]
    assert kw["max_completion_tokens"] == 33768 and kw["reasoning_effort"] == "high" and kw["messages"][0]["content"] == "SECRET-SYSTEM"
    assert kw["response_format"]["json_schema"]["strict"] is True and res["schema_mode"] == "json_schema_strict"
    assert res["usage"]["reasoning_tokens"] == 12 and res["usage"]["cached_prompt_tokens"] == 10 and res["text"] == '{"code": "abc"}'
    seen.clear()
    res = be.answer(_body(), {"backend": "openai", "model": "reject"})
    assert res["schema_mode"] == "prompt_schema_fallback" and seen[-1]["response_format"] == {"type": "json_object"}


def _cli_run(seen, result=None, rc=0):
    def run(argv, **kw):
        seen.append((argv, kw))
        out = result if result is not None else {
            "type": "result", "subtype": "success", "is_error": False, "result": '{"code":"abc"}', "stop_reason": "end_turn",
            "structured_output": {"code": "abc"}, "total_cost_usd": 0.0104,
            "usage": {"input_tokens": 2, "cache_creation_input_tokens": 1111, "cache_read_input_tokens": 7, "output_tokens": 73,
                      "output_tokens_details": {"thinking_tokens": 40}}}
        return SimpleNamespace(returncode=rc, stdout=json.dumps(out), stderr="")
    return run


def test_account_mode_answers_through_the_claude_cli_without_tools_or_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-reach-the-cli")
    seen = []
    res = CB.ClaudeCliBackend(run=_cli_run(seen)).answer(_body(), {"backend": "anthropic", "effort": "medium"})
    argv, kw = seen[0]
    assert argv[:2] == ["claude", "-p"] and argv[argv.index("--model") + 1] == "claude-opus-5-5"
    assert argv[argv.index("--tools") + 1] == "" and "--strict-mcp-config" in argv and "--no-session-persistence" in argv
    assert argv[argv.index("--setting-sources") + 1] == "" and json.loads(argv[argv.index("--json-schema") + 1]) == SCHEMA
    assert "ANTHROPIC_API_KEY" not in kw["env"] and kw["input"] == "SECRET-USER" and "SECRET" not in " ".join(argv)
    assert res["text"] == '{"code": "abc"}' and res["usage"]["billing"] == "account" and "cost_usd" not in res["usage"]
    assert res["usage"]["prompt_tokens"] == 1120 and res["usage"]["list_cost_usd"] == 0.0104 and res["finish"] == "stop"
    bad = CB.ClaudeCliBackend(run=_cli_run([], {"type": "result", "is_error": True, "subtype": "error_max_turns"}, rc=1))
    try:
        bad.answer(_body(), {})
        raise AssertionError("a failed CLI call must raise")
    except RuntimeError as exc:
        assert str(exc).startswith("CLAUDE_CLI_FAILED")


def test_the_mode_file_routes_claude_per_call_and_tool_calls_never_reach_the_api_in_account_mode(tmp_path):
    mode = tmp_path / "claude-mode.json"
    seen = []
    api = FakeClient()
    bridge = CB.Bridge({"claude-opus-5-5": {"backend": "anthropic"}},
                       {"anthropic": CB.AnthropicBackend("k", client=api), "claude-cli": CB.ClaudeCliBackend(run=_cli_run(seen))},
                       tmp_path / "m.jsonl", mode)
    bridge.complete(_body())  # no mode file: the owner's default, account
    mode.write_text(json.dumps({"mode": "api"}))
    bridge.complete(_body())
    mode.write_text(json.dumps({"mode": "account"}))
    bridge.complete(_body())
    tools = {**_body(), "tools": [{"type": "function", "function": {"name": "read_file", "parameters": {"type": "object"}}}]}
    tool_seen = []
    bridge.backends["claude-cli"] = CB.ClaudeCliBackend(run=_cli_run(tool_seen, {
        "type": "result", "is_error": False, "stop_reason": "end_turn", "usage": {},
        "structured_output": {"action": "tool_calls", "tool_calls": [{"name": "read_file", "arguments": {}}], "content": ""}}))
    assert bridge.complete(tools)["finish"] == "tool_calls" and len(tool_seen) == 1
    bridge.backends["claude-cli"] = CB.ClaudeCliBackend(run=_cli_run(seen))
    mode.write_text("garbage")
    bridge.complete(_body())
    rows = [json.loads(x) for x in (tmp_path / "m.jsonl").read_text().splitlines()]
    assert [r["backend"] for r in rows] == ["claude-cli", "anthropic", "claude-cli", "claude-cli", "claude-cli"]
    assert [r["claude_mode"] for r in rows] == ["account", "api", "account", "account", "account"]  # garbage: default
    assert rows[3]["tool_emulation"] == "claude-cli" and "account_fallback" not in rows[3] and len(api.calls) == 1
    mode.write_text(json.dumps({"mode": "api"}))
    bridge.complete(tools)  # api mode: tools pass through to the API unchanged
    assert len(api.calls) == 2 and "tools" in api.calls[-1]
    assert CB.read_mode(None) == "account" and CB.read_mode(tmp_path / "missing") == "account"


def test_the_inspector_mode_file_routes_openai_to_the_codex_login(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-codex")
    seen, api = [], []

    def run(argv, **kw):
        seen.append((argv, kw))
        with open(argv[argv.index("-o") + 1], "w") as f:
            f.write('{"code": "xyz"}')
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    def create(**kw):
        api.append(kw)
        msg = SimpleNamespace(content='{"code": "abc"}', tool_calls=None)
        usage = SimpleNamespace(prompt_tokens=5, completion_tokens=2, total_tokens=7, prompt_tokens_details=None,
                                completion_tokens_details=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")], usage=usage)

    mode = tmp_path / "inspector-mode.json"
    cfg = {"backend": "openai", "model": "gpt-6.1-sol", "reasoning_effort": "high"}
    bridge = CB.Bridge({"gpt-6.1-sol": cfg},
                       {"openai": CB.OpenAIBackend("k", client=SimpleNamespace(chat=SimpleNamespace(
                           completions=SimpleNamespace(create=create)))), "codex": CB.CodexBackend(str(tmp_path), run=run)},
                       tmp_path / "m.jsonl", None, mode)
    mode.write_text(json.dumps({"mode": "api"}))
    bridge.complete(_body(model="gpt-6.1-sol"))
    mode.write_text(json.dumps({"mode": "account"}))
    res = bridge.complete(_body(model="gpt-6.1-sol"))
    with pytest.raises(CB.AccountToolCallError):  # tools on the account: emulated ('{"code"...}' is no envelope)
        bridge.complete({**_body(model="gpt-6.1-sol"), "tools": [{"type": "function", "function": {"name": "f"}}]})
    rows = [json.loads(x) for x in (tmp_path / "m.jsonl").read_text().splitlines()]
    assert [r["backend"] for r in rows] == ["openai", "codex", "codex"] and len(api) == 1 and len(seen) == 3
    assert rows[2]["tool_emulation"] == "codex-cli" and rows[2]["error_code"] == "ACCOUNT_MODE_TOOL_CALL_FAILED"
    assert "account_fallback" not in rows[2] and res["usage"]["billing"] == "account"
    argv, kw = seen[0]
    assert "OPENAI_API_KEY" not in kw["env"] and argv[argv.index("-m") + 1] == "gpt-6.1-sol"
    assert 'model_reasoning_effort="high"' in argv
