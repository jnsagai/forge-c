"""The PROPOSED detection lessons written from the cloud cross-inspection of 2026-11-02 (IL-005..IL-010): generic,
validator-clean, paired with their lrtx-seeded-3 defects, bound to the frozen real misses and the certified-clean
baselines, and never retrieved by a production inspector before a paired trial and a CRE decision promote them."""
from __future__ import annotations

import pytest
from forge_factory.knowledge import inspection as IL
from forge_factory.lrtx import seeded as SD

PAIRS = {"IL-005": ["S1-DOMAIN"], "IL-006": ["S1-OBLDECLINE", "S1-OBLNARROW"], "IL-007": ["S1-PRECOND"],
         "IL-008": ["S1-VERIFRESET"], "IL-009": ["S1-XCUT"], "IL-010": ["S1-TRACESEC"]}
PENDING = "evidence/014-durable-local-autonomy/cross-inspection-20261102/"


@pytest.fixture(scope="module")
def rows():
    return {r["id"]: r for r in IL.load()}


def test_each_proposed_lesson_is_a_clean_detection_lesson_paired_with_its_seeded_defects(rows):
    known = {c["id"] for c in SD.CATALOGUE}
    for lid, cases in PAIRS.items():
        r = rows[lid]
        assert r["_state"] == "PROPOSED" and r["purpose"] == "DETECTION" and r["_reasons"] == [], (lid, r["_reasons"])
        assert r["must_still_detect"] == cases and set(cases) <= known
        assert all(x.startswith(PENDING) for x in r["pending_evidence_refs"])
        assert r["detection"]["real_misses"] and r["detection"]["certified_clean"]
        assert all(m["item"] in r["scope"]["items"] for m in r["detection"]["real_misses"])


def test_promotion_is_refused_until_the_pending_evidence_and_a_paired_trial_exist(rows):
    for lid in PAIRS:
        got = IL.detection_promotion_issues(rows[lid], [], [])
        assert any(x.startswith("PENDING_EVIDENCE_UNRESOLVED") for x in got)
        assert got[-1] == "NO_PAIRED_TRIAL_WITH_THIS_LESSON_VERSION"
        assert IL.promotion_issues(rows[lid], []) == ["DETECTION_LESSON_NEEDS_PAIRED_TRIAL"]


@pytest.mark.parametrize("item", ["SWE1-01", "SWE1-02", "SWE1-03", "SWE1-05", "SWE1-06"])
def test_proposed_lessons_are_not_retrieved_in_production_but_in_a_recorded_trial(item):
    present = {"workproducts/SWE.1/software_requirements.md", "traceability/upstream_gaps.md",
               "traceability/obligations_to_requirements.csv", "workproducts/SWE.1/register_effects.json"}
    assert IL.select("SWE.1", item, "LL", present) == []
    trial = [x["id"] for x in IL.select("SWE.1", item, "LL", present, include_proposed=True, token_budget=10_000)]
    assert trial == sorted(trial) and all(i in rows_for(item) for i in trial if i in PAIRS)


def rows_for(item):
    return [r["id"] for r in IL.load() if item in (r.get("scope") or {}).get("items", [])]


def test_the_hardware_precondition_lesson_agrees_with_the_low_level_failure_handling_lesson(rows):
    """IL-002 (LL: no failure-response requirements) and IL-007 share SWE1-03 for LL orders: IL-007 must not demand a
    failure response there."""
    st = rows["IL-007"]["statement"]
    assert "caller precondition is sufficient and no failure response is required" in st
    assert "LL" in rows["IL-002"]["scope"]["layers"] and "SWE1-03" in rows["IL-007"]["scope"]["items"]


def test_the_trace_section_lesson_is_marked_optional(rows):
    assert "deterministic trace-section check" in rows["IL-010"]["optional"]
