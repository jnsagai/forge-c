"""Codex/ACP proxy: strips client capabilities, injects only gate servers, denies agent->client requests (edits,
commands, fs/terminal) without forwarding them, forwards updates, prepends the tool note."""
import io
import json
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
                 "params": {"toolCall": {"kind": "edit", "title": "Edit files"}}})
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
    assert replies[900]["result"] == {"outcome": {"outcome": "cancelled"}}
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
