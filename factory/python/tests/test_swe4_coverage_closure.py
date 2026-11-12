"""Owner decisions 2026-11-03 (D/E): each uncovered line/branch/MC/DC condition gets a targeted closure test task
(the decision, its location, the missing outcome and the unit's USPEC items - never the code or expected values);
a gap no requirement or USPEC reaches is a CODE defect to SWE.3, never an invented requirement or oracle-less test."""
from __future__ import annotations

import json

import pytest
from forge_factory.inspection import uspec_plan
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe4
from test_lrtx_swe1 import _scripted, pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import ws1  # noqa: F401 - fixture
from test_lrtx_swe3 import ws2  # noqa: F401 - fixture
from test_lrtx_swe4 import TESTS, ws3  # noqa: F401 - fixture
from test_swe4_gtest import GTEST

pytestmark = [pytestmark, GTEST]
BRANCHES = ("    if (prescaler > 15U)\n    {\n        prescaler = 15U;\n    }\n"
            "    if (prescaler > 100U)\n    {\n        prescaler = 0U;\n    }\n")
REACH = {"verdict": "test", "reason": "USPEC-LL-05-01 confines the argument to the 4-bit field: a value above the "
         "field width is the corner case that takes this outcome", "verifies": ["USPEC-LL-05-01"], "kinds": ["boundary"],
         "code": "/** @test UT-010 @verifies USPEC-LL-05-01 */\nTEST(SWU_LL_05, UT_010)\n{\n    ut_reset_regs();\n"
                 "    LL_IWDG_SetPrescaler(0x1FU);\n"
                 "    EXPECT_EQ(ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U] & LL_IWDG_PR_PR_MSK, 0xFU);\n}"}
DEAD = {"verdict": "unreachable", "reason": "no requirement or USPEC item of SWU-LL-05 states a behaviour for an "
        "argument above 100 once it is confined to the field", "code": "", "verifies": [], "kinds": []}


def _seed(ws3):  # noqa: F811
    hdr = ws3 / "software/ll/stm32n6xx_ll_iwdg.h"
    t = hdr.read_text()
    i = t.index("static inline void LL_IWDG_SetPrescaler")
    j = t.index("{\n", i) + 2
    hdr.write_text(t[:j] + BRANCHES + t[j:])


def test_uncovered_decisions_get_closure_tasks_and_dead_code_a_code_defect(ws3, monkeypatch):  # noqa: F811
    _seed(ws3)
    calls = []
    monkeypatch.setattr(S, "call", _scripted({**TESTS, "test:UT-010": REACH, "test:UT-011": DEAD}, calls))
    rep = swe4.visit_tests(ws3, "m")
    closure = [p for p in calls if p["task"] in ("test:UT-010", "test:UT-011")]
    assert [p["task"] for p in closure] == ["test:UT-010", "test:UT-011"]
    text = json.dumps(closure[0]["_messages"])
    assert "prescaler > 15U" in text and "true outcome never taken" in text and "USPEC-LL-05-01" in text
    assert "reg &= ~LL_IWDG_PR_PR_MSK" not in text  # the decision only, never the code around it
    assert rep["status"] == "FAILED" and any(i.startswith("defect filed: DEF-") for i in rep["issues"]), rep
    d = json.loads(sorted((ws3 / ".forge-run/defects").glob("DEF-*.json"))[-1].read_text())
    assert d["kind"] == "CODE" and d["target_phase"] == "SWE.3" and "COVERAGE_UNREACHABLE" in d["summary"]
    assert "prescaler > 100U" in d["summary"] and d["requirement_ids"] == ["SWR-005"]
    plan = json.loads((ws3 / uspec_plan.PLAN).read_text())
    assert [c["ut"] for c in plan["closure"]] == ["UT-010"] and plan["closure"][0]["kind"] == "closure"
    assert plan["closure_unreachable"][0]["ut"] == "UT-011"
    assert "TEST(SWU_LL_05, UT_010)" in (ws3 / "software/tests/unit/test_iwdg.cpp").read_text()
    from forge_factory.lrtx import tools as T

    cov = T.call(ws3, "forge-tests-mcp", "llvm_coverage", {}, "swe4-author", "SWE.4")
    left = [g for g in swe4.coverage_gaps(ws3, cov) if g["kind"] == "branch"]
    assert [g["text"] for g in left] == ["prescaler > 100U"]  # the reachable one is closed by UT-010


