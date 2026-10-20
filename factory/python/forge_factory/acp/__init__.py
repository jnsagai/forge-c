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
OD-2026-10-19-08: the same proxy and gates also run Claude (claude-agent-acp on the owner's Claude account login,
claude_home) for the non-author nodes, with no built-in tool and no settings source.
"""

import re as _re
import sys as _sys
from pathlib import Path as _Path

ACP_PROVIDER = "openai-codex (owner ChatGPT login, forge ACP proxy + policy gates)"
CLAUDE_PROVIDER = "anthropic-claude (owner Claude account login, forge ACP proxy + policy gates)"
# OD-2026-10-19-08: every agent node that is not an author (the inspectors and the Release Manager)
NON_AUTHOR_ROLES = ("-inspector", "release-manager")


def acp_command(ws: _Path, node: str, agent: str = "codex") -> str:
    from ..common import state_dir

    pp = _Path(__file__).resolve().parents[2]
    return (f"env PYTHONPATH={pp} FORGE_STATE_DIR={state_dir()} {_sys.executable} -m forge_factory.acp.proxy "
            f"--binding {_Path(ws) / '.forge-run/binding.json'} --node {node}"
            + (f" --agent {agent}" if agent != "codex" else ""))


_NODE = _re.compile(r"^([ \t]*)(\w+) \[", _re.M)


def _close(text: str, i: int) -> int | None:
    """Index of the ']' closing the attribute list that starts at `i`, outside double-quoted strings (backslash
    escapes honoured); None when it never closes."""
    q = False
    while i < len(text):
        c = text[i]
        if q and c == "\\":
            i += 2
            continue
        if c == '"':
            q = not q
        elif c == "]" and not q:
            return i
        i += 1
    return None


def statements(graph: str):
    """Every `name [attrs]` node statement as (start, end, indent, name, attrs); attrs may span lines (CAPA-051: a
    prompt holding real line breaks, e.g. a code example, spans several lines)."""
    pos = 0
    for m in _NODE.finditer(graph):
        if m.start() < pos:
            continue
        end = _close(graph, m.end())
        if end is None or graph[end + 1:].split("\n", 1)[0].strip():
            continue
        pos = end + 1
        yield m.start(), end + 1, m.group(1), m.group(2), graph[m.end():end]


def _split_attrs(attrs: str) -> list[str]:
    out, q, i, start = [], False, 0, 0
    while i < len(attrs):
        c = attrs[i]
        if q and c == "\\":
            i += 2
            continue
        if c == '"':
            q = not q
        elif c == "," and not q:
            out.append(attrs[start:i])
            start = i + 1
        i += 1
    out.append(attrs[start:])
    return [a.strip() for a in out if a.strip()]


def attach(graph: str, nodes: dict[str, dict], ws: _Path, roles: tuple[str, ...] = ("-author",),
           agent: str = "codex") -> tuple[str, list[str]]:
    """Make the agent nodes whose role ends with one of `roles` ACP nodes of `agent` (codex | claude); API-only
    attributes are removed. Returns the new graph text and the converted node ids."""
    done, out, pos = [], [], 0
    for start, end, indent, name, attrs in statements(graph):
        if name in nodes and nodes[name].get("role", "").endswith(roles) and 'prompt="' in attrs:
            kept = ", ".join(a for a in _split_attrs(attrs) if not a.startswith("model="))
            out += [graph[pos:start], f'{indent}{name} [backend="acp", acp.command="{acp_command(ws, name, agent)}", '
                    f'{kept}]']
            pos = end
            done.append(name)
    out.append(graph[pos:])
    return "".join(out), done


def native_agent_nodes(graph: str) -> list[str]:
    """Agent nodes (a prompt) that would run on the Fabro run model rather than on an ACP backend."""
    return [name for _s, _e, _i, name, attrs in statements(graph)
            if 'prompt="' in attrs and 'backend="acp"' not in attrs]
