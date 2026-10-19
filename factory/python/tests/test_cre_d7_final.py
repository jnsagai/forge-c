"""CRE-T042 (AT-039): final verification - readiness is evidence-derived and never a safety claim, 001-003
regression is green, every checked task has passing evidence, convergence findings stay visible until done."""
import json
import re
import subprocess

from forge_factory.common import REPO_ROOT
from forge_factory.reliability import readiness as RD
from forge_factory.reliability import trace

TASKS = REPO_ROOT / "specs/004-continuous-reliability-engineering/tasks.md"


def test_readiness_is_recomputable_evidence_based_and_never_a_safety_claim():
    rec = json.loads((REPO_ROOT / "evidence/cre/readiness-assessment.json").read_text())
    now = RD.assess()
    assert rec["readiness"] == now["readiness"] in ("OBSERVE_ONLY", "PILOT_ELIGIBLE", "ACTIVE_ELIGIBLE",
                                                    "NOT_DEMONSTRATED")
    assert rec["safety_signoff"] is None and rec["scope"] == "OFFLINE_REVIEW_ONLY_NOT_SAFETY_APPROVED"
    assert "ISO 26262 / ASIL B approval" in rec["not_claimed"] and "universal or 100% reliability" in rec["not_claimed"]
    if rec["readiness"] != "PILOT_ELIGIBLE":
        assert rec["levels"]["PILOT_ELIGIBLE"]["missing"]  # every unmet prerequisite is named
    faults = json.loads((REPO_ROOT / "evidence/cre/faults/fault-injection-latest.json").read_text())
    e2e = json.loads((REPO_ROOT / "evidence/cre/e2e/local-qwen-e2e-latest.json").read_text())
    demo = json.loads((REPO_ROOT / "evidence/cre/promotion/candidate-vs-baseline-latest.json").read_text())
    assert faults["passed"] == faults["total"] >= 18 and faults["protected_inputs_sha256"]["unchanged"]
    assert e2e["result"] == "PASS"
    assert {"REJECTED", "ELIGIBLE_FOR_OFFLINE_REVIEW"} <= {d["decision"] for d in demo["decisions"]}
    assert all(d["allowed_auto_deployment"] is False for d in demo["decisions"])


def test_001_to_003_regression_baseline_is_green_on_this_line():
    b = json.loads((REPO_ROOT / "evidence/cre/baseline/baseline-latest.json").read_text())
    assert b["status"] == "PASS" and {r["id"] for r in b["results"]} >= {"design", "unittest-release-manager",
                                                                          "oss-demo", "factory-pytest"}
    anc = subprocess.run(["git", "merge-base", "--is-ancestor", b["git_head"], "HEAD"], cwd=REPO_ROOT)
    assert anc.returncode == 0


def test_every_checked_task_has_passing_evidence_and_open_findings_stay_visible():
    text = TASKS.read_text()
    for m in re.finditer(r"^- \[X\] \*\*(CRE-T\d{3})\b.*$", text, re.M):
        rec = json.loads((REPO_ROOT / f"evidence/v0.4/runs/{m.group(1)}/latest.json").read_text())
        assert rec["status"] == "PASS" and rec["exit_code"] == 0, m.group(1)
    assert "## Phase 8: Convergence" in text
    open_tasks = re.findall(r"^- \[ \] \*\*(CRE-T\d{3})", text, re.M)
    assert open_tasks == []  # all 54 closed with evidence (CRE-T053 last, 2026-10-19); a reopened task shows here
    assert all(r["status"] == "COVERED" for r in trace.rows() if r["priority"] == "P0")
