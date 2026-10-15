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
    # r64: the failing check's expression is in the result, so the author can decide without reading files
    assert "CHECK_EXPR:scn_hsi.c#1:HAL_RCC_HSI_Enable(1000U) == HAL_OK" in out["issues"], out["issues"]
    # ADR-0008 test-integrity record: the scenario with failing checks (runtime, not a build error) is recorded
    import json as _json

    rec = _json.loads((tmp_path / "evidence/test-integrity.jsonl").read_text().splitlines()[-1])
    assert rec["op"] == "run_robot" and rec["status"] == "FAIL" and rec["phase"] == "SWE.6"
    assert rec["assert_failed"] == ["software/tests/software/scn_hsi.c"]
    assert "software/tests/software/test_rcc_requirements.robot" in rec["files"]


def test_robot_policy_rejects_suites_that_could_run_arbitrary_code(tmp_path):
    """r57: the SWE.6 author imported Process and ran a shell script - a bypass of its MCP-only grant."""
    from forge_factory.mcp.servers.robot_policy import check_suite

    ok = tmp_path / "ok.robot"
    ok.write_text(SUITE.replace("*** Test Cases ***", "*** Keywords ***\nCheck HSI\n    Run Target Scenario    scn_hsi.c"
                                "\n    Log    done\n\n*** Test Cases ***\nSWR-009 uses a local keyword\n    Check HSI\n"))
    assert check_suite(ok) == []
    bad = {
        "LIBRARY_NOT_ALLOWED": "*** Settings ***\nLibrary    Process\n\n*** Test Cases ***\nT\n    Run Process    ls\n",
        "RESOURCE_IMPORT": "*** Settings ***\nResource    x.resource\n\n*** Test Cases ***\nT\n    Log    x\n",
        "VARIABLES_IMPORT": "*** Settings ***\nVariables    vars.py\n\n*** Test Cases ***\nT\n    Log    x\n",
        "INLINE_PYTHON": "*** Test Cases ***\nT\n    Log    ${{__import__('os').getcwd()}}\n",
        "KEYWORD_NOT_ALLOWED": "*** Test Cases ***\nT\n    Evaluate    __import__('os').system('id')\n",
        "DYNAMIC_KEYWORD": "*** Test Cases ***\nT\n    Run ${what} Scenario    a\n",
    }
    for code, text in bad.items():
        p = tmp_path / f"{code}.robot"
        p.write_text(text)
        assert any(code in i for i in check_suite(p)), (code, check_suite(p))
    for kw in ("Import Library    Process", "Run Keyword    Log    x", "Should Be True    1", "BuiltIn.Evaluate    1"):
        p = tmp_path / "k.robot"
        p.write_text(f"*** Test Cases ***\nT\n    {kw}\n")
        assert any("KEYWORD_NOT_ALLOWED" in i for i in check_suite(p)), kw
    p = tmp_path / "s.robot"
    p.write_text("*** Settings ***\nSuite Setup    Evaluate    1\n\n*** Test Cases ***\nT\n    [Teardown]    Run Process"
                 "    ls\n    Log    x\n")
    assert len([i for i in check_suite(p) if "KEYWORD_NOT_ALLOWED" in i]) == 2


def test_run_robot_refuses_policy_violation_before_running(tmp_path, monkeypatch):
    marker = tmp_path / "pwned"
    out = run(tmp_path, monkeypatch, {"software/tests/software/test_rcc_requirements.robot":
                                      f"*** Settings ***\nLibrary    OperatingSystem\n\n*** Test Cases ***\nSWR-001 x\n"
                                      f"    [Tags]    SWR-001\n    Create File    {marker}    x\n"})
    assert out["status"] == "FAIL" and any("LIBRARY_NOT_ALLOWED:OperatingSystem" in i for i in out["issues"])
    assert not marker.exists() and not (tmp_path / "build/robot").exists()


def test_robot_scaffold_one_tagged_placeholder_per_requirement_never_passes(tmp_path, monkeypatch):
    """r59: suite skeleton generated from SWE.1; placeholders fail, so only authored target checks can pass."""
    from forge_factory.mcp.servers.robot_policy import check_suite
    from forge_factory.workflow.robot_scaffold import SUITE as SUITE_PATH
    from forge_factory.workflow.robot_scaffold import scaffold

    (tmp_path / "workproducts/SWE.1").mkdir(parents=True)
    (tmp_path / "workproducts/SWE.1/software_requirements.md").write_text(
        REQS + "- **SWR-004** If ${x} & @{y} appear, then the RCC driver shall not break the suite.\n")
    out = scaffold(tmp_path)
    assert out["created"] and out["test_cases"] == 4
    suite = (tmp_path / SUITE_PATH).read_text()
    assert check_suite(tmp_path / SUITE_PATH) == [] and "${" not in suite and "@{" not in suite
    for i in range(1, 5):
        assert f"[Tags]    SWR-00{i}" in suite
    (tmp_path / SUITE_PATH).write_text(suite + "# authored\n")
    assert scaffold(tmp_path)["created"] is False and "# authored" in (tmp_path / SUITE_PATH).read_text()
    (tmp_path / SUITE_PATH).write_text(suite)
    r = run(tmp_path, monkeypatch, {})
    assert r["status"] == "FAIL" and r["metrics"]["passed"] == 0 and r["metrics"]["tests"] == 4, r


