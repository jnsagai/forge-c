"""T009: the POSIX-sh locator finds hi-gates scripts under every APM target root."""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from conftest import PKG, SCRIPTS

LOCATE = SCRIPTS / "locate.sh"
ROOTS = [".claude/skills", ".agents/skills", ".github/skills", ".cursor/skills", ".kiro/skills"]


def install_probe(project, root):
    d = project / root / "hi-gates" / "scripts"
    d.mkdir(parents=True)
    (d / "probe.py").write_text("import sys; print('probe', *sys.argv[1:])\n")


@pytest.mark.parametrize("root", ROOTS)
def test_locator_finds_each_root(tmp_project, root):
    install_probe(tmp_project, root)
    r = subprocess.run(["sh", str(LOCATE), "probe.py", "x"], cwd=tmp_project, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "probe x"


def test_locator_env_override(tmp_project, tmp_path_factory):
    other = tmp_path_factory.mktemp("gates")
    (other / "probe.py").write_text("print('override')\n")
    r = subprocess.run(
        ["sh", str(LOCATE), "probe.py"],
        cwd=tmp_project,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "HI_GATES_DIR": str(other)},
    )
    assert r.stdout.strip() == "override"


def test_locator_missing_exits_127(tmp_project):
    r = subprocess.run(["sh", str(LOCATE), "probe.py"], cwd=tmp_project, capture_output=True, text=True)
    assert r.returncode == 127
    assert "hi-gates" in r.stderr


def _hook_command():
    doc = json.loads((PKG / ".apm" / "hooks" / "hi-write-scope.json").read_text())
    (entry,) = doc["hooks"]["PreToolUse"]
    return entry, entry["hooks"][0]["command"]


def test_hook_matcher_covers_write_tools():
    entry, _ = _hook_command()
    for tool in ("Write", "Edit", "MultiEdit", "NotebookEdit", "apply_patch"):
        assert tool in entry["matcher"].split("|")


@pytest.mark.parametrize("root", [".claude/skills", ".agents/skills"])
def test_hook_command_runs_guard_from_installed_root(tmp_project, root):
    _, cmd = _hook_command()
    dest = tmp_project / root / "hi-gates" / "scripts"
    shutil.copytree(SCRIPTS, dest)
    (tmp_project / ".hi").mkdir()
    (tmp_project / ".hi" / "active-role.json").write_text(json.dumps({"role": "author", "write_scope": ["hi/**"]}))
    payload = {"tool_name": "Write", "tool_input": {"file_path": "src/x.c"}, "cwd": str(tmp_project)}
    r = subprocess.run(["sh", "-c", cmd], cwd=tmp_project, input=json.dumps(payload), capture_output=True, text=True)
    assert r.returncode == 2, (r.stdout, r.stderr)
