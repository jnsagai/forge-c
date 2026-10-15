"""T050 (clean-workstation reproducibility + operations docs) and T051 (FR coverage matrix + status report)."""
import json
import os
import subprocess
import sys

import pytest
from forge_factory.common import REPO_ROOT

DOC = REPO_ROOT / "docs/OPERATIONS-v0.4.md"


def test_t050_operations_guide_covers_required_topics():
    t = DOC.read_text().lower()
    for topic in ("ubuntu workstation setup", "service lifecycle", "backup and restore", "trace retention",
                  "dashboard authentication", "upgrade and rollback", "failure runbook", "offline reviewer",
                  "known safety-tool"):
        assert topic in t, topic
    assert "not iso 26262" in t.replace("\n", " ") or "not constitutes" in t or "nothing in this guide" in t
    for script in ("scripts/forge-env.sh", "scripts/bootstrap_factory.sh", "scripts/forge_services.sh",
                   "scripts/install_supervisor.sh"):
        assert (REPO_ROOT / script).is_file() and script in DOC.read_text()


@pytest.mark.skipif(os.environ.get("FORGE_CLEAN_REPRO") != "1", reason="clean reproduction is slow; opt-in")
def test_t050_clean_bootstrap_reproduces_demo_and_fault_injections(tmp_path):
    venv = tmp_path / "venv"
    r = subprocess.run(["./scripts/bootstrap_factory.sh", str(venv)], cwd=REPO_ROOT, capture_output=True, text=True,
                       timeout=900)
    assert r.returncode == 0 and "BOOTSTRAP PASS" in r.stdout, r.stderr[-500:]
    demo = subprocess.run(["./scripts/run_oss_demo.sh"], cwd=REPO_ROOT, capture_output=True, text=True, timeout=900)
    assert demo.returncode == 0 and "DEMO PASS" in demo.stdout
    env = {**os.environ, "PYTHONPATH": ""}
    faults = subprocess.run([str(venv / "bin/python"), "-m", "pytest", "-q", "-p", "no:cacheprovider",
                             "factory/python/tests/test_m3_supervisor.py", "factory/python/tests/test_m4_repair.py",
                             "factory/python/tests/test_t007_policy.py", "-k", "not live"],
                            cwd=REPO_ROOT, capture_output=True, text=True, timeout=1200, env=env)
    assert faults.returncode == 0, faults.stdout[-800:]


def test_t051_status_report_no_unexplained_p0_gap():
    r = subprocess.run([sys.executable, "-m", "forge_factory.report"], cwd=REPO_ROOT, capture_output=True, text=True,
                       timeout=300)
    assert r.returncode == 0
    rep = json.loads((REPO_ROOT / "evidence/v0.4/implementation-status.json").read_text())
    assert rep["p0_gaps"] == []
    assert all(row["status"] == "COVERED" for row in rep["fr_matrix"] if row["priority"] == "P0")
    md = (REPO_ROOT / "docs/IMPLEMENTATION-STATUS-v0.4.md").read_text()
    assert "READY_FOR_OFFLINE_REVIEW or BLOCKED only" in md and "ASIL_B_APPROVED" not in md
    for t in rep["tasks_002"] + rep["tasks_003"]:
        assert t["status"] in ("PASS", "FAIL", "NOT_RUN")
        if t["status"] == "PASS":
            assert t["evidence"] and t["checked"]


def test_t051_all_contract_and_legacy_suites_pass():
    for cmd in ([sys.executable, "tests/spec/validate_design.py"],
                [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                [sys.executable, "-m", "unittest", "discover", "-s", "factory/release-manager/tests", "-p", "test_*.py"]):
        r = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=600)
        assert r.returncode == 0, (cmd, r.stdout[-400:], r.stderr[-400:])
    for p in ("examples/0002-arm_55_rcc_st/inputs/inputs-manifest.json", "config/factory/kpi-catalog.lock.json",
              "config/factory/skills.lock.json"):
        assert (REPO_ROOT / p).is_file()
