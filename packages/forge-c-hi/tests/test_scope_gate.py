"""T025: the write-scope backstop gate (git mode and snapshot mode)."""
from __future__ import annotations

import subprocess

from forge_hi import scope
from hi_helpers import SYS_ITEMS, make_project, reqset, write


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def committed_project(root):
    make_project(root)
    git(root, "add", "-A")
    git(root, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "base")
    return root


def test_git_mode_inside_scope_passes(tmp_project):
    committed_project(tmp_project)
    write(tmp_project / "hi/sys-req/requirements.json", reqset("sys-req", SYS_ITEMS))
    write(tmp_project / "hi/sys-req/gates/quality.json", {})  # tool-owned, ignored in git mode
    doc = scope.run(tmp_project, "author", "sys-req")
    assert doc["verdict"] == "PASS", doc["issues"]
    assert "git" in doc["tool"]["name"]
    assert (tmp_project / "hi/sys-req/gates/scope.json").is_file()


def test_git_mode_outside_scope_fails(tmp_project):
    committed_project(tmp_project)
    write(tmp_project / "hi/sys-req/requirements.json", reqset("sys-req", SYS_ITEMS))
    (tmp_project / "needs/stakeholder-needs.md").write_text("tampered\n")
    write(tmp_project / "src/x.c", "int x;\n")
    doc = scope.run(tmp_project, "author", "sys-req")
    assert doc["verdict"] == "FAIL"
    assert {i["target_id"] for i in doc["issues"]} == {"needs/stakeholder-needs.md", "src/x.c"}


def test_inspector_may_write_nothing(tmp_project):
    committed_project(tmp_project)
    write(tmp_project / "hi/sys-req/requirements.json", reqset("sys-req", SYS_ITEMS))
    assert scope.run(tmp_project, "inspector", "sys-req")["verdict"] == "FAIL"


def test_sw_design_author_may_write_code():
    assert scope.violations(["src/sup.c", "include/sup.h", "hi/sw-design/design.json"],
                            scope.write_scope("author", "sw-design")) == []
    assert scope.violations(["tests/t.c"], scope.write_scope("author", "sw-design")) == ["tests/t.c"]


def test_snapshot_mode_without_git(tmp_path):
    make_project(tmp_path)
    snap = scope.save_snapshot(tmp_path, tmp_path / ".hi/runs/r1/snapshot.json")
    write(tmp_path / "hi/sys-req/requirements.json", reqset("sys-req", SYS_ITEMS))
    doc = scope.run(tmp_path, "author", "sys-req", snapshot_file=snap, write=False)
    assert doc["verdict"] == "PASS", doc["issues"]
    write(tmp_path / "src/evil.c", "int x;\n")
    doc = scope.run(tmp_path, "author", "sys-req", snapshot_file=snap)
    assert [i["target_id"] for i in doc["issues"]] == ["src/evil.c"]


def test_snapshot_mode_detects_change_add_and_delete(tmp_path):
    make_project(tmp_path)
    before = scope.snapshot(tmp_path)
    (tmp_path / "needs/constraints.md").unlink()
    write(tmp_path / "hi/sys-req/requirements.json", reqset("sys-req", SYS_ITEMS))
    (tmp_path / "needs/stakeholder-needs.md").write_text("changed\n")
    changed = scope.diff(before, scope.snapshot(tmp_path))
    assert changed == ["hi/sys-req/requirements.json", "needs/constraints.md", "needs/stakeholder-needs.md"]
    assert scope.violations(changed, scope.write_scope("author", "sys-req")) == [
        "needs/constraints.md", "needs/stakeholder-needs.md"]


def test_no_git_no_snapshot_is_not_run(tmp_path):
    make_project(tmp_path)
    assert scope.run(tmp_path, "author", "sys-req")["verdict"] == "NOT_RUN"


def test_snapshot_mode_flags_forged_gate_or_findings(tmp_path):
    make_project(tmp_path)
    snap = scope.save_snapshot(tmp_path, tmp_path / ".hi/runs/r1/snapshot.json")
    write(tmp_path / "hi/sys-req/inspection/findings.json", {"forged": True})
    write(tmp_path / "hi/sys-req/gates/quality.json", {"verdict": "PASS"})
    doc = scope.run(tmp_path, "author", "sys-req", snapshot_file=snap, write=False)
    assert sorted(i["target_id"] for i in doc["issues"]) == [
        "hi/sys-req/gates/quality.json", "hi/sys-req/inspection/findings.json"]


def test_running_hi_writes_no_bytecode_into_the_installed_skills(tmp_project):
    """Negative case T042 found it: `hi` run inside a consumer project left __pycache__ under .claude/skills, and the
    git-mode scope gate then reported those files as writes outside every role's scope."""
    import shutil
    import subprocess
    import sys
    from conftest import SKILLS
    from hi_helpers import SYS_ITEMS, make_project
    installed = tmp_project / ".claude" / "skills"
    shutil.copytree(SKILLS / "hi-gates", installed / "hi-gates",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    make_project(tmp_project, sys_items=SYS_ITEMS)
    for args in (["status"], ["gate", "sys-req"], ["quality", "sys-req"]):
        subprocess.run([sys.executable, str(installed / "hi-gates/scripts/hi.py"), *args], cwd=tmp_project,
                       capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
    subprocess.run([sys.executable, str(installed / "hi-gates/scripts/guard.py")], cwd=tmp_project, input="{}",
                   capture_output=True, text=True)
    assert list(installed.rglob("__pycache__")) == []
