"""Owner safety-scope decision (2026-10-18: RCC ASIL B): reaches the work order read-only, is never agent-derived,
and an ASIL scope keeps the package BLOCKED until the human-written safety evidence exists."""
import json

import pytest
from forge_factory.assurance import package as P
from forge_factory.assurance import scope


def _repo(tmp_path, approved_by="Jefferson Nascimento", src="approved:owner-decision-2026-10-18"):
    (tmp_path / "config/factory").mkdir(parents=True)
    (tmp_path / scope.DECISIONS).write_text(
        "decisions:\n  - scope_id: SC-1\n    examples: [0002a-arm_55_rcc_ll]\n    target_asil: B\n"
        f"    product_asil_source: '{src}'\n    approved_by: '{approved_by}'\n    approved_at: '2026-10-18'\n")
    return tmp_path


def test_owner_decision_becomes_a_scope_record(tmp_path):
    rec = scope.owner_scope("0002a-arm_55_rcc_ll", "WO-1", "h" * 64, repo=_repo(tmp_path))
    assert rec["scope"]["target_asil"] == "B" and rec["scope"]["work_order_id"] == "WO-1"
    assert scope.owner_scope("other-example", "WO-1", "h" * 64, repo=tmp_path) is None


@pytest.mark.parametrize("who,src,err", [("agent:swe-author", "approved:x", "NOT_HUMAN_APPROVED"),
                                         ("Jefferson Nascimento", "profile:HIGH_ASSURANCE", "SCOPE_DECISION_INVALID")])
def test_agent_or_profile_derived_asil_is_refused(tmp_path, who, src, err):
    with pytest.raises(ValueError, match=err):
        scope.owner_scope("0002a-arm_55_rcc_ll", "WO-1", "h" * 64, repo=_repo(tmp_path, who, src))


def test_asil_b_scope_blocks_without_safety_evidence_and_travels_with_the_package(tmp_path):
    rec = scope.owner_scope("0002a-arm_55_rcc_ll", "WO-1", "h" * 64, repo=_repo(tmp_path))
    ws, stage = tmp_path / "WO-1/workspace", tmp_path / "stage"
    (ws / ".forge-run").mkdir(parents=True)
    stage.mkdir()
    (ws / P.SCOPE_FILE).write_text(json.dumps(rec))
    r = P.scope_dispositions(ws, stage)
    assert r["status"] == "BLOCKED" and r["target_asil"] == "B"
    assert {"SAFETY_EVIDENCE_MISSING:hsi", "SAFETY_EVIDENCE_MISSING:allocation_review",
            "SAFETY_EVIDENCE_MISSING:software_safety_analysis",
            "SAFETY_EVIDENCE_MISSING:tool_assurance_assessment"} <= set(r["issues"])
    assert json.loads((stage / "configuration/safety_scope.json").read_text())["scope"]["target_asil"] == "B"