def test_requirement_must_be_observed_by_its_tagged_checks_r63(tmp_path):
    """r60/r63: SWR-014 ('shall return HAL_ERROR ...') was tagged on checks that never mention HAL_ERROR."""
    from forge_factory.mcp.servers.robot_policy import unobserved_requirements

    (tmp_path / "scn_param.c").write_text(
        "int main(void) {\n    TCHECK(9, ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] == cr_before);\n"
        "    TCHECK(10, HAL_RCC_PeriphClock_Enable(99U) == HAL_ERROR);\n"
        "    TCHECK(i + 1U, (ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] & LL_RCC_CR_HSION_MSK) != 0U);\n}\n")
    reqs = {"SWR-014": "If a parameter is invalid, then the RCC driver shall return HAL_ERROR without any register write.",
            "SWR-001": "When HSI enable is requested, the RCC driver shall set RCC_CR.HSION.",
            "SWR-016": "The RCC driver shall occupy at most 4096 bytes of flash."}
    suite = tmp_path / "s.robot"
    suite.write_text("*** Settings ***\nLibrary    ForgeTarget\n\n*** Test Cases ***\nSWR-014 vacuous\n    [Tags]    SWR-014\n"
                     "    Run Target Scenario    scn_param.c\n    Target Check Should Pass    9\n\n"
                     "SWR-001\n    [Tags]    SWR-001\n    Check HSI    scn_param.c\n\n"
                     "SWR-016\n    [Tags]    SWR-016\n    Driver Flash Size Should Be At Most    4096\n\n"
                     "*** Keywords ***\nCheck HSI\n    [Arguments]    ${scn}\n    Run Target Scenario    ${scn}\n"
                     "    All Target Checks Should Pass\n")
    out = unobserved_requirements(suite, tmp_path, reqs)
    assert out[0].startswith("HOW_TO_OBSERVE:") and len(out[0]) <= 120  # r65: actionable, within the issue cap
    assert out[1:] == ["REQUIREMENT_NOT_OBSERVED:SWR-014:needs TCHECK on HAL_ERROR in scn_param.c"]
    suite.write_text(suite.read_text().replace("Target Check Should Pass    9\n",
                                               "Target Check Should Pass    9\n    Target Check Should Pass    10\n"))
    assert unobserved_requirements(suite, tmp_path, reqs) == []  # check 10 observes HAL_ERROR


def test_build_failures_come_first_once_per_scenario_with_compiler_hint_r67(tmp_path, monkeypatch):
    """r67: build errors were cut from the capped result behind observability lines; authors never saw them."""
    bad = SCN.replace("LL_RCC_CR_HSION_MSK", "LL_RCC_CR_HSION")
    suite = SUITE.replace("Run Target Scenario    scn_hsi_timeout.c", "Run Target Scenario    scn_hsi.c")
    out = run(tmp_path, monkeypatch, {"software/tests/software/scn_hsi.c": bad,
                                      "software/tests/software/test_rcc_requirements.robot": suite})
    assert out["status"] == "FAIL"
    first = out["issues"][0]
    assert first.startswith("BUILD_FAIL:scn_hsi.c:") and "LL_RCC_CR_HSION" in first, out["issues"]
    assert sum(1 for i in out["issues"] if i.startswith("BUILD_FAIL:")) == 1  # one line per scenario
    assert not any(i.startswith(("REQUIREMENT_NOT_OBSERVED", "HOW_TO_OBSERVE")) for i in out["issues"])


def test_check_expr_shows_the_call_that_set_the_checked_variable_r68(tmp_path, monkeypatch):
    scn = ("#include \"stm32n6xx_hal_rcc.h\"\n#include \"forge_target_test.h\"\nFORGE_MAILBOX_DEFINE;\nint main(void)\n{\n"
           "    int st;\n    FORGE_TEST_BEGIN();\n    st = HAL_RCC_HSI_Enable(1000U);\n    TCHECK(1, st == HAL_TIMEOUT);\n"
           "    FORGE_TEST_END();\n    return 0;\n}\n")
    suite = SUITE[:SUITE.index("SWR-002")].replace("    Target Check Should Pass    2\n", "")
    out = run(tmp_path, monkeypatch, {"software/tests/software/scn_hsi.c": scn,
                                      "software/tests/software/test_rcc_requirements.robot": suite})
    assert "CHECK_EXPR:scn_hsi.c#1:st == HAL_TIMEOUT with st = HAL_RCC_HSI_Enable(1000U)" in out["issues"], out["issues"]
    # ADR-0008 L11: structured failed-check record + snapshot of the exact files for the route gate's safety net
    import json as _json

    rec = _json.loads((tmp_path / "evidence/test-integrity.jsonl").read_text().splitlines()[-1])
    assert rec["failed_checks"] == [{"requirements": ["SWR-001"], "scenario": "scn_hsi.c", "check": "1",
                                     "expr": "st == HAL_TIMEOUT with st = HAL_RCC_HSI_Enable(1000U)",
                                     "observes": [], "driver_call": True}]  # SWR-001 names RCC_CR.HSION, not a status
    assert rec["build_failed"] == [] and all((tmp_path / ".forge-run/test-snapshots" / h).is_file()
                                             for h in rec["files"].values())
