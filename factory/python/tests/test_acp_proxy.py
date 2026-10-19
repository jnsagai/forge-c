"""Codex/ACP proxy: strips client capabilities, injects only gate servers, denies agent->client requests (edits,
commands, fs/terminal) without forwarding them, forwards updates, prepends the tool note."""
import io
import json
import re
import sys
import textwrap

from forge_factory.acp import proxy as P
from forge_factory.policy.authz import Binding

FAKE = textwrap.dedent('''
    import json, os, sys
    rec = open(sys.argv[1], "a")
    rec.write(json.dumps({"env": {k: os.environ.get(k) for k in ("CODEX_CONFIG", "CODEX_HOME", "CODEX_PATH",
                                                                  "INITIAL_AGENT_MODE")}}) + "\\n")
    def out(o): sys.stdout.write(json.dumps(o) + "\\n"); sys.stdout.flush()
    for line in sys.stdin:
        m = json.loads(line); rec.write(json.dumps(m) + "\\n"); rec.flush()
        if m.get("method") == "initialize":
            out({"jsonrpc": "2.0", "id": m["id"], "result": {"protocolVersion": 1}})
        elif m.get("method") == "session/new":
            out({"jsonrpc": "2.0", "id": 900, "method": "session/request_permission",
                 "params": {"toolCall": {"kind": "edit", "title": "Edit files"}, "options": [
                     {"optionId": "allow", "name": "Allow", "kind": "allow_once"},
                     {"optionId": "deny", "name": "Reject", "kind": "reject_once"}]}})
            out({"jsonrpc": "2.0", "id": 901, "method": "fs/write_text_file", "params": {"path": "/x", "content": "y"}})
            out({"jsonrpc": "2.0", "method": "session/update", "params": {"update": {"sessionUpdate": "agent_message_chunk"}}})
            out({"jsonrpc": "2.0", "id": m["id"], "result": {"sessionId": "S1"}})
        elif m.get("method") == "session/prompt":
            out({"jsonrpc": "2.0", "id": m["id"], "result": {"stopReason": "end_turn"}})
''')


def test_proxy_enforces_the_boundary(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws = tmp_path / "WO" / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/workflow.toml").write_text("[run.agent.mcps.forge_build_mcp]\ntype = \"stdio\"\n")
    b = ws / ".forge-run/binding.json"
    Binding("BND", str(ws), {"n1": {"role": "swe3-author", "phase": "SWE.3"}}).dump(b)
    fake, seen = tmp_path / "fake.py", tmp_path / "seen.jsonl"
    fake.write_text(FAKE)
    client = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": 1, "clientCapabilities": {
                  "fs": {"readTextFile": True, "writeTextFile": True}, "terminal": True}}},
              {"jsonrpc": "2.0", "id": 2, "method": "session/new", "params": {"cwd": str(ws), "mcpServers": [
                  {"name": "evil", "command": "/bin/sh", "args": [], "env": []}]}},
              {"jsonrpc": "2.0", "id": 3, "method": "session/prompt", "params": {"sessionId": "S1", "prompt": [
                  {"type": "text", "text": "do the task"}]}}]
    out = io.StringIO()
    p = P.Proxy(b, "n1", agent_argv=[sys.executable, str(fake), str(seen)], fin=iter(()), fout=out)
    import time

    def slow_lines():
        for x in client:
            yield json.dumps(x) + "\n"
            time.sleep(0.4)
    p.fin = slow_lines()
    p.run()
    to_agent = [json.loads(x) for x in seen.read_text().splitlines()]
    init = next(m for m in to_agent if m.get("method") == "initialize")
    assert init["params"]["clientCapabilities"] == {"fs": {"readTextFile": False, "writeTextFile": False}, "terminal": False}
    new = next(m for m in to_agent if m.get("method") == "session/new")
    assert new["params"]["mcpServers"] == []                                   # the client's "evil" server is dropped
    env = next(m["env"] for m in to_agent if "env" in m)
    assert env["INITIAL_AGENT_MODE"] == "read-only" and env["CODEX_HOME"].endswith("codex-home")
    codex_cfg = json.loads(env["CODEX_CONFIG"])
    assert codex_cfg["features"]["shell_tool"] is False and codex_cfg["features"]["unified_exec"] is False
    assert codex_cfg["model_verbosity"] == "low"
    cfg = codex_cfg["mcp_servers"]
    assert sorted(cfg) == ["forge_build_mcp", "forge_fs"]
    assert all(s["args"][:2] == ["-m", "forge_factory.acp.gate"] and s["default_tools_approval_mode"] == "approve"
               for s in cfg.values())
    replies = {m["id"]: m for m in to_agent if "id" in m and "method" not in m}
    assert replies[900]["result"] == {"outcome": {"outcome": "selected", "optionId": "deny"}}  # CAPA-049: not cancel
    assert replies[901]["error"]["code"] == -32601
    prompt = next(m for m in to_agent if m.get("method") == "session/prompt")
    assert prompt["params"]["prompt"][0]["text"] == P.TOOL_NOTE and prompt["params"]["prompt"][1]["text"] == "do the task"
    assert prompt["params"]["prompt"][-1]["text"] == P.REPLY_NOTE                   # CAPA-045: last instruction
    to_client = [json.loads(x) for x in out.getvalue().splitlines()]
    assert not any(m.get("method") in ("session/request_permission", "fs/write_text_file") for m in to_client)
    assert any(m.get("method") == "session/update" for m in to_client)
    assert {m.get("id") for m in to_client if "result" in m} >= {1, 2, 3}
    log = [json.loads(x) for x in (ws / ".forge-run/acp/n1.proxy.jsonl").read_text().splitlines()]
    assert {x["event"] for x in log} >= {"session", "denied_permission", "denied_request"}
    assert next(x for x in log if x["event"] == "session")["client_mcp_servers_dropped"] == ["evil"]