def test_without_gaps_no_closure_task_is_made(ws3, monkeypatch):  # noqa: F811
    calls = []
    monkeypatch.setattr(S, "call", _scripted(TESTS, calls))
    assert swe4.visit_tests(ws3, "m")["status"] == "PASS"
    assert not [p for p in calls if p["task"] == "test:UT-010"]
    assert json.loads((ws3 / uspec_plan.PLAN).read_text())["closure"] == []


def test_closure_answer_validation(ws3):  # noqa: F811
    _seed(ws3)
    g = {"id": "GAP-x", "kind": "branch", "file": "software/ll/stm32n6xx_ll_iwdg.h", "line": 1, "col": 1,
         "function": "LL_IWDG_SetPrescaler", "text": "prescaler > 15U", "missing": "true outcome never taken",
         "lines": []}
    c = swe4._closure_case(ws3, g, "UT-010")
    assert c["uspecs"] == ["USPEC-LL-05-01"] and c["unit"]["id"] == "SWU-LL-05"
    assert swe4.validate_closure(ws3, REACH, c) == []
    assert swe4.validate_closure(ws3, DEAD, c) == []
    assert swe4.validate_closure(ws3, {**REACH, "verifies": ["USPEC-LL-01-01"]}, c)[0].startswith(
        "USPEC-LL-01-01 is not a USPEC item of SWU-LL-05")
    assert swe4.validate_closure(ws3, {**DEAD, "code": "x"}, c) == ["verdict unreachable takes code '' and verifies []"]


@pytest.mark.parametrize("purpose,kinds", [("ASPICE_ONLY", {"line", "branch"}),
                                           ("DEVELOPMENT", {"line", "branch", "mcdc"})])
def test_blocking_gap_kinds_follow_the_purpose(ws3, purpose, kinds):  # noqa: F811
    m = json.loads((ws3 / ".forge-run/manifest.json").read_text())
    m.pop("quality", None)  # the defaults of that purpose (no order-stated quality block)
    (ws3 / ".forge-run/manifest.json").write_text(json.dumps({**m, "purpose": purpose}))
    gaps = [{"kind": k, "function": "f"} for k in ("line", "branch", "mcdc")]
    cov = {"status": "PASS", "metrics": {"line_pct": 90.0, "branch_pct": 50.0, "mcdc_pct": 50.0, "uncovered": gaps}}
    assert {g["kind"] for g in swe4._blocking_gaps(ws3, cov)} == kinds


def test_below_target_but_at_the_order_minimum_progresses_with_the_shortfall_reported(ws3, monkeypatch):  # noqa: F811
    """Owner rule 2026-11-03: target 100, minimum 80 - closure works toward the target; when it cannot progress (the
    dead decision is a CODE defect) the visit passes at the minimum and the report shows the shortfall."""
    _seed(ws3)
    m = json.loads((ws3 / ".forge-run/manifest.json").read_text())
    pair = {"target": 100, "minimum": 80}
    m["quality"] = {"structural_coverage": {"line": pair, "branch": pair, "mcdc": pair},
                    "requirements_coverage": {"uspec_tested": {"target": 100, "minimum": 100},
                                              "swr_verified_swe6": {"target": 100, "minimum": 100}},
                    "misra": {"open_violations_max": 0, "undeviated_rules_max": 0, "deviation_owner_approval": True}}
    m["quality_source"] = "order"
    (ws3 / ".forge-run/manifest.json").write_text(json.dumps(m))
    monkeypatch.setattr(S, "call", _scripted({**TESTS, "test:UT-010": REACH, "test:UT-011": DEAD}, []))
    rep = swe4.visit_tests(ws3, "m")
    assert rep["status"] == "PASS", rep
    plan = json.loads((ws3 / uspec_plan.PLAN).read_text())
    st = plan["closure_status"]
    assert not st["target_met"] and st["below_minimum"] == [] and st["code_defects"]
    assert st["shortfall"] and all(s.startswith("COVERAGE_BELOW_TARGET:") for s in st["shortfall"])
    d = json.loads(sorted((ws3 / ".forge-run/defects").glob("DEF-*.json"))[-1].read_text())
    assert d["kind"] == "CODE" and "prescaler > 100U" in d["summary"]  # the reason the target was missed
    assert swe4.visit_report(ws3)["status"] == "PASS"
    rpt = (ws3 / "workproducts/SWE.4/unit_verification_report.md").read_text()
    assert "## Quality achieved vs target" in rpt and "BELOW_TARGET" in rpt and d["id"] in rpt
    assert "target NOT met" in rpt
