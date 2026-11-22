"""T008: the PreToolUse write-scope guard (Claude Code and Codex style inputs)."""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from conftest import SCRIPTS

GUARD = SCRIPTS / "guard.py"


def run_guard(cwd, payload, raw=None):
    data = raw if raw is not None else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(GUARD)], input=data, capture_output=True, text=True, cwd=cwd, timeout=20
    )


def set_role(root, scope, role="author", stage="sys-req"):
    (root / ".hi").mkdir(exist_ok=True)
    (root / ".hi" / "active-role.json").write_text(
        json.dumps({"role": role, "stage": stage, "write_scope": scope, "run_id": "r-1"})
    )


def claude(tool, path, cwd):
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    return {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {key: str(path)}, "cwd": str(cwd)}


def codex_patch(paths, cwd):
    body = "*** Begin Patch\n" + "".join(f"*** Update File: {p}\n@@\n-a\n+b\n" for p in paths) + "*** End Patch\n"
    return {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "tool_input": {"input": body}, "cwd": str(cwd)}


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit"])
def test_inside_scope_allowed(tmp_project, tool):
    set_role(tmp_project, ["hi/sys-req/**"])
    r = run_guard(tmp_project, claude(tool, tmp_project / "hi/sys-req/requirements.json", tmp_project))
    assert r.returncode == 0, r.stderr


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit", "NotebookEdit"])
def test_outside_scope_denied(tmp_project, tool):
    set_role(tmp_project, ["hi/sys-req/**"])
    r = run_guard(tmp_project, claude(tool, tmp_project / "hi/sw-req/requirements.json", tmp_project))
    assert r.returncode == 2
    assert "outside" in r.stderr.lower()


def test_relative_path_resolved_against_cwd(tmp_project):
    set_role(tmp_project, ["hi/sys-req/**"])
    r = run_guard(tmp_project, claude("Write", "hi/sys-req/x.json", tmp_project))
    assert r.returncode == 0, r.stderr


def test_path_escaping_project_denied(tmp_project):
    set_role(tmp_project, ["**"])
    r = run_guard(tmp_project, claude("Write", tmp_project.parent / "elsewhere.txt", tmp_project))
    assert r.returncode == 2


def test_hi_state_dir_is_never_writable_by_roles(tmp_project):
    set_role(tmp_project, ["**"])
    r = run_guard(tmp_project, claude("Write", tmp_project / ".hi/active-role.json", tmp_project))
    assert r.returncode == 2


def test_read_only_role_denies_everything(tmp_project):
    set_role(tmp_project, [], role="inspector")
    r = run_guard(tmp_project, claude("Write", tmp_project / "hi/sys-req/requirements.json", tmp_project))
    assert r.returncode == 2


def test_codex_apply_patch_all_paths_checked(tmp_project):
    set_role(tmp_project, ["hi/sys-req/**"])
    ok = run_guard(tmp_project, codex_patch(["hi/sys-req/a.json"], tmp_project))
    assert ok.returncode == 0, ok.stderr
    bad = run_guard(tmp_project, codex_patch(["hi/sys-req/a.json", "src/main.c"], tmp_project))
    assert bad.returncode == 2


def test_no_active_role_allows(tmp_project):
    r = run_guard(tmp_project, claude("Write", tmp_project / "anything.txt", tmp_project))
    assert r.returncode == 0


def test_malformed_input_fails_closed_when_role_active(tmp_project):
    set_role(tmp_project, ["hi/sys-req/**"])
    r = run_guard(tmp_project, None, raw="{not json")
    assert r.returncode == 2


def test_unknown_write_shape_fails_closed_when_role_active(tmp_project):
    set_role(tmp_project, ["hi/sys-req/**"])
    r = run_guard(tmp_project, {"tool_name": "Write", "tool_input": {"content": "x"}, "cwd": str(tmp_project)})
    assert r.returncode == 2


def test_role_file_found_from_subdirectory(tmp_project):
    set_role(tmp_project, ["hi/sys-req/**"])
    sub = tmp_project / "hi" / "sys-req"
    sub.mkdir(parents=True)
    r = run_guard(sub, claude("Write", sub / "requirements.json", sub))
    assert r.returncode == 0, r.stderr