def test_attach_converts_author_nodes_only_and_drops_api_only_attributes(tmp_path):
    from forge_factory import acp

    g = ('digraph X {\n  swe3_author [label="SWE.3 author", model="qwen3-coder:30b", max_visits=3, prompt="do"]\n'
         '  swe3_inspector [label="SWE.3 inspector", prompt="check"]\n  gate [shape=parallelogram, script="x"]\n}\n')
    nodes = {"swe3_author": {"role": "swe3-author"}, "swe3_inspector": {"role": "swe3-inspector"}}
    out, done = acp.attach(g, nodes, tmp_path)
    assert done == ["swe3_author"]
    line = next(x for x in out.splitlines() if x.strip().startswith("swe3_author"))
    assert line.strip().startswith('swe3_author [backend="acp", acp.command="env ') and 'model="' not in line
    assert "--node swe3_author" in line and 'max_visits=3' in line
    assert 'swe3_inspector [label="SWE.3 inspector", prompt="check"]' in out


def test_attestation_sees_codex_authors_and_run_model_inspectors(tmp_path):
    from forge_factory.assurance import package as PK

    ws = tmp_path / "WO-X" / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/model-profile.json").write_text(json.dumps({
        "default": "deepseek-flash", "provider": "deepseek", "nodes": [],
        "acp_authors": {"nodes": ["swe3_author"], "model": "gpt-6.1-sol", "provider": "openai-codex"}}))
    att = PK.attestation(ws)
    assert att["decision"] == "SUPPORTED" and att["shared_common_cause_refs"] == []   # different model and provider


def test_capa049_a_denied_permission_rejects_and_never_cancels_the_turn():
    """CAPA-049 (LL r165): 'cancelled' ended the Codex turn and Fabro failed the whole run."""
    assert P.deny_outcome({"options": [{"optionId": "a1", "kind": "allow_once"}, {"optionId": "r2", "kind": "reject_always"},
                                       {"optionId": "r1", "kind": "reject_once"}]}) == {"outcome": "selected", "optionId": "r1"}
    assert P.deny_outcome({"options": [{"optionId": "a1", "kind": "allow_always"}]}) == {"outcome": "cancelled"}
    assert P.deny_outcome(None) == {"outcome": "cancelled"}


FAKE_CLAUDE = re.sub(r"for k in \([^)]*\)", 'for k in ("CLAUDE_CONFIG_DIR", "ANTHROPIC_API_KEY", '
                     '"CLAUDE_CODE_OAUTH_TOKEN", "DISABLE_AUTOUPDATER")', FAKE, count=1, flags=re.S)


