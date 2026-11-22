"""T027: the forge-c-hi MCP server over stdio."""
from __future__ import annotations

import json
import re
import subprocess
import sys

import pytest

from conftest import SCRIPTS, SPECS
from hi_helpers import SWR_ITEMS, SYS_ITEMS, make_project

SERVER = SCRIPTS / "hi_mcp.py"


class Client:
    def __init__(self, cwd):
        self.p = subprocess.Popen([sys.executable, str(SERVER)], cwd=cwd, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.n = 0

    def raw(self, line):
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()
        return json.loads(self.p.stdout.readline())

    def call(self, method, params=None):
        self.n += 1
        return self.raw(json.dumps({"jsonrpc": "2.0", "id": self.n, "method": method, "params": params or {}}))

    def notify(self, method):
        self.p.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.p.stdin.flush()

    def close(self):
        self.p.stdin.close()
        self.p.wait(timeout=10)


@pytest.fixture
def client(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS)
    c = Client(tmp_project)
    yield c
    c.close()


def test_initialize_and_list(client):
    r = client.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                   "clientInfo": {"name": "t", "version": "0"}})
    assert r["result"]["serverInfo"]["name"] == "forge-c-hi"
    assert r["result"]["protocolVersion"] == "2025-06-18"
    client.notify("notifications/initialized")
    assert client.call("ping")["result"] == {}
    tools = {t["name"] for t in client.call("tools/list")["result"]["tools"]}
    contract = (SPECS / "contracts" / "cli-and-mcp.md").read_text()
    documented = set(re.findall(r"`(hi_[a-z_]+)`", contract))
    assert documented and documented <= tools


def test_trace_tool_matches_cli(client, tmp_project):
    r = client.call("tools/call", {"name": "hi_trace_check", "arguments": {"stage": "sw-req"}})["result"]
    assert r["isError"] is False
    mcp_payload = r["structuredContent"]
    assert json.loads(r["content"][0]["text"]) == mcp_payload
    cli = subprocess.run([sys.executable, str(SCRIPTS / "hi.py"), "trace", "--stage", "sw-req"], cwd=tmp_project,
                         capture_output=True, text=True)
    assert json.loads(cli.stdout) == mcp_payload
    assert mcp_payload["verdict"] == "PASS"


def test_fail_is_a_result_and_config_error_is_error(client):
    r = client.call("tools/call", {"name": "hi_quality_rules", "arguments": {"stage": "nosuch"}})["result"]
    assert r["isError"] is True
    r = client.call("tools/call", {"name": "hi_scope_check", "arguments": {"role": "inspector", "stage": "sys-req"}})
    assert r["result"]["isError"] is False and r["result"]["structuredContent"]["verdict"] == "FAIL"


def test_unknown_tool_and_method_are_jsonrpc_errors(client):
    assert client.call("tools/call", {"name": "hi_nope", "arguments": {}})["error"]["code"] == -32602
    assert client.call("resources/list")["error"]["code"] == -32601
    assert client.raw("{not json")["error"]["code"] == -32700
