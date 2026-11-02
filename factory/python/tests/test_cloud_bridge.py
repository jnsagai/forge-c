"""Owner 2026-11-02: the Claude/Codex comparison line answers the same structured tasks through a bridge behind the
unchanged gateway. Fake backends only (no paid call, no CLI): SSE shape the structured runner reads, schema handling,
Codex strict-schema rule, metering without prompts, unix-socket gateway route."""
import json
import threading
from types import SimpleNamespace

import httpx
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
    bridge = CB.Bridge({"claude-opus-5-5": {"backend": "anthropic"}}, {"anthropic": CB.AnthropicBackend("k", client=FakeClient())},
                       meter)
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
    bridge = CB.Bridge({"claude-opus-5-5": {"backend": "anthropic"}}, {"anthropic": CB.AnthropicBackend("k", client=FakeClient())},
                       meter)
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
