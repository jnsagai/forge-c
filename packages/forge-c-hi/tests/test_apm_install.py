"""T003: the package installs through APM into Claude Code and Codex targets.

Skipped when the `apm` CLI is not on PATH (set HI_APM to an explicit binary to force a path).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest

from conftest import PKG

APM = os.environ.get("HI_APM") or shutil.which("apm")
pytestmark = pytest.mark.skipif(not APM, reason="apm CLI not installed")


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=300)


@pytest.fixture(scope="module")
def consumer(tmp_path_factory):
    src = tmp_path_factory.mktemp("pkgsrc") / "forge-c-hi"
    # install from a clean git copy so only tracked-style content is used
    shutil.copytree(PKG, src, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "tests"))
    for c in (["git", "init", "-q"], ["git", "add", "-A"]):
        run(c, src)
    run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "pkg"], src)
    proj = tmp_path_factory.mktemp("consumer")
    run(["git", "init", "-q"], proj)
    r = run([APM, "init", "-y", "--target", "claude,codex"], proj)
    assert r.returncode == 0, r.stdout + r.stderr
    r = run([APM, "install", str(src)], proj)
    assert r.returncode == 0, r.stdout + r.stderr
    return proj


@pytest.mark.parametrize("root", [".claude/skills", ".agents/skills"])
def test_gates_skill_and_scripts_installed(consumer, root):
    assert (consumer / root / "hi-gates" / "SKILL.md").is_file()
    assert (consumer / root / "hi-gates" / "scripts" / "guard.py").is_file()


def test_hooks_installed_for_both_targets(consumer):
    claude = json.loads((consumer / ".claude" / "settings.json").read_text())
    codex = json.loads((consumer / ".codex" / "hooks.json").read_text())
    for doc in (claude, codex):
        cmds = [h["command"] for e in doc["hooks"]["PreToolUse"] for h in e["hooks"]]
        assert any("guard.py" in c for c in cmds)


def test_agents_installed(consumer):
    assert (consumer / ".claude" / "agents" / "hi-inspector.md").is_file()
    assert (consumer / ".codex" / "agents" / "hi-inspector.toml").is_file()


def test_mcp_server_declared(consumer):
    mcp = json.loads((consumer / ".mcp.json").read_text())
    assert "forge-c-hi" in mcp["mcpServers"]


def test_apm_audit_clean(consumer):
    r = run([APM, "audit"], consumer)
    assert r.returncode == 0, r.stdout + r.stderr


def test_installed_mcp_server_starts_from_project_root(consumer):
    spec = json.loads((consumer / ".mcp.json").read_text())["mcpServers"]["forge-c-hi"]
    msg = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}})
    r = subprocess.run([spec["command"], *spec["args"]], cwd=consumer, input=msg + "\n", capture_output=True,
                       text=True, timeout=30)
    assert json.loads(r.stdout.splitlines()[0])["result"]["serverInfo"]["name"] == "forge-c-hi", r.stderr
