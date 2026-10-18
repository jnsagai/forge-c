"""Codex/ACP policy gate: the same decisions as the Fabro pre_tool_use hook, for every tool a Codex session has."""
import json
import os
import sys

import pytest
from forge_factory.acp.gate import Gate, serve
from forge_factory.policy.authz import Binding


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    saved = dict(os.environ)
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))
    w = tmp_path / "WO" / "workspace"
    for rel, text in {"workproducts/SWE.1/software_requirements.md": "- **SWR-001** x\n",
                      ".fabro/skills/swe2-author/SKILL.md": "# swe2-author skill v1\n",
                      ".fabro/skills/swe3-author/SKILL.md": "# swe3\n",
                      ".git/config": "[core]\n", ".forge-run/fabro_run_id": "RUN-1\n"}.items():
        (w / rel).parent.mkdir(parents=True, exist_ok=True)
        (w / rel).write_text(text)
    b = Binding("BND-T", str(w), {"swe2_author": {"role": "swe2-author", "phase": "SWE.2"}})
    b.dump(w / ".forge-run/binding.json")
    (w / ".forge-run/workflow.toml").write_text(f'''_version = 1
[run.agent.mcps.forge_docs_mcp]
type = "stdio"
command = ["{sys.executable}", "-m", "forge_factory.mcp.servers.docs"]
[run.agent.mcps.forge_docs_mcp.env]
FORGE_STATE_DIR = "{tmp_path / 'state'}"
FORGE_BINDING_ID = "BND-T"
''')
    yield w
    os.environ.clear()
    os.environ.update(saved)


def _fs(ws):
    return Gate(ws / ".forge-run/binding.json", "swe2_author", "forge_fs")


def test_file_tools_follow_the_native_tool_rules(ws):
    g = _fs(ws)
    assert g.call("read_file", {"file_path": "workproducts/SWE.1/software_requirements.md"}) == (False, "     1\t- **SWR-001** x")
    for path, code in ((".git/config", "SECRET_PATH_DENIED"), ("../../etc/passwd", "PATH_OUTSIDE_WORKSPACE")):
        err, text = g.call("read_file", {"file_path": path})
        assert err and text.startswith(f"FORGE_POLICY:{code}")
    assert g.call("write_file", {"file_path": "workproducts/SWE.2/a.md", "content": "x\n"})[0] is False
    assert (ws / "workproducts/SWE.2/a.md").read_text() == "x\n"
    for path, code in (("software/hal/x.c", "WRITE_SCOPE_DENIED"), (".forge-run/x", "PROTECTED_PATH_DENIED"),
                       ("inputs/rm.md", "PROTECTED_PATH_DENIED")):
        err, text = g.call("write_file", {"file_path": path, "content": "x"})
        assert err and text.startswith(f"FORGE_POLICY:{code}") and not (ws / path).exists()
    assert g.call("edit_file", {"file_path": "workproducts/SWE.2/a.md", "old_string": "x", "new_string": "y"})[0] is False


def test_only_the_own_skill_and_no_unknown_tool(ws):
    g = _fs(ws)
    assert g.call("use_skill", {"skill_name": "swe2-author"}) == (False, "# swe2-author skill v1\n")
    assert g.call("use_skill", {"skill_name": "swe3-author"})[1].startswith("FORGE_POLICY:FOREIGN_SKILL_DENIED")
    assert g.call("shell", {"command": "id"})[1].startswith("FORGE_POLICY:UNKNOWN_TOOL_DENIED")


def test_unbound_node_is_denied(ws):
    g = Gate(ws / ".forge-run/binding.json", "intruder", "forge_fs")
    assert g.call("read_file", {"file_path": "workproducts/SWE.1/software_requirements.md"})[1].startswith(
        "FORGE_POLICY:UNBOUND_AGENT")


def test_forge_mcp_operations_need_the_role_grant_and_are_ticketed(ws):
    g = Gate(ws / ".forge-run/binding.json", "swe2_author", "forge-docs-mcp")
    assert {t["name"] for t in g.tools()} >= {"validate_artifact", "build_docs"}
    assert g.call("build_docs", {})[1].startswith("FORGE_POLICY:MCP_TOOL_NOT_GRANTED")
    err, text = g.call("validate_artifact", {"path": "workproducts/SWE.1/software_requirements.md",
                                             "kind": "requirements"})
    assert not err
    assert "NO_BINDING" not in text and "TICKET" not in text.upper()      # reached the server with a valid ticket


def test_turn_budget_applies_per_node_visit(ws):
    from forge_factory.policy import governor as GV

    g = _fs(ws)
    limit = GV.turn_limit("swe2-author", str(ws))
    for _ in range(limit):
        assert g.call("list_dir", {"path": "."})[0] is False
    assert g.call("list_dir", {"path": "."})[1].startswith("FORGE_POLICY:TURN_BUDGET_EXHAUSTED")
    log = [json.loads(x) for x in (ws / ".forge-run/acp/swe2_author.gate.jsonl").read_text().splitlines()]
    assert log[-1] == {**log[-1], "allow": False, "code": "TURN_BUDGET_EXHAUSTED"}


def test_mcp_stdio_protocol(ws):
    import io

    lines = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
             {"jsonrpc": "2.0", "method": "notifications/initialized"},
             {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
             {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "write_file", "arguments": {
                 "file_path": "software/x.c", "content": "x"}}}]
    out = io.StringIO()
    serve(_fs(ws), io.StringIO("\n".join(json.dumps(x) for x in lines) + "\n"), out)
    res = [json.loads(x) for x in out.getvalue().splitlines()]
    assert res[0]["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert {t["name"] for t in res[1]["result"]["tools"]} >= {"read_file", "write_file", "use_skill"}
    assert res[2]["result"]["isError"] and "WRITE_SCOPE_DENIED" in res[2]["result"]["content"][0]["text"]
