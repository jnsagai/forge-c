"""SWE.6 Robot Framework requirement tests on the Renode STM32N6 model via forge-tests-mcp.run_robot."""
import os

import pytest
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import sim, tests
from test_sim_renode import HAL_C, HAL_H, LL

pytestmark = pytest.mark.skipif(sim.renode_bin() is None, reason="renode not installed")
SCN = ("#include \"stm32n6xx_hal_rcc.h\"\n#include \"forge_target_test.h\"\nFORGE_MAILBOX_DEFINE;\nint main(void)\n{\n"
       "    FORGE_TEST_BEGIN();\n    TCHECK(1, HAL_RCC_HSI_Enable(1000U) == HAL_OK);\n"
       "    TCHECK(2, (ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] & LL_RCC_CR_HSION_MSK) != 0U);\n"
       "    FORGE_TEST_END();\n    return 0;\n}\n")
SCN_TO = SCN.replace("== HAL_OK", "== HAL_TIMEOUT")
SUITE = """*** Settings ***
Library    ForgeTarget

*** Test Cases ***
SWR-001 HSI enable sets HSION and reports ready
    [Tags]    SWR-001
    Run Target Scenario    scn_hsi.c
    Target Check Should Pass    1
    Target Check Should Pass    2

SWR-002 HSI enable times out when never ready
    [Tags]    SWR-002
    Run Target Scenario    scn_hsi_timeout.c    scenario=never_ready
    All Target Checks Should Pass

SWR-003 Driver flash within budget
    [Tags]    SWR-003
    Driver Flash Size Should Be At Most    4096
"""
REQS = ("- **SWR-001** When HSI enable is requested, the RCC driver shall set RCC_CR.HSION.\n"
        "- **SWR-002** If HSIRDY is not set within the timeout, then the RCC driver shall return HAL_TIMEOUT.\n"
        "- **SWR-003** The RCC driver shall occupy at most 4096 bytes of flash.\n")


def run(tmp_path, monkeypatch, files):
    for rel, txt in {"software/ll/stm32n6xx_ll_rcc.h": LL, "software/hal/stm32n6xx_hal_rcc.h": HAL_H,
                     "software/hal/stm32n6xx_hal_rcc.c": HAL_C,
                     "workproducts/SWE.1/software_requirements.md": REQS, **files}.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(txt)
    for k, v in {"FORGE_MCP_TRUST": "env", "FORGE_WORKSPACE": str(tmp_path), "FORGE_EVENTS_DIR": str(tmp_path / ".ev"),
                 "FORGE_ROLE": "swe6-author", "FORGE_PHASE": "SWE.6"}.items():
        monkeypatch.setenv(k, v)
    os.environ["FORGE_ROLE"], os.environ["FORGE_PHASE"] = "swe6-author", "SWE.6"
    return sdk.invoke("forge-tests-mcp", next(o for o in tests.OPERATIONS if o.name == "run_robot"), {})


def test_robot_suite_verifies_every_requirement_on_target_model(tmp_path, monkeypatch):
    out = run(tmp_path, monkeypatch, {"software/tests/software/scn_hsi.c": SCN,
                                      "software/tests/software/scn_hsi_timeout.c": SCN_TO,
                                      "software/tests/software/test_rcc_requirements.robot": SUITE})
    assert out["status"] == "PASS", out
    assert out["metrics"]["tests"] == 3 and out["metrics"]["requirements_verified"] == 3
    assert (tmp_path / "build/robot/log.html").is_file() and (tmp_path / "build/robot/report.html").is_file()


def test_robot_fails_on_failing_test_and_uncovered_requirement(tmp_path, monkeypatch):
    suite = SUITE.replace("Run Target Scenario    scn_hsi.c\n", "Run Target Scenario    scn_hsi.c    scenario=never_ready\n")
    suite = suite[:suite.index("SWR-003 Driver")]  # SWR-003 no longer verified
    out = run(tmp_path, monkeypatch, {"software/tests/software/scn_hsi.c": SCN,
                                      "software/tests/software/scn_hsi_timeout.c": SCN_TO,
                                      "software/tests/software/test_rcc_requirements.robot": suite})
    assert out["status"] == "FAIL"
    assert any(i.startswith("ROBOT_FAIL:SWR-001") for i in out["issues"])
    assert "UNCOVERED_REQUIREMENT:SWR-001" in out["issues"] and "UNCOVERED_REQUIREMENT:SWR-003" in out["issues"]
