"""CAPA-094 (run WO-F014-SWE4-OBL-20261101-L2, SWE4-05): straight-line LL code has no branch points, llvm-cov reports
branch None%; the SWE.4 report states each coverage measure as met, not met (a finding) or not applicable."""
from forge_factory.lrtx import swe4


def test_a_measure_without_branch_points_is_not_applicable_and_a_shortfall_is_a_finding():
    lines, gaps = swe4._coverage({"metrics": {"line_pct": 100.0, "branch_pct": None, "mcdc_pct": None}})
    assert lines[0] == "- statement/line: 100.0% - goal met" and gaps == []
    assert "branch: not applicable - llvm-cov counted no branch points" in lines[1]
    assert "MC/DC: not applicable" in lines[2]
    lines, gaps = swe4._coverage({"metrics": {"line_pct": 92.5, "branch_pct": 50.0, "mcdc_pct": None}})
    assert gaps == ["COVERAGE_GOAL_NOT_MET: statement/line 92.5% (< 100%)", "COVERAGE_GOAL_NOT_MET: branch 50.0% (< 100%)"]
