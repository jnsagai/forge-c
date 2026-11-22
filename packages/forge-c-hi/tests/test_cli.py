"""T026: the `hi` CLI contract (exit codes 0/1/2, one JSON object of at most 2 KB, documented output paths)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys

import pytest

from conftest import PKG, SCRIPTS
from hi_helpers import SWR_ITEMS, SYS_ITEMS, make_project, reqset, req, write

HI = SCRIPTS / "hi.py"


def hi(root, *args, check_size=True):
    r = subprocess.run([sys.executable, str(HI), *args], cwd=root, capture_output=True, text=True, timeout=60)
    lines = r.stdout.strip().splitlines()
    assert len(lines) == 1, (r.stdout, r.stderr)
    if check_size:
        assert len(lines[0].encode()) <= 2048
    return r.returncode, json.loads(lines[0])


def test_init_reference_presets(tmp_project):
    make_project(tmp_project)
    (tmp_project / ".hi/project.json").unlink()
    code, out = hi(tmp_project, "init", "--level", "HI-2", "--class", "nl", "--input", "needs/stakeholder-needs.md:needs")
    assert code == 0, out
    assert out["level_name"] == "HI-2" and out["entry"] == "sys-req"
    proj = json.loads((tmp_project / ".hi/project.json").read_text())
    assert proj["roles"]["author"]["harness"] == "claude-code"
    assert proj["roles"]["inspector"]["harness"] == "codex"
    assert proj["roles"]["inspector"]["read_only"] is True
    assert proj["roles"]["inspector"]["command"][:4] == ["codex", "exec", "-s", "read-only"]
    lock = json.loads((tmp_project / ".hi/inputs.lock.json").read_text())
    assert list(lock["inputs"]) == ["needs/stakeholder-needs.md"]
    code, out = hi(tmp_project, "init", "--level", "HI-2")
    assert code == 2 and "exists" in out["error"]


def test_init_from_example_and_profiles(tmp_project):
    ex = PKG / "examples" / "safety-supervisor"
    shutil.copytree(ex / "needs", tmp_project / "needs")
    code, out = hi(tmp_project, "init", "--from", str(ex / "hi-project.example.json"))
    assert code == 0, out
    assert out["project"] == "safety-supervisor" and out["inputs"] == 2
    code, out = hi(tmp_project, "init", "--from", str(ex / "hi-project.example.json"), "--profile", "iso26262", "--force")
    assert code == 0 and out["level_name"] == "ASIL B"
    code, out = hi(tmp_project, "init", "--level", "HI-0", "--profile", "iec61508", "--input",
                   "needs/stakeholder-needs.md:needs", "--force")
    assert code == 2 and "not defined" in out["error"]
    code, out = hi(tmp_project, "init", "--level", "HI-1", "--profile", "nosuch", "--force",
                   "--input", "needs/stakeholder-needs.md:needs")
    assert code == 2


def test_init_local_model_preset_needs_family(tmp_project):
    make_project(tmp_project)
    code, out = hi(tmp_project, "init", "--level", "HI-1", "--force", "--input", "needs/stakeholder-needs.md:needs",
                   "--inspector", "codex-oss-ollama", "--inspector-model", "qwen3-coder:30b")
    assert code == 2 and "model family" in out["error"]
    code, out = hi(tmp_project, "init", "--level", "HI-1", "--force", "--input", "needs/stakeholder-needs.md:needs",
                   "--inspector", "codex-oss-ollama", "--inspector-model", "qwen3-coder:30b", "--inspector-family", "qwen")
    assert code == 0, out
    cmd = json.loads((tmp_project / ".hi/project.json").read_text())["roles"]["inspector"]["command"]
    assert cmd[-2:] == ["-m", "qwen3-coder:30b"] and "--oss" in cmd


def test_init_warns_about_personal_data(tmp_project):
    make_project(tmp_project)
    (tmp_project / "needs/stakeholder-needs.md").write_text("- **STK-SUP-001** contact jane@example.com\n")
    code, out = hi(tmp_project, "init", "--level", "HI-1", "--force", "--input", "needs/stakeholder-needs.md:needs")
    assert code == 0 and out["warnings"]


def test_validate(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS)
    code, out = hi(tmp_project, "validate", "hi/sys-req/requirements.json")
    assert code == 0 and out["verdict"] == "PASS"
    assert (tmp_project / "hi/sys-req/gates/validate.json").is_file()
    bad = reqset("sys-req", SYS_ITEMS)
    bad["items"][0]["id"] = "bad id"
    write(tmp_project / "hi/sys-req/requirements.json", bad)
    code, out = hi(tmp_project, "validate", "hi/sys-req/requirements.json")
    assert code == 1 and out["verdict"] == "FAIL" and out["top"][0]["code"] == "VAL-SCHEMA"
    write(tmp_project / "x.json", {"schema": "something/else@1"})
    code, out = hi(tmp_project, "validate", "x.json")
    assert code == 1 and out["top"][0]["code"] == "VAL-NO-CONTRACT"


def test_quality_trace_and_files(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS)
    assert hi(tmp_project, "quality", "sys-req")[0] == 0
    code, out = hi(tmp_project, "trace", "--stage", "sw-req")
    assert code == 0 and out["written"] == "hi/trace-matrix.md"
    assert (tmp_project / "hi/trace.json").is_file() and (tmp_project / "hi/sw-req/gates/trace.json").is_file()


def test_scope_and_role(tmp_project):
    make_project(tmp_project)
    code, out = hi(tmp_project, "role", "set", "author", "sys-req", "--run-id", "r1")
    assert code == 0 and out["write_scope"] == ["hi/sys-req/**"]
    assert json.loads((tmp_project / ".hi/active-role.json").read_text())["role"] == "author"
    code, out = hi(tmp_project, "role", "clear")
    assert code == 0 and out["cleared"] is True and not (tmp_project / ".hi/active-role.json").exists()
    write(tmp_project / "src/a.c", "int a;\n")
    code, out = hi(tmp_project, "scope", "--role", "author", "--stage", "sys-req")
    assert code == 1 and out["verdict"] == "FAIL"


def test_gate_runs_required_gates_for_level(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS)
    code, out = hi(tmp_project, "gate", "sys-req")
    assert set(out["gates"]) == {"validate", "quality", "trace", "scope", "independence"}
    # needs/ and .hi/ are untracked in this fresh repo, so the git-mode scope backstop fails honestly
    assert out["gates"]["scope"] == "FAIL" and code == 1
    subprocess.run(["git", "add", "-A", "needs", ".hi"], cwd=tmp_project, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "x"],
                   cwd=tmp_project, check=True)
    code, out = hi(tmp_project, "gate", "sys-req")
    assert code == 0 and out["verdict"] == "PASS", out


def test_gate_level_changes_required_set_and_not_run_is_a_gap(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS, level="HI-0")
    code, out = hi(tmp_project, "gate", "sys-req")
    assert set(out["gates"]) == {"validate", "trace"} and code == 0
    make_project(tmp_project, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS, level="HI-2")
    subprocess.run(["git", "add", "-A"], cwd=tmp_project, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "x"],
                   cwd=tmp_project, check=True)
    code, out = hi(tmp_project, "gate", "sw-design")
    assert out["gates"]["build"] == "NOT_RUN" and code == 1


def test_independence_same_family_fails_at_hi3(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS, level="HI-3")
    proj = json.loads((tmp_project / ".hi/project.json").read_text())
    proj["roles"]["inspector"].update(harness="codex", model_family="fake-a")
    write(tmp_project / ".hi/project.json", proj)
    code, out = hi(tmp_project, "gate", "sys-req")
    assert out["gates"]["independence"] == "FAIL" and code == 1
    proj["roles"]["inspector"]["harness"] = "manual"  # a human inspector is independent of any model family
    write(tmp_project / ".hi/project.json", proj)
    assert hi(tmp_project, "gate", "sys-req")[1]["gates"]["independence"] == "PASS"


def test_status(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS)
    hi(tmp_project, "gate", "sys-req")
    code, out = hi(tmp_project, "status")
    assert code == 0 and out["next"] == "sys-req"
    assert out["stages"][0]["stage"] == "sys-req" and out["stages"][0]["gates"]["validate"] == "PASS"
    assert out["stages"][1]["state"] == "not-started"


@pytest.mark.parametrize("args", [["quality", "nosuch"], ["gate"], ["frobnicate"], ["scope", "--role", "x",
                                                                                     "--stage", "sys-req"]])
def test_usage_errors_exit_2(tmp_project, args):
    make_project(tmp_project)
    code, out = hi(tmp_project, *args)
    assert code == 2 and out["status"] == "ERROR"


def test_no_project_is_config_error(tmp_project):
    code, out = hi(tmp_project, "status")
    assert code == 2 and "hi init" in out["error"]


def test_doc_index_missing_document_fails(tmp_project):
    make_project(tmp_project)
    code, out = hi(tmp_project, "doc-index", "x.pdf", "--doc-id", "RM1")
    assert code == 1 and out["verdict"] == "FAIL" and out["top"][0]["code"] == "DOC-MISSING"


def test_stdout_capped_at_2kb(tmp_project):
    many = [req(f"SYS-SUP-{n:03d}", "The supervisor reacts quickly and/or soon.", ["STK-SUP-404"]) for n in range(1, 200)]
    make_project(tmp_project, sys_items=many)
    code, out = hi(tmp_project, "quality", "sys-req")
    assert code == 1 and out["issues"] > 100


def test_runs_from_a_subdirectory(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS)
    (tmp_project / "deep/er").mkdir(parents=True)
    code, out = hi(tmp_project / "deep/er", "validate", str(tmp_project / "hi/sys-req/requirements.json"))
    assert code == 0, out
