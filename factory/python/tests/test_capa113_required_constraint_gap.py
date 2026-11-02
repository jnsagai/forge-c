"""CAPA-113 (RPR-113): under a bound inspection assessment view, a recorded NOT_PROVIDED required constraint is an open
input gap that does not satisfy SWE1-04 (missing_required_constraint: OPEN_INPUT_GAP_NOT_SATISFIED), so the refuter no
longer withdraws a finding that the CPU/timing constraint is missing. What the view does allow stays refuted: the
recorded HSI or safety-allocation gap, an objection to the status of stated budgets, and every order without a view."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from forge_factory.inspection import assessment_context
from forge_factory.knowledge import inspection as IL
from forge_factory.lrtx import review
from forge_factory.release import aspice

CPU = ("No CPU constraint (e.g., maximum cycle count or instruction count per public API call) is stated in "
       "workproducts/SWE.1/software_requirements.md; the manifest records budgets.api_cycle_limits as PLACEHOLDER "
       "(not provided upstream).")
TIMING = ("Timing constraint missing: No measurable timing constraint is stated for the driver; the manifest's "
          "budgets.max_wait_polling_iterations remains NOT_PROVIDED.")
HSI = "The HSI contract is NOT_PROVIDED upstream and no requirement states the approved interface contract."
SAFETY = "The safety allocation is NOT_PROVIDED upstream: no software safety requirement is allocated."
STATUS = ("The flash, RAM and stack budgets are explicit and measurable. However, the upstream budget status is "
          "NOT_PROVIDED, so the budgets are not approved.")
GAPS = ("| Input | Status | SWR |\n| --- | --- | --- |\n| HSI contract | upstream.status: NOT_PROVIDED | SWR-001 |\n"
        "| Budgets | flash_bytes: 4096; upstream.status: NOT_PROVIDED | SWR-002 |\n")


def _ws(tmp: Path, bound: bool = True) -> Path:
    m = {"work_order": "WO-T", "scope": "driver", "layer": "LL", "target": {"safety_allocation": "NOT_ASSESSED"},
         "budgets": {"flash_bytes": 4096}, "upstream": {"status": "NOT_PROVIDED"}}
    if bound:
        m.update({"purpose": aspice.PURPOSE, "aspice_development": aspice.binding()})
        m[assessment_context.FIELD] = assessment_context.binding(m)
    (tmp / ".forge-run").mkdir()
    (tmp / ".forge-run/manifest.json").write_text(json.dumps(m))
    (tmp / "workproducts/SWE.1").mkdir(parents=True)
    (tmp / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-001** The driver shall not wait.\n  - Source: s\n  - Verification: Pass when it returns.\n"
        "- **SWR-002** The driver shall occupy at most 4096 bytes of flash.\n  - Source: b\n"
        "  - Verification: Pass when the size is at most 4096 bytes.\n")
    (tmp / "traceability").mkdir()
    (tmp / "traceability/upstream_gaps.md").write_text(GAPS)
    return tmp


def _refuted(ws: Path, f: str) -> bool:
    return any("recorded as NOT_PROVIDED" in x for x in review.fact_conflicts(ws, "SWE.1", "SWE1-04", [f]))


@pytest.mark.parametrize("finding", [CPU, TIMING])
def test_a_missing_required_constraint_is_not_refuted_by_its_recorded_gap(tmp_path, finding):
    ws = _ws(tmp_path)
    assert review.missing_constraint_not_satisfied(ws)
    assert not _refuted(ws, finding)


@pytest.mark.parametrize("finding", [HSI, SAFETY, STATUS])
def test_what_the_assessment_view_allows_stays_refuted(tmp_path, finding):
    assert _refuted(_ws(tmp_path), finding)


def test_an_order_without_an_assessment_view_is_unchanged(tmp_path):
    ws = _ws(tmp_path, bound=False)
    assert not review.missing_constraint_not_satisfied(ws)
    assert _refuted(ws, CPU) and _refuted(ws, TIMING)


def test_a_changed_binding_is_no_view(tmp_path):
    ws = _ws(tmp_path)
    p = ws / ".forge-run/manifest.json"
    m = json.loads(p.read_text())
    m["budgets"]["flash_bytes"] = 8192  # the bound scope changed after binding
    p.write_text(json.dumps(m))
    assert not review.missing_constraint_not_satisfied(ws) and _refuted(ws, CPU)


def test_il_004_is_retracted_with_the_assessment_context_as_reason():
    row = next(r for r in IL.load() if r["id"] == "IL-004")
    assert row["_state"] == "RETRACTED" and "OPEN_INPUT_GAP_NOT_SATISFIED" in row["retraction"]["reason"]
    assert all(x["id"] != "IL-004" for x in IL.select("SWE.1", "SWE1-04", "LL", {
        "workproducts/SWE.1/software_requirements.md", "traceability/upstream_gaps.md"}, include_proposed=True))
