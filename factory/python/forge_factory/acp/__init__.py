"""Codex via ACP under the factory policy (owner decision 2026-10-18, option 3).

Fabro 0.362's ACP backend runs an external agent without the pre_tool_use policy hook and without the run's MCP
servers (probe 2026-10-18). This package restores the guardrails around Codex (codex-acp):
  * codex_home: an isolated CODEX_HOME (factory login, no personal hooks/plugins/MCP servers) whose config turns off
    every Codex capability that acts outside MCP (shell, unified exec, browser/computer use, plugins, sub-agents,
    image tools, web search ...), read-only sandbox;
  * gate: the ONLY tools Codex gets - Fabro-native-equivalent file/skill tools and the run's forge MCP operations -
    each call decided by the existing policy hook logic (forge_factory.policy.fabro_hook.handle: role grants, path
    scopes, protected paths, turn budget), ticketed and audited exactly like a Fabro tool call; fail closed;
  * proxy: the ACP agent Fabro starts (acp.command); it strips client fs/terminal capabilities, injects the gate
    servers into session/new and denies every permission request (direct edits/commands) - nothing reaches Fabro.
"""

import re as _re
import sys as _sys
from pathlib import Path as _Path

ACP_PROVIDER = "openai-codex (owner ChatGPT login, forge ACP proxy + policy gates)"


def acp_command(ws: _Path, node: str) -> str:
    from ..common import state_dir

    pp = _Path(__file__).resolve().parents[2]
    return (f"env PYTHONPATH={pp} FORGE_STATE_DIR={state_dir()} {_sys.executable} -m forge_factory.acp.proxy "
            f"--binding {_Path(ws) / '.forge-run/binding.json'} --node {node}")


def attach(graph: str, nodes: dict[str, dict], ws: _Path, roles: tuple[str, ...] = ("-author",)) -> tuple[str, list[str]]:
    """Make the agent nodes whose role ends with one of `roles` ACP (Codex) nodes; API-only attributes are removed.
    Returns the new graph text and the converted node ids."""
    done = []
    out = []
    for line in graph.splitlines():
        m = _re.match(r"^(\s*)(\w+) \[(.*)\]\s*$", line)
        if m and m.group(2) in nodes and nodes[m.group(2)].get("role", "").endswith(roles) and 'prompt="' in line:
            attrs = _re.sub(r'(^|,\s*)model="[^"]*"', "", m.group(3)).lstrip(", ")
            line = f'{m.group(1)}{m.group(2)} [backend="acp", acp.command="{acp_command(ws, m.group(2))}", {attrs}]'
            done.append(m.group(2))
        out.append(line)
    return "\n".join(out) + ("\n" if graph.endswith("\n") else ""), done
