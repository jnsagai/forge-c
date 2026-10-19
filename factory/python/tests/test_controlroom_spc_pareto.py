"""CR-T022: SPC limits against hand-computed references, run rules, minimum samples; Pareto normalisation and order."""
import json
import math

from controlroom_fixtures import CFG, inspect, passed, rejected, route, workspace
from forge_factory.controlroom.pareto import History, block_code
from forge_factory.controlroom.spc import i_mr, p_chart

SPC = {"min_subgroups": 3, "min_n": 10, "min_points": 4, "rules": ["WE1", "WE2", "WE3"]}


def test_p_chart_variable_limits_match_the_formula():
    g = [{"t": "d1", "passes": 4, "n": 5}, {"t": "d2", "passes": 2, "n": 4}, {"t": "d3", "passes": 5, "n": 6}]
    c = p_chart(g, SPC)
    p = 11 / 15
    assert c["status"] == "OK" and math.isclose(c["center"], round(p, 6))
    assert math.isclose(c["ucl"][0], round(min(1, p + 3 * math.sqrt(p * (1 - p) / 5)), 6))
    assert math.isclose(c["lcl"][1], round(max(0, p - 3 * math.sqrt(p * (1 - p) / 4)), 6))


def test_p_chart_insufficient_data_draws_no_limits():
    c = p_chart([{"t": "d1", "passes": 1, "n": 2}], SPC)
    assert c["status"] == "INSUFFICIENT_DATA" and c["ucl"] is None and c["minimum"] == {"subgroups": 3, "n": 10}


def test_i_mr_limits_and_clipping():
    pts = [{"t": str(i), "value": v} for i, v in enumerate([10, 12, 11, 13, 50])]
    c = i_mr(pts, SPC)
    xbar, mr = 96 / 5, (2 + 1 + 2 + 37) / 4
    assert math.isclose(c["center"], round(xbar, 3)) and math.isclose(c["ucl"], round(xbar + 2.66 * mr, 3))
    assert c["lcl"] == 0.0 and c["lcl_clipped_at_zero"] is True
    assert i_mr(pts[:3], SPC)["status"] == "INSUFFICIENT_DATA"


def test_run_rules():
    spc = {**SPC, "min_points": 2}
    flat = [{"t": str(i), "value": v} for i, v in enumerate([5] * 10 + [100])]
    assert any(v["rule"] == "WE1" and v["point_index"] == 10 for v in i_mr(flat, spc)["violations"])
    trend = [{"t": str(i), "value": float(v)} for i, v in enumerate([1, 2, 3, 4, 5, 6, 7])]
    assert any(v["rule"] == "WE3" for v in i_mr(trend, spc)["violations"])
    side = [{"t": str(i), "value": v} for i, v in enumerate([1] * 9 + [10] * 9)]
    assert any(v["rule"] == "WE2" for v in i_mr(side, spc)["violations"])


def test_loss_code_keeps_the_category_code_and_the_tool_or_output():
    from forge_factory.controlroom.floor import code

    assert code("CODE:DOXYGEN_WARNING:software/ll/x.h:14: warning: y") == "CODE:DOXYGEN_WARNING"
    assert code("UNIT:SWR_NOT_REFINED:SWR-020 (allocated)") == "UNIT:SWR_NOT_REFINED"
    assert code("REQUIRED_TOOL_NOT_PASS:run_unit:FAIL") == "REQUIRED_TOOL_NOT_PASS:run_unit"
    assert code("MISSING_REQUIRED_OUTPUT:workproducts/SWE.4/unit_verification_report.md") == \
        "MISSING_REQUIRED_OUTPUT:unit_verification_report.md"
    assert code("CONTRACT_SWR_NOT_COVERED:SWR-005 (it sets)") == "CONTRACT_SWR_NOT_COVERED"


def test_block_code_normalisation():
    assert block_code({"step": "route", "gate": {"decision": "BLOCKED", "reason": "rework budget exhausted (4 failed cycles)"}}) \
        == "rework budget exhausted (N failed cycles)"
    assert block_code({"step": "route", "gate": {"decision": "BLOCKED", "reason": "STUCK: identical x"}}).startswith("STUCK")


def test_pareto_counts_order_shares_and_inspection_findings(tmp_path):
    root = tmp_path / "wo"
    a = workspace(root, "WO-A-r1", [rejected("SWE.2", 1), rejected("SWE.2", 3), route("SWE.2", 4),
                                    rejected("SWE.2", 5, "ARCH_IRQ_OWNER_MISSING:x"), inspect("SWE.3", 9, "REWORK")])
    (a / "inspection/SWE.3").mkdir(parents=True)
    (a / "inspection/SWE.3/INS-SWE.3-001.json").write_text(json.dumps({"findings": [
        {"id": "SWE3-04", "severity": "major"}, {"id": "SWE3-09", "severity": "minor"}]}))
    workspace(root, "WO-B-r1", [rejected("SWE.2", 2), route("SWE.2", 6, "BLOCKED", "rework budget exhausted (3 failed cycles)")])
    h = History(root=root)
    pa = h.pareto("2026-10-19T00:00:00Z", "2026-10-20T00:00:00Z")
    assert [(x["station"], x["kind"], x["reason_code"], x["count"]) for x in pa[:2]] == [
        ("SWE.2", "REJECTED", "CONTRACT_SWR_NOT_COVERED", 3), ("SWE.2", "BLOCKED", "rework budget exhausted (N failed cycles)", 1)]
    assert pa[-1]["cumulative_share"] == 1.0 and {x["reason_code"] for x in pa} >= {"SWE3-04", "ARCH_IRQ_OWNER_MISSING"}
    assert "SWE3-09" not in {x["reason_code"] for x in pa}                       # minor findings are not losses
    assert pa[0]["refs"][0] == {"work_order": "WO-A-r1", "line": 1}
    assert [x["reason_code"] for x in h.pareto("2026-10-19T00:00:00Z", "2026-10-20T00:00:00Z", "SWE.3")] == ["SWE3-04"]


def test_first_pass_groups_and_time_to_pass(tmp_path):
    root = tmp_path / "wo"
    workspace(root, "WO-A-r1", [*passed("SWE.1", 0), *passed("SWE.2", 10)])
    workspace(root, "WO-B-r1", [*passed("SWE.1", 0), inspect("SWE.2", 20, "REWORK"), *passed("SWE.2", 30)])
    h = History(root=root)
    g = h.first_pass_groups("2026-10-19T00:00:00Z", "2026-10-20T00:00:00Z", "SWE.2", CFG["tz"])
    assert g == [{"t": "2026-10-19", "passes": 1, "n": 2, "units": ["WO-A-r1", "WO-B-r1"]}]
    tp = {p["units"][0]: p["value"] for p in h.time_to_pass("2026-10-19T00:00:00Z", "2026-10-20T00:00:00Z", "SWE.2")}
    assert tp == {"WO-A-r1": 600.0, "WO-B-r1": 1800.0}                      # from the SWE.1 pass (minute 1)
