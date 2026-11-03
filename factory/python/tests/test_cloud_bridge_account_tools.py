"""Owner 2026-11-03 ("the account claude is the default, not the API"): in account mode a tool-calling request (Fabro
native agent nodes) is answered through the Claude account CLI by tool-call emulation - never by the Anthropic API.
Fake claude CLI only (an injected runner and one fake executable): no network, no account call, no API call."""
import json
import os
import stat
import sys
import threading

import httpx
import pytest
from forge_factory.lrtx import cloud_bridge as CB

READ = {"type": "object", "additionalProperties": False, "required": ["path"],
        "properties": {"path": {"type": "string", "minLength": 1}}}
WRITE = {"type": "object", "additionalProperties": False, "required": ["path", "text"],
         "properties": {"path": {"type": "string"}, "text": {"type": "string"}}}
TOOLS = [{"type": "function", "function": {"name": "read_file", "description": "read a file", "parameters": READ}},
         {"type": "function", "function": {"name": "write_file", "description": "write a file", "parameters": WRITE}}]
HIST = [{"role": "system", "content": "SECRET-SYSTEM"}, {"role": "user", "content": "SECRET-USER copy a to b"},
        {"role": "assistant", "content": None, "tool_calls": [
            {"id": "call_1", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "a"}'}}]},
        {"role": "tool", "tool_call_id": "call_1", "content": "SECRET-FILE-TEXT"}]


def _body(**kw):
    return {"model": "claude-opus-5-5", "stream": True, "max_tokens": 1000, "messages": HIST, "tools": TOOLS,
            "tool_choice": "auto", **kw}


def _out(so, stop="end_turn"):
    return {"type": "result", "subtype": "success", "is_error": False, "result": "", "stop_reason": stop,
            "structured_output": so, "total_cost_usd": 0.01,
            "usage": {"input_tokens": 10, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 0, "output_tokens": 7}}


def _cli(seen, *answers, rc=0):
    """A fake `claude -p`: records argv, stdin, env and the system prompt file; answers in order."""
    queue = list(answers)

    def run(argv, **kw):
        sp = argv[argv.index("--system-prompt-file") + 1]
        seen.append({"argv": argv, "input": kw["input"], "env": kw["env"], "system": open(sp).read(),
                     "schema": json.loads(argv[argv.index("--json-schema") + 1]) if "--json-schema" in argv else None})
        out = queue.pop(0) if len(queue) > 1 else queue[0]
        return type("P", (), {"returncode": rc, "stdout": json.dumps(out), "stderr": ""})()
    return run


CALL_WRITE = {"action": "tool_calls", "tool_calls": [{"name": "write_file", "arguments": {"path": "b", "text": "x"}}],
              "content": ""}


def test_a_tool_call_round_trips_through_the_account_cli(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-reach-the-cli")
    seen = []
    res = CB.ClaudeCliBackend(run=_cli(seen, _out(CALL_WRITE))).answer(_body(), {"effort": "medium"})
    s = seen[0]
    assert s["argv"][s["argv"].index("--tools") + 1] == "" and "--strict-mcp-config" in s["argv"]
    assert "ANTHROPIC_API_KEY" not in s["env"]
    assert s["schema"]["properties"]["tool_calls"]["items"]["properties"]["name"]["enum"] == ["read_file", "write_file"]
    assert s["schema"]["properties"]["action"]["enum"] == ["tool_calls", "final"]
    assert s["system"].startswith("SECRET-SYSTEM\n\nTOOL CALLING.") and '"name": "write_file"' in s["system"]
    # the whole conversation, the earlier tool call and its result included, reaches the CLI
    assert "[user]\nSECRET-USER copy a to b" in s["input"]
    assert '[assistant tool call id=call_1]\n{"arguments": {"path": "a"}, "name": "read_file"}' in s["input"]
    assert "[tool result id=call_1 name=read_file]\nSECRET-FILE-TEXT" in s["input"]
    assert res["finish"] == "tool_calls" and res["schema_mode"] == "tool_emulation_json_schema"
    (tc,) = res["tool_calls"]
    assert tc["id"].startswith("call_") and len(tc["id"]) == 29 and tc["type"] == "function"
    assert tc["function"] == {"name": "write_file", "arguments": '{"path": "b", "text": "x"}'}
    assert res["usage"]["billing"] == "account" and res["meter"] == {"tool_emulation": "claude-cli",
                                                                      "tool_emulation_attempts": 1, "tool_calls": 1}


def test_parallel_calls_and_a_final_answer():
    two = {"action": "tool_calls", "content": "both", "tool_calls": [{"name": "read_file", "arguments": {"path": "x"}},
                                                                     {"name": "read_file", "arguments": {"path": "y"}}]}
    res = CB.ClaudeCliBackend(run=_cli([], _out(two))).answer(_body(), {})
    assert [json.loads(c["function"]["arguments"])["path"] for c in res["tool_calls"]] == ["x", "y"]
    assert len({c["id"] for c in res["tool_calls"]}) == 2 and res["text"] == "both"
    final = {"action": "final", "tool_calls": [], "content": "done: b written"}
    res = CB.ClaudeCliBackend(run=_cli([], _out(final))).answer(_body(), {})
    assert res["finish"] == "stop" and res["tool_calls"] == [] and res["text"] == "done: b written"


def test_tool_choice_and_parallel_flag_shape_the_envelope():
    seen = []
    be = CB.ClaudeCliBackend(run=_cli(seen, _out(CALL_WRITE)))
    be.answer(_body(tool_choice="required", parallel_tool_calls=False), {})
    sch = seen[-1]["schema"]
    assert sch["properties"]["action"]["enum"] == ["tool_calls"] and sch["properties"]["tool_calls"]["maxItems"] == 1
    assert "You MUST call a tool" in seen[-1]["system"] and "at most ONE tool" in seen[-1]["system"]
    be.answer(_body(tool_choice={"type": "function", "function": {"name": "write_file"}}), {})
    assert seen[-1]["schema"]["properties"]["tool_calls"]["items"]["properties"]["name"]["enum"] == ["write_file"]
    with pytest.raises(CB.AccountToolCallError, match="TOOL_CHOICE_NOT_OFFERED"):
        be.answer(_body(tool_choice={"type": "function", "function": {"name": "rm_rf"}}), {})
    # tool_choice none: a plain answer on the account (no envelope), the tool history still rendered
    plain = {**_out(None), "result": "plain text"}
    seen2 = []
    res = CB.ClaudeCliBackend(run=_cli(seen2, plain)).answer(_body(tool_choice="none"), {})
    assert seen2[0]["schema"] is None and res["text"] == "plain text" and "[tool result id=call_1" in seen2[0]["input"]


def test_a_malformed_answer_gets_one_repair_retry():
    bad = {"action": "tool_calls", "tool_calls": [{"name": "write_file", "arguments": {"path": "b"}}], "content": ""}
    seen = []
    res = CB.ClaudeCliBackend(run=_cli(seen, _out(bad), _out(CALL_WRITE))).answer(_body(), {})
    assert len(seen) == 2 and res["finish"] == "tool_calls"
    assert res["meter"]["tool_emulation_attempts"] == 2 and res["meter"]["tool_emulation_rejected"] == [
        "TOOL_ARGS_INVALID:write_file:$"]
    assert "[bridge]\nYour previous answer was rejected" in seen[1]["input"] and "'text' is a required property" in seen[1]["input"]
    assert res["usage"]["prompt_tokens"] == 220 and res["usage"]["list_cost_usd"] == 0.02  # both attempts metered


@pytest.mark.parametrize("so,reason", [
    (None, "NO_STRUCTURED_ANSWER"),
    ({"action": "tool_calls", "tool_calls": [{"name": "rm_rf", "arguments": {}}], "content": ""},
     "ENVELOPE_INVALID:$.tool_calls[0].name"),
    ({"action": "final", "tool_calls": [{"name": "read_file", "arguments": {"path": "a"}}], "content": ""},
     "FINAL_WITH_TOOL_CALLS"),
    ({"action": "tool_calls", "tool_calls": [], "content": ""}, "TOOL_CALLS_EMPTY"),
    ({"action": "tool_calls", "tool_calls": [{"name": "read_file", "arguments": {"path": ""}}], "content": ""},
     "TOOL_ARGS_INVALID:read_file:$.path"),
])
def test_still_malformed_after_the_repair_is_an_explicit_refusal(so, reason):
    seen = []
    with pytest.raises(CB.AccountToolCallError) as ei:
        CB.ClaudeCliBackend(run=_cli(seen, _out(so))).answer(_body(), {})
    assert len(seen) == 2 and str(ei.value) == f"ACCOUNT_MODE_TOOL_CALL_FAILED:MALFORMED_AFTER_REPAIR:{reason}"
    assert ei.value.meter["tool_emulation_rejected"] == [reason, reason] and ei.value.meter["usage"]["billing"] == "account"


def test_a_cli_failure_or_a_broken_tool_schema_is_refused_without_retry():
    seen = []
    with pytest.raises(CB.AccountToolCallError, match="ACCOUNT_MODE_TOOL_CALL_FAILED:CLAUDE_CLI_FAILED:rc1"):
        CB.ClaudeCliBackend(run=_cli(seen, {"type": "result", "is_error": True, "subtype": "x"}, rc=1)).answer(_body(), {})
    assert len(seen) == 1
    broken = [{"type": "function", "function": {"name": "f", "parameters": {"type": "no-such-type"}}}]
    with pytest.raises(CB.AccountToolCallError, match="TOOL_SCHEMA_INVALID:f"):
        CB.ClaudeCliBackend(run=_cli(seen, _out(CALL_WRITE))).answer(_body(tools=broken), {})
    assert len(seen) == 1


class NoApi:
    """The API backend in account mode: any call is a test failure."""

    def answer(self, body, cfg):
        raise AssertionError("account mode reached the Anthropic API")


def _serve(tmp_path, cli):
    mode = tmp_path / "claude-mode.json"
    mode.write_text(json.dumps({"mode": "account"}))
    bridge = CB.Bridge({"claude-opus-5-5": {"backend": "anthropic"}}, {"anthropic": NoApi(), "claude-cli": cli},
                       tmp_path / "calls.jsonl", mode)
    sock = tmp_path / "bridge.sock"
    srv = CB.serve(sock, bridge)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, httpx.Client(transport=httpx.HTTPTransport(uds=str(sock)), base_url="http://cloud-bridge")


def test_the_bridge_streams_emulated_tool_calls_and_meters_them(tmp_path):
    srv, c = _serve(tmp_path, CB.ClaudeCliBackend(run=_cli([], _out(CALL_WRITE))))
    try:
        r = c.post("/v1/chat/completions", json=_body())
        events = [json.loads(x[6:]) for x in r.text.splitlines() if x.startswith("data: ") and x[6:] != "[DONE]"]
        deltas = [ch for e in events for ch in e.get("choices") or []]
        (tc,) = deltas[0]["delta"]["tool_calls"]
        assert tc["index"] == 0 and tc["function"]["name"] == "write_file" and tc["id"].startswith("call_")
        assert deltas[-1]["finish_reason"] == "tool_calls" and events[-1]["usage"]["billing"] == "account"
        r = c.post("/v1/chat/completions", json={**_body(), "stream": False})
        msg = r.json()["choices"][0]
        assert msg["finish_reason"] == "tool_calls" and msg["message"]["tool_calls"][0]["function"]["name"] == "write_file"
    finally:
        srv.shutdown()
        srv.server_close()
    rows = [json.loads(x) for x in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert all(r["backend"] == "claude-cli" and r["tool_emulation"] == "claude-cli" and r["ok"] for r in rows)
    assert rows[0]["tool_calls"] == 1 and rows[0]["finish"] == "tool_calls" and "account_fallback" not in rows[0]
    assert "SECRET" not in (tmp_path / "calls.jsonl").read_text()


def test_the_bridge_refuses_explicitly_and_records_it(tmp_path):
    srv, c = _serve(tmp_path, CB.ClaudeCliBackend(run=_cli([], _out({"action": "nonsense"}))))
    try:
        r = c.post("/v1/chat/completions", json=_body())
        err = r.json()["error"]
        assert r.status_code == 502 and err["type"] == "account_mode_tool_call_failed"
        assert err["code"] == "ACCOUNT_MODE_TOOL_CALL_FAILED" and "SECRET" not in r.text
    finally:
        srv.shutdown()
        srv.server_close()
    (row,) = [json.loads(x) for x in (tmp_path / "calls.jsonl").read_text().splitlines()]
    assert row["ok"] is False and row["error_code"] == "ACCOUNT_MODE_TOOL_CALL_FAILED" and row["backend"] == "claude-cli"
    assert row["tool_emulation"] == "claude-cli" and row["tool_emulation_attempts"] == 2
    assert row["error"].startswith("AccountToolCallError:ACCOUNT_MODE_TOOL_CALL_FAILED:MALFORMED_AFTER_REPAIR:ENVELOPE_INVALID")
    assert "SECRET" not in (tmp_path / "calls.jsonl").read_text()


def test_a_fake_claude_executable_through_a_real_subprocess(tmp_path, monkeypatch):
    """The real subprocess path: argv, stdin, environment and the empty working directory as the CLI gets them."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-reach-the-cli")
    log = tmp_path / "fake-claude.json"
    exe = tmp_path / "claude"
    exe.write_text(f"""#!{sys.executable}
import json, os, sys
argv = sys.argv[1:]
stdin = sys.stdin.read()
json.dump({{"argv": argv, "stdin": stdin, "key": "ANTHROPIC_API_KEY" in os.environ, "cwd_files": os.listdir(".")}},
          open({str(log)!r}, "w"))
schema = json.loads(argv[argv.index("--json-schema") + 1])
assert schema["properties"]["action"]["enum"] == ["tool_calls", "final"]
print(json.dumps({{"type": "result", "is_error": False, "stop_reason": "end_turn", "usage": {{"input_tokens": 3}},
                  "structured_output": {{"action": "tool_calls", "content": "",
                                        "tool_calls": [{{"name": "read_file", "arguments": {{"path": "c"}}}}]}}}}))
""")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    res = CB.ClaudeCliBackend(exe=str(exe)).answer(_body(), {"timeout_s": 60})
    seen = json.loads(log.read_text())
    assert res["tool_calls"][0]["function"] == {"name": "read_file", "arguments": '{"path": "c"}'}
    assert seen["key"] is False and seen["cwd_files"] == ["system.txt"] and "[tool result id=call_1" in seen["stdin"]
    assert seen["argv"][0] == "-p" and os.path.basename(str(exe)) == "claude"