def test_claude_proxy_gets_gate_servers_only_no_builtin_tools_and_no_api_key(tmp_path, monkeypatch):
    """OD-2026-10-19-08: inspectors on Claude (owner account) behind the same proxy and gates as Codex."""
    import time

    assert FAKE_CLAUDE != FAKE
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-must-not-pass")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "tok-must-not-pass")
    ws = tmp_path / "WO" / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/workflow.toml").write_text("[run.agent.mcps.forge_build_mcp]\ntype = \"stdio\"\n")
    b = ws / ".forge-run/binding.json"
    Binding("BND", str(ws), {"i1": {"role": "swe3-inspector", "phase": "SWE.3"}}).dump(b)
    fake, seen = tmp_path / "fake.py", tmp_path / "seen.jsonl"
    fake.write_text(FAKE_CLAUDE)
    client = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": 1, "clientCapabilities": {
                  "fs": {"readTextFile": True, "writeTextFile": True}, "terminal": True}}},
              {"jsonrpc": "2.0", "id": 2, "method": "session/new", "params": {"cwd": str(ws), "mcpServers": [
                  {"name": "evil", "command": "/bin/sh", "args": [], "env": []}]}},
              {"jsonrpc": "2.0", "id": 3, "method": "session/prompt", "params": {"sessionId": "S1", "prompt": [
                  {"type": "text", "text": "inspect"}]}}]
    out = io.StringIO()
    p = P.Proxy(b, "i1", agent_argv=[sys.executable, str(fake), str(seen)], fin=iter(()), fout=out, agent="claude")

    def slow_lines():
        for x in client:
            yield json.dumps(x) + "\n"
            time.sleep(0.4)
    p.fin = slow_lines()
    p.run()
    to_agent = [json.loads(x) for x in seen.read_text().splitlines()]
    env = next(m["env"] for m in to_agent if "env" in m)
    assert env["CLAUDE_CONFIG_DIR"].endswith("claude-home") and env["DISABLE_AUTOUPDATER"] == "1"
    assert env["ANTHROPIC_API_KEY"] is None and env["CLAUDE_CODE_OAUTH_TOKEN"] is None   # account login only
    init = next(m for m in to_agent if m.get("method") == "initialize")
    assert init["params"]["clientCapabilities"]["terminal"] is False
    new = next(m for m in to_agent if m.get("method") == "session/new")["params"]
    assert [s["name"] for s in new["mcpServers"]] == ["forge_fs", "forge_build_mcp"]       # "evil" dropped
    assert all(s["args"][:2] == ["-m", "forge_factory.acp.gate"] and "--node" in s["args"] and
               {"name": "PYTHONPATH", "value": s["env"][0]["value"]} in s["env"] for s in new["mcpServers"])
    opts = new["_meta"]["claudeCode"]["options"]
    assert opts["tools"] == [] and opts["settingSources"] == [] and opts["strictMcpConfig"] is True
    assert opts["model"] == "claude-opus-5-5" and new["_meta"]["disableBuiltInTools"] is True
    assert sorted(opts["allowedTools"]) == ["mcp__forge_build_mcp", "mcp__forge_fs"]
    replies = {m["id"]: m for m in to_agent if "id" in m and "method" not in m}
    assert replies[900]["result"] == {"outcome": {"outcome": "selected", "optionId": "deny"}}
    assert replies[901]["error"]["code"] == -32601
    prompt = next(m for m in to_agent if m.get("method") == "session/prompt")["params"]["prompt"]
    assert prompt[0]["text"] == P.TOOL_NOTE and prompt[-1]["text"] == P.REPLY_NOTE


def test_attach_claude_converts_inspectors_and_release_manager_only(tmp_path):
    from forge_factory import acp

    g = ('digraph X {\n  swe3_author [label="SWE.3 author", prompt="do"]\n'
         '  swe3_inspector [label="SWE.3 inspector", model="deepseek-flash", prompt="check"]\n'
         '  release_manager [label="Release Manager", max_visits=1, prompt="pack"]\n  gate [shape=parallelogram, script="x"]\n}\n')
    nodes = {"swe3_author": {"role": "swe3-author"}, "swe3_inspector": {"role": "swe3-inspector"},
             "release_manager": {"role": "release-manager"}}
    out, done = acp.attach(g, nodes, tmp_path, roles=acp.NON_AUTHOR_ROLES, agent="claude")
    assert done == ["swe3_inspector", "release_manager"]
    ins = next(x for x in out.splitlines() if x.strip().startswith("swe3_inspector"))
    assert "--node swe3_inspector --agent claude" in ins and 'model="' not in ins
    assert 'swe3_author [label="SWE.3 author", prompt="do"]' in out
    both, _ = acp.attach(out, nodes, tmp_path)                                  # then Codex authors on top
    assert "--agent" not in next(x for x in both.splitlines() if x.strip().startswith("swe3_author"))


def test_attestation_sees_claude_inspectors(tmp_path, monkeypatch):
    from forge_factory.assurance import independence
    from forge_factory.assurance import package as PK

    seen = {}
    real = independence.attest
    monkeypatch.setattr(independence, "attest", lambda wo, au, ins, *r: seen.update(au=au, ins=ins) or real(wo, au, ins, *r))

    ws = tmp_path / "WO-Y" / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/model-profile.json").write_text(json.dumps({
        "default": "deepseek-flash", "provider": "deepseek", "nodes": [],
        "acp_authors": {"nodes": ["swe3_author"], "model": "gpt-6.1-sol", "provider": "openai-codex"},
        "acp_inspectors": {"nodes": ["swe3_inspector"], "model": "claude-opus-5", "provider": "anthropic-claude"}}))
    att = PK.attestation(ws)
    assert att["decision"] == "SUPPORTED"
    assert (seen["ins"]["model"], seen["ins"]["provider"]) == ("claude-opus-5", "anthropic-claude")
    assert seen["au"]["model"] == "gpt-6.1-sol"
