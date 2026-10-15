"""T004: verified Fabro 0.362 capabilities (recorded probe fixture + optional live smoke).

Live smoke runs only with FORGE_FABRO_LIVE=1 against the isolated Forge-C server; otherwise the
recorded fixture (captured from the real server, ADR-0002) is the mocked fallback.
"""
import json
import os
import subprocess
from pathlib import Path

import httpx
import pytest
from forge_factory.fabro.client import FabroClient, run_status

FIX = Path(__file__).parent / "fixtures"
EVENTS = [json.loads(line) for line in (FIX / "fabro-0.362-probe-events.jsonl").read_text().splitlines()]
HOOKS = [json.loads(line) for line in (FIX / "fabro-0.362-probe-hooks.jsonl").read_text().splitlines()]


def kinds():
    return [e["event"] for e in EVENTS]


def test_skill_discovery_and_activation_events_exist():
    assert "agent.skills.discovered" in kinds() and "agent.skill.activated" in kinds()


def test_mcp_stdio_server_ready_and_tool_called():
    assert "agent.mcp.server.ready" in kinds()
    done = [e for e in EVENTS if e["event"] == "agent.tool.completed"]
    names = [e["properties"]["event"]["ToolCallCompleted"]["tool_name"] for e in done]
    assert "mcp__forge_probe__ping" in names


def test_pre_tool_use_hook_sees_every_tool_and_can_deny_native_shell():
    assert [h["tool_name"] for h in HOOKS] == ["use_skill", "mcp__forge_probe__ping", "shell"]
    shell = [e["properties"]["event"]["ToolCallCompleted"] for e in EVENTS if e["event"] == "agent.tool.completed"
             and e["properties"]["event"]["ToolCallCompleted"]["tool_name"] == "shell"]
    assert shell and shell[0]["error_kind"] == "denied" and shell[0]["is_error"] is True


def test_no_reasoning_text_persisted_when_routed_through_gateway():
    for e in EVENTS:
        if e["event"] == "agent.message":
            assert "reasoning" not in e["properties"]["event"]["AssistantMessage"]


def test_events_are_ordered_and_usage_reported():
    seqs = [e["seq"] for e in EVENTS]
    assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
    done = [e for e in EVENTS if e["event"] == "run.completed"][0]
    assert done["properties"]["usage"]["tokens"]["input"] > 0


def test_client_pages_events_idempotently():
    def handler(req: httpx.Request) -> httpx.Response:
        since = int(req.url.params.get("since_seq", 0))
        limit = int(req.url.params.get("limit", 200))
        data = [e for e in EVENTS if e["seq"] > since][:limit]
        return httpx.Response(200, json={"data": data})

    c = FabroClient("http://x", "t", transport=httpx.MockTransport(handler))
    got = list(c.iter_events("r", 0, page=7))
    assert [e["seq"] for e in got] == [e["seq"] for e in EVENTS]
    assert list(c.iter_events("r", EVENTS[-1]["seq"])) == []


def test_client_pages_past_server_page_cap():
    def handler(req: httpx.Request) -> httpx.Response:  # server caps every page at 5 events
        since = int(req.url.params.get("since_seq", 0))
        return httpx.Response(200, json={"data": [e for e in EVENTS if e["seq"] > since][:5]})

    c = FabroClient("http://x", "t", transport=httpx.MockTransport(handler))
    assert [e["seq"] for e in c.iter_events("r")] == [e["seq"] for e in EVENTS]


def test_unreachable_fabro_is_not_healthy_and_unknown_status_not_pass():
    def handler(req):
        raise httpx.ConnectError("down")

    c = FabroClient("http://x", None, transport=httpx.MockTransport(handler))
    assert c.health() is False
    assert run_status({}) == "UNKNOWN"


@pytest.mark.skipif(os.environ.get("FORGE_FABRO_LIVE") != "1", reason="live Fabro smoke disabled")
def test_live_probe_against_installed_fabro():
    from forge_factory.fabro.client import load_token

    c = FabroClient(token=load_token())
    info = c.system_info()
    assert info["version"].startswith("0.362.0")
    repo = Path(__file__).resolve().parents[3]
    state = Path(os.environ["FORGE_STATE_DIR"]) / "probes" / "t004"
    for f in ("hook-calls.jsonl", "mcp-calls.jsonl"):
        (state / f).unlink(missing_ok=True)
    env = {**os.environ, "HOME": os.environ["FORGE_FABRO_HOME"], "FABRO_NO_UPGRADE_CHECK": "1"}
    fabro = os.environ["FORGE_FABRO_BIN"]
    out = subprocess.run([fabro, "run", str(state / "workflow.toml"), "--detach", "--auto-approve", "--environment",
                          "local", "--label", "forge=t004-live"], cwd=repo, env=env, capture_output=True, text=True,
                         timeout=120)
    run_id = out.stdout.strip().splitlines()[-1]
    subprocess.run([fabro, "wait", run_id], env=env, capture_output=True, timeout=600)
    evs = list(c.iter_events(run_id))
    assert run_status(c.get_run(run_id)) == "SUCCEEDED"
    hooks = [json.loads(x)["tool_name"] for x in (state / "hook-calls.jsonl").read_text().splitlines()]
    assert "shell" in hooks and any(h.startswith("mcp__forge_probe__") for h in hooks)
    denied = [e for e in evs if e["event"] == "agent.tool.completed"
              and e["properties"]["event"]["ToolCallCompleted"].get("error_kind") == "denied"]
    assert denied
    assert not any("reasoning" in e["properties"]["event"].get("AssistantMessage", {})
                   for e in evs if e["event"] == "agent.message")
