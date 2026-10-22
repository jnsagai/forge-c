"""Feature 010 P4: structured SWE.4 (LL) with a scripted model on top of the structured SWE.1-SWE.3 (frozen by the
unchanged gates): oracle-based unit tests, the real run_unit, deterministic report, the unchanged SWE.4 gate, and the
ADR-0008 rule that a failing correct test becomes a CODE defect instead of a bent test."""
from __future__ import annotations

import json

import pytest
from forge_factory.inspection import unit_scaffold
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe3, swe4
from forge_factory.workflow import scaffold
from test_lrtx_swe1 import _scripted, pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import ws1  # noqa: F401 - fixture
from test_lrtx_swe3 import CODE, TOOLS, _gate, ws2  # noqa: F401 - fixture

pytestmark = [pytestmark, pytest.mark.skipif(not TOOLS, reason="build tools not installed")]


def _t(ut, spec, body):
    name = "ut_" + ut.lower().replace("-", "_")
    return {"code": f"/** @test {ut} @verifies {spec} */\nstatic void {name}(void)\n{{\n    ut_reset_regs();\n{body}\n}}"}


TESTS = {
    "test:UT-001": _t("UT-001", "USPEC-LL-01-01", '    LL_IWDG_Enable();\n    CHECK("UT-001", (ll_iwdg_regs[LL_IWDG_KR_OFFSET '
                      '/ 4U] & LL_IWDG_KR_KEY_MSK) == 0x0000CCCCU);'),
    "test:UT-002": _t("UT-002", "USPEC-LL-02-01", '    LL_IWDG_ReloadCounter();\n    CHECK("UT-002", (ll_iwdg_regs['
                      'LL_IWDG_KR_OFFSET / 4U] & LL_IWDG_KR_KEY_MSK) == 0x0000AAAAU);'),
    "test:UT-003": _t("UT-003", "USPEC-LL-03-01", '    LL_IWDG_EnableWriteAccess();\n    CHECK("UT-003", (ll_iwdg_regs['
                      'LL_IWDG_KR_OFFSET / 4U] & LL_IWDG_KR_KEY_MSK) == 0x00005555U);'),
    "test:UT-004": _t("UT-004", "USPEC-LL-04-01", '    ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = 0x5555U;\n'
                      '    LL_IWDG_DisableWriteAccess();\n    CHECK("UT-004", (ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] & '
                      'LL_IWDG_KR_KEY_MSK) == 0U);'),
    "test:UT-005": _t("UT-005", "USPEC-LL-05-01", '    ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U] = 0xFFFFFFF0U;\n'
                      '    LL_IWDG_SetPrescaler(5U);\n    CHECK("UT-005", ((ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U] & '
                      'LL_IWDG_PR_PR_MSK) == 5U) && ((ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U] & '
                      '~LL_IWDG_PR_PR_MSK) == 0xFFFFFFF0U));'),
    "test:UT-006": _t("UT-006", "USPEC-LL-06-01", '    LL_IWDG_SetReloadCounter(0xFFFU);\n    CHECK("UT-006", ('
                      'll_iwdg_regs[LL_IWDG_RLR_OFFSET / 4U] & LL_IWDG_RLR_RL_MSK) == 0xFFFU);'),
    "test:UT-007": _t("UT-007", "USPEC-LL-07-01", '    uint32_t clear = LL_IWDG_IsActive();\n    uint32_t set;\n    '
                      'll_iwdg_regs[LL_IWDG_SR_OFFSET / 4U] = LL_IWDG_SR_ONF_MSK;\n    set = LL_IWDG_IsActive();\n    '
                      'CHECK("UT-007", (clear == 0U) && (set == 1U));'),
    "test:UT-008": _t("UT-008", "USPEC-LL-08-01", '    uint32_t clear = LL_IWDG_IsActiveFlag_PVU();\n    uint32_t set;\n    '
                      'll_iwdg_regs[LL_IWDG_SR_OFFSET / 4U] = LL_IWDG_SR_PVU_MSK;\n    set = LL_IWDG_IsActiveFlag_PVU();\n    '
                      'CHECK("UT-008", (clear == 0U) && (set == 1U));'),
    "test:UT-009": _t("UT-009", "USPEC-LL-09-01", '    uint32_t clear = LL_IWDG_IsActiveFlag_RVU();\n    uint32_t set;\n    '
                      'll_iwdg_regs[LL_IWDG_SR_OFFSET / 4U] = LL_IWDG_SR_RVU_MSK;\n    set = LL_IWDG_IsActiveFlag_RVU();\n    '
                      'CHECK("UT-009", (clear == 0U) && (set == 1U));')}


@pytest.fixture()
def ws3(ws2, monkeypatch):  # noqa: F811
    monkeypatch.setattr(S, "call", _scripted(CODE, []))
    assert swe3.visit_code(ws2, "m")["status"] == "PASS"
    unit_scaffold.scaffold(ws2)
    assert swe3.visit_design(ws2)["status"] == "PASS" and _gate(ws2, "SWE.3", monkeypatch) == 0
    scaffold.scaffold(ws2)
    return ws2


def test_oracle_tests_pass_run_unit_and_the_unchanged_swe4_gate(ws3, monkeypatch):
    calls = []
    monkeypatch.setattr(S, "call", _scripted(TESTS, calls))
    rep = swe4.visit_tests(ws3, "m")
    assert rep["status"] == "PASS", rep
    assert all("ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = 0x0000CCCCU" not in json.dumps(p["_messages"]) for p in calls)
    assert swe4.visit_report(ws3)["status"] == "PASS"
    rpt = (ws3 / "workproducts/SWE.4/unit_verification_report.md").read_text()
    assert "## Coverage" in rpt and "| UT-005 | LL_IWDG_SetPrescaler | SWR-005 |" in rpt
    assert _gate(ws3, "SWE.4", monkeypatch) == 0


def test_a_correct_failing_test_files_a_code_defect_not_a_bent_test(ws3, monkeypatch):
    hdr = ws3 / "software/ll/stm32n6xx_ll_iwdg.h"
    hdr.write_text(hdr.read_text().replace("= 0x0000AAAAU;", "= 0x0000AAABU;"))  # seeded implementation defect
    triage = {"verdict": "code_defect", "code": "", "reason": "SWR-002 requires 0x0000AAAA in IWDG_KR.KEY; the "
              "implementation writes 0x0000AAAB"}
    calls = []
    monkeypatch.setattr(S, "call", _scripted({**TESTS, "triage:UT-002": triage}, calls))
    rep = swe4.visit_tests(ws3, "m")
    assert rep["status"] == "FAILED" and any("defect filed: DEF-" in i for i in rep["issues"])
    d = json.loads(sorted((ws3 / ".forge-run/defects").glob("DEF-*.json"))[-1].read_text())
    assert d["kind"] == "CODE" and d["target_phase"] == "SWE.3" and d["requirement_ids"] == ["SWR-002"]
    assert "0x0000AAAAU" in (ws3 / "software/tests/unit/test_iwdg.c").read_text()  # the test was not bent
