"""EASA-T071 / AT-071: the status matrix takes status from evidence only; forged, tampered, off-branch or reasonless
records never count as PASS."""
import hashlib
import json
import subprocess

import pytest
from forge_factory.assurance import matrix as M
from forge_factory.common import REPO_ROOT

HEAD = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def runs(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "RUNS", tmp_path / "runs")
    return tmp_path


def _rec(tmp, task, **over):
    d = tmp / "runs" / task
    d.mkdir(parents=True)
    log = d / "x.log"
    log.write_text("1 passed\n")
    rec = {"status": "PASS", "exit_code": 0, "git_head": HEAD, "log": str(log),
           "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(), **over}
    (d / "latest.json").write_text(json.dumps(rec))
    return log


def test_at071_valid_record_is_pass(runs):
    _rec(runs, "EASA-T900")
    assert M.task_status("EASA-T900", {})["status"] == "PASS"


@pytest.mark.parametrize("over,reason", [({"exit_code": 1}, "exit 1"), ({"status": "FAIL"}, "status FAIL"),
                                         ({"git_head": "0" * 40}, "not on this branch"), ({"log": None}, "exit 0")])
def test_at071_forged_or_off_branch_evidence_is_fail(runs, over, reason):
    _rec(runs, "EASA-T901", **over)
    s = M.task_status("EASA-T901", {})
    assert s["status"] == "FAIL" and reason in s["reason"]


def test_at071_tampered_log_is_fail(runs):
    _rec(runs, "EASA-T902").write_text("1 passed\nplus an edit\n")
    assert M.task_status("EASA-T902", {}) == {"status": "FAIL", "reason": "LOG_HASH_MISMATCH",
                                              "evidence": str(runs / "runs/EASA-T902/latest.json")}


def test_at071_blockers_need_a_reason_and_never_hide_as_pass(runs):
    assert M.task_status("EASA-T903", {}) == {"status": "NOT_RUN"}
    assert M.task_status("EASA-T903", {"EASA-T903": {"status": "BLOCKED", "reason": "owner authorization"}}) == \
        {"status": "BLOCKED", "reason": "owner authorization"}
    for bad in ({"status": "BLOCKED"}, {"status": "BLOCKED", "reason": " "}, {"status": "PASS", "reason": "x"}):
        assert M.task_status("EASA-T903", {"EASA-T903": bad})["status"] == "FAIL"
    _rec(runs, "EASA-T904", exit_code=2)
    s = M.task_status("EASA-T904", {"EASA-T904": {"status": "BLOCKED", "reason": "tool missing"}})
    assert s["status"] == "BLOCKED" and s["evidence"].endswith("latest.json")   # failed attempt stays visible


def test_at071_matrix_covers_all_tasks_and_frs_and_the_addendum():
    rep = M.build()
    assert len(rep["tasks"]) == 72 and len(rep["fr_matrix"]) == 72
    assert sorted(rep["addendum_tasks"]) == [f"EASA-T0{n}" for n in range(73, 80)]
    assert all(t["status"] in ("PASS", "FAIL", "NOT_RUN", "BLOCKED", "NOT_APPLICABLE", "PARTIAL")
               for t in list(rep["tasks"].values()) + list(rep["addendum_tasks"].values()))
    md = M.markdown(rep)
    assert "Owner addendum 2026-10-17" in md and "no ISO 26262 / Automotive SPICE conformance claim" in md
