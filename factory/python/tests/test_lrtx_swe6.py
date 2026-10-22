"""Feature 010 P4: structured SWE.6 (LL) with a scripted model on top of the structured SWE.1-SWE.5: target scenario
programs per SWE.1 register group, budget keywords rendered, the real run_robot on Renode, the deterministic report and
the unchanged SWE.6 gate."""
from __future__ import annotations

import pytest
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe4, swe5, swe6
from forge_factory.workflow import robot_scaffold
from test_lrtx_swe1 import _scripted, pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import ws1  # noqa: F401 - fixture
from test_lrtx_swe3 import TOOLS, _gate, ws2  # noqa: F401 - fixture
from test_lrtx_swe4 import TESTS, ws3  # noqa: F401 - fixture
from test_lrtx_swe5 import FILES

pytestmark = [pytestmark, pytest.mark.skipif(not TOOLS, reason="build tools not installed")]
HEAD = '#include "stm32n6xx_ll_iwdg.h"\n#include "forge_target_test.h"\n\nFORGE_MAILBOX_DEFINE;\n\nint main(void)\n{\n'
TAIL = "    FORGE_TEST_END();\n    return 0;\n}\n"


def _prog(body):
    return HEAD + "    FORGE_TEST_BEGIN();\n" + body + TAIL


R = "ll_iwdg_regs[LL_IWDG_{0}_OFFSET / 4U] & LL_IWDG_{0}_{1}_MSK"
SCN = {
    "scenario:iwdg_kr": {"default_code": _prog(
        "    LL_IWDG_EnableWriteAccess();\n    LL_IWDG_SetPrescaler(4U);\n"
        f"    TCHECK(3, (({R.format('KR', 'KEY')}) == 0U) && (({R.format('PR', 'PR')}) == 4U));\n"
        "    LL_IWDG_DisableWriteAccess();\n"
        f"    LL_IWDG_SetPrescaler(6U);\n    TCHECK(4, (({R.format('KR', 'KEY')}) == 0U) && (({R.format('PR', 'PR')}) == 4U));\n"
        f"    LL_IWDG_Enable();\n    TCHECK(1, (({R.format('KR', 'KEY')}) == 0U) && (LL_IWDG_IsActive() == 1U));\n"
        "    LL_IWDG_ReloadCounter();\n"
        f"    TCHECK(2, (({R.format('KR', 'KEY')}) == 0U) && (LL_IWDG_IsActive() == 1U));\n"), "never_ready_code": "", "never_ready_swrs": []},
    "scenario:iwdg_pr": {"default_code": _prog(
        f"    LL_IWDG_EnableWriteAccess();\n    LL_IWDG_SetPrescaler(5U);\n    TCHECK(5, ({R.format('PR', 'PR')}) == 5U);\n"),
        "never_ready_code": "", "never_ready_swrs": []},
    "scenario:iwdg_rlr": {"default_code": _prog(
        f"    LL_IWDG_EnableWriteAccess();\n    LL_IWDG_SetReloadCounter(0xABCU);\n"
        f"    TCHECK(6, ({R.format('RLR', 'RL')}) == 0xABCU);\n"), "never_ready_code": "", "never_ready_swrs": []},
    "scenario:iwdg_sr_1": {"default_code": _prog("    LL_IWDG_Enable();\n    TCHECK(7, (LL_IWDG_IsActive() == 1U) && "
                                                 f"(({R.format('SR', 'ONF')}) != 0U));\n"),
                           "never_ready_code": "", "never_ready_swrs": []},
    "scenario:iwdg_sr_2": {"default_code": _prog(f"    TCHECK(8, (LL_IWDG_IsActiveFlag_PVU() == 0U) && "
                                                 f"(({R.format('SR', 'PVU')}) == 0U));\n"),
                           "never_ready_code": _prog(
                               "    LL_IWDG_EnableWriteAccess();\n    LL_IWDG_SetReloadCounter(0x100U);\n"
                               f"    TCHECK(9, (LL_IWDG_IsActiveFlag_RVU() == 1U) && (({R.format('SR', 'RVU')}) != 0U));\n"),
                           "never_ready_swrs": ["SWR-009"]},
    "scenario:startup": {"default_code": _prog(f"    TCHECK(10, (({R.format('PR', 'PR')}) == 0U) && "
                                               f"(({R.format('RLR', 'RL')}) == 0xFFFU));\n"),
                         "never_ready_code": "", "never_ready_swrs": []}}


def test_structured_swe6_passes_robot_on_renode_and_the_unchanged_gate(ws3, monkeypatch):  # noqa: F811
    monkeypatch.setattr(S, "call", _scripted(TESTS, []))
    assert swe4.visit(ws3, "m")["status"] == "PASS" and _gate(ws3, "SWE.4", monkeypatch) == 0
    monkeypatch.setattr(S, "call", _scripted(FILES, []))
    assert swe5.visit(ws3, "m")["status"] == "PASS" and _gate(ws3, "SWE.5", monkeypatch) == 0
    robot_scaffold.scaffold(ws3)
    pl = swe6.plan(ws3)
    assert pl["budgets"] == {"SWR-011": "Driver Flash Size Should Be At Most    4096",
                             "SWR-012": "Driver Static RAM Should Be At Most    64",
                             "SWR-013": "Driver Stack Should Be At Most    128"}
    assert pl["topics"]["startup"] == ["SWR-010"]
    monkeypatch.setattr(S, "call", _scripted(SCN, []))
    rep = swe6.visit(ws3, "m")
    assert rep["status"] == "PASS", rep
    suite = (ws3 / robot_scaffold.suite(ws3)).read_text()
    assert "Fail    NOT IMPLEMENTED:" not in suite and "scn_iwdg_sr_2_pending.c    scenario=never_ready" in suite
    assert _gate(ws3, "SWE.6", monkeypatch) == 0


def test_scenario_validation_needs_exactly_one_check_per_requirement_naming_its_field(ws3):  # noqa: F811
    blind = {**SCN["scenario:iwdg_sr_1"], "default_code": _prog("    LL_IWDG_Enable();\n    TCHECK(7, LL_IWDG_IsActive() == 1U);\n")}
    assert swe6.validate_scenarios(ws3, blind, ["SWR-007"]) == [
        "TCHECK(7) must name LL_IWDG_SR_ONF_MSK (SWR-007 names that field)"]
    doc = {**SCN["scenario:iwdg_sr_2"], "never_ready_swrs": []}
    found = " ".join(swe6.validate_scenarios(ws3, {**doc, "default_code": doc["default_code"].replace("TCHECK(8", "TCHECK(12")},
                                             ["SWR-008", "SWR-009"]))
    assert "TCHECK(12) is not a requirement number" in found and "SWR-008 has no TCHECK(8)" in found
