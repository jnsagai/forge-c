"""Owner decision 2026-11-03 (C): 100% line and branch coverage of the scoped driver code is a BLOCKING SWE.4 gate;
100% MC/DC is additionally blocking for a safety work-order purpose; 'not applicable' (llvm-cov counts nothing)
stays acceptable. Work orders without unit_verification keep the reported goal."""
from __future__ import annotations

import json

import pytest
from forge_factory.inspection import coverage_gate as CG
from forge_factory.layer import UNIT_VERIFICATION


def _ws(tmp_path, purpose, flag=True):
    (tmp_path / ".forge-run").mkdir(parents=True, exist_ok=True)
    m = {"purpose": purpose, **({"unit_verification": UNIT_VERIFICATION} if flag else {})}
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps(m))
    return tmp_path


def _cov(line, branch, mcdc, status="PASS"):
    return {"status": status, "metrics": {"line_pct": line, "branch_pct": branch, "mcdc_pct": mcdc}}


@pytest.mark.parametrize("purpose,mcdc", [("ASPICE_ONLY", False), ("QM", False), ("DEVELOPMENT", True),
                                          ("FORMAL_REVIEW", True)])
def test_measures_follow_the_work_order_purpose(tmp_path, purpose, mcdc):
    r = CG.required(_ws(tmp_path, purpose))
    assert r["mcdc"] is mcdc and [m for m, _k in r["measures"]][:2] == ["line", "branch"]


def test_unknown_purpose_is_refused_not_guessed(tmp_path):
    with pytest.raises(ValueError, match="COVERAGE_GATE_PURPOSE_UNKNOWN"):
        CG.required(_ws(tmp_path, None))
    assert CG.findings(_ws(tmp_path, "SOMETHING")) == ["COVERAGE_GATE_PURPOSE_UNKNOWN:SOMETHING"]


def test_aspice_only_blocks_line_and_branch_and_reports_mcdc(tmp_path):
    ws = _ws(tmp_path, "ASPICE_ONLY")
    assert CG.evaluate(ws, _cov(100.0, 100.0, 50.0))["status"] == "PASS"  # MC/DC reported, not blocking
    ev = CG.evaluate(ws, _cov(100.0, 75.0, 100.0))
    assert ev["status"] == "FAIL" and ev["findings"][0].startswith("COVERAGE_GATE:BRANCH_NOT_100:75.0%")
    assert CG.evaluate(ws, _cov(96.5, 100.0, None))["findings"][0].startswith("COVERAGE_GATE:LINE_NOT_100:96.5%")


def test_safety_purpose_also_blocks_mcdc(tmp_path):
    ws = _ws(tmp_path, "DEVELOPMENT")
    ev = CG.evaluate(ws, _cov(100.0, 100.0, 50.0))
    assert ev["status"] == "FAIL" and ev["findings"][0].startswith("COVERAGE_GATE:MCDC_NOT_100:50.0%")


def test_not_applicable_stays_acceptable(tmp_path):
    for purpose in ("ASPICE_ONLY", "DEVELOPMENT"):
        ev = CG.evaluate(_ws(tmp_path, purpose), _cov(100.0, None, None))
        assert ev["status"] == "PASS" and {r["status"] for r in ev["rows"]} >= {"NOT_APPLICABLE"}


def test_unmeasured_and_stale_coverage_block(tmp_path):
    ws = _ws(tmp_path, "ASPICE_ONLY")
    assert CG.evaluate(ws, _cov(100.0, 100.0, 100.0, status="BLOCKED"))["findings"][0].startswith(
        "COVERAGE_GATE:NOT_MEASURED")
    assert CG.findings(ws) == ["COVERAGE_GATE:NOT_MEASURED (llvm_coverage NOT_RUN)"]
    (ws / "evidence").mkdir()
    recs = [{"server": "forge-tests-mcp", "op": "llvm_coverage", "ts_utc": "2026-11-03T01:00:00Z",
             "result": _cov(100.0, 100.0, 100.0)},
            {"server": "forge-tests-mcp", "op": "run_unit", "ts_utc": "2026-11-03T02:00:00Z", "result": {"status": "PASS"}}]
    (ws / "evidence/tool-results.jsonl").write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    assert CG.findings(ws)[0].startswith("COVERAGE_GATE:STALE")


def test_older_work_orders_keep_the_reported_goal(tmp_path):
    assert CG.findings(_ws(tmp_path, "ASPICE_ONLY", flag=False)) == []


def test_brownfield_scope_measures_are_used(tmp_path):
    ws = _ws(tmp_path, "ASPICE_ONLY")
    cov = {"status": "PASS", "metrics": {"line_pct": 1.2, "branch_pct": 3.0, "mcdc_pct": None, "scope_functions": 4,
                                         "scope_region_pct": 100.0, "scope_branch_pct": 100.0}}
    assert CG.evaluate(ws, cov)["status"] == "PASS"
