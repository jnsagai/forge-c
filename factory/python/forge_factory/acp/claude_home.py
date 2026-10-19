"""Isolated CLAUDE_CONFIG_DIR for factory Claude sessions (owner decision OD-2026-10-19-08: inspectors and the other
non-author agent nodes on Claude through the owner's Claude account, not the paid API). Only the owner's login lives
here (`CLAUDE_CONFIG_DIR=<it> claude auth login`); the owner's personal ~/.claude settings, hooks, plugins, MCP
servers and memory never load, and no session reads any settings file (settingSources = [])."""
from __future__ import annotations

import os
from pathlib import Path

from ..common import data_root

ADAPTER = "toolchains/claude-agent-acp-0.85.1/node_modules/.bin/claude-agent-acp"  # pinned, Apache-2.0
MODEL = "claude-opus-5-5"  # owner choice 2026-10-19 (Opus 5.5)
# API credentials are never used: the session authenticates with the owner's account login only.
API_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDE_CODE_OAUTH_TOKEN",
           "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX", "CLAUDE_CONFIG_DIR")


def home() -> Path:
    return data_root() / "claude-home"


def ensure() -> Path:
    h = home()
    h.mkdir(parents=True, exist_ok=True)
    os.chmod(h, 0o700)
    return h


def logged_in() -> bool:
    return (home() / ".credentials.json").is_file()


def agent_env(base: dict[str, str]) -> dict[str, str]:
    env = {k: v for k, v in base.items() if k not in API_ENV}
    return {**env, "CLAUDE_CONFIG_DIR": str(home()), "DISABLE_AUTOUPDATER": "1",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"}


def session_options(servers: list[str], model: str = MODEL) -> dict:
    """_meta.claudeCode.options for session/new: no built-in tool (no shell, file, web or sub-agent tools), no
    settings source, only the gate servers (each allowed without a prompt: the gate decides every call), MCP tools
    always loaded (a deferred tool would need the built-in ToolSearch tool, which is off)."""
    return {"tools": [], "settingSources": [], "strictMcpConfig": True, "model": model,
            "allowedTools": [f"mcp__{s}" for s in servers], "env": {"ENABLE_TOOL_SEARCH": "false"}}
