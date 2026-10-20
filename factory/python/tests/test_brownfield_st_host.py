"""Feature 008 follow-up (owner 2026-10-20 "address all"; proposal checklist-v0.4-brownfield, ST pilot): the delivered
ST CMSIS code is unit-tested on the host (generated host device map), built and measured (generated build-only unit),
run on Renode (8 KB RCC window with the RM0486 set/clear registers) and observed by the Robot policy through the vendor
mask names. Needs the fingerprinted ST downloads (skipped where they are absent)."""
import ast
import re
import shutil
import subprocess

import pytest
from forge_factory.assurance import hardware
from forge_factory.brownfield import cmsis
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import robot_policy
from forge_factory.mcp.servers import tests as T
from forge_factory.mcp.servers.sim import SIM_DIR
from forge_factory.workflow.builder import build
from forge_factory.workflow.scaffold import TEST_CALLS_MARKER, TEST_CASES_MARKER, scaffold, unit_test
from test_brownfield_pilot import _contract, ws  # noqa: F401 - pytest fixture
from test_brownfield_pilot import pytestmark as pilot_mark

UT = """static void ut_hsi(void)
{
    ut_reset_regs();
    LL_RCC_HSI_Enable();
    CHECK("UT-001", forge_host_rcc.CSR == RCC_CSR_HSIONS);
    LL_RCC_HSI_Disable();
    CHECK("UT-002", forge_host_rcc.CCR == RCC_CCR_HSIONC);
    forge_host_rcc.SR = RCC_SR_HSIRDY;
    CHECK("UT-003", LL_RCC_HSI_IsReady() == 1U);
    ut_reset_regs();
    LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_GPDMA1);
    CHECK("UT-004", (forge_host_rcc.AHB1ENSR & LL_AHB1_GRP1_PERIPH_GPDMA1) != 0U);
}
"""
TARGET = """#include "stm32n6xx_ll_rcc.h"
#include "stm32n6xx_ll_bus.h"
#include "forge_target_test.h"
FORGE_MAILBOX_DEFINE;
int main(void)
{
    uint32_t i = 0U;
    FORGE_TEST_BEGIN();
    LL_RCC_HSI_Enable();
    while ((LL_RCC_HSI_IsReady() == 0U) && (i < 1000U)) { i++; }
    TCHECK(1, LL_RCC_HSI_IsReady() == 1U);
    LL_RCC_HSI_Disable();
    TCHECK(2, (RCC->CR & RCC_CR_HSION) == 0U);
    LL_AHB1_GRP1_EnableClock(LL_AHB1_GRP1_PERIPH_GPDMA1);
    TCHECK(3, LL_AHB1_GRP1_IsEnabledClock(LL_AHB1_GRP1_PERIPH_GPDMA1) == 1U);
    LL_AHB1_GRP1_ForceReset(LL_AHB1_GRP1_PERIPH_GPDMA1);
    TCHECK(4, (RCC->AHB1RSTR & LL_AHB1_GRP1_PERIPH_GPDMA1) != 0U);
    LL_AHB1_GRP1_ReleaseReset(LL_AHB1_GRP1_PERIPH_GPDMA1);
    TCHECK(5, (RCC->AHB1RSTR & LL_AHB1_GRP1_PERIPH_GPDMA1) == 0U);
    FORGE_TEST_END();
    return 0;
}
"""


def _model_tables() -> tuple[dict, dict]:
    tree = ast.parse((SIM_DIR / "rcc_model.py").read_text())
    vals = {t.targets[0].id: ast.literal_eval(t.value) for t in tree.body
            if isinstance(t, ast.Assign) and getattr(t.targets[0], "id", "") in ("SET_ALIAS", "CLEAR_ALIAS")}
    return vals["SET_ALIAS"], vals["CLEAR_ALIAS"]


@pilot_mark
def test_rcc_model_set_clear_table_matches_rm0486(ws):  # noqa: F811
    idx = hardware.index(ws / "inputs/sections/RM0486", "RCC")
    al = hardware.set_clear_aliases(idx)
    sets, clrs = _model_tables()
    assert sets == {idx[s]["offset"]: idx[t]["offset"] for t, (s, _c) in al.items()}
    assert clrs == {idx[c]["offset"]: idx[t]["offset"] for t, (_s, c) in al.items()}
    assert len(sets) == 41 and sets[0x800] == 0x000 and clrs[0x1000] == 0x000 and sets[0xA50] == 0x250
    assert "size: 0x2000" in (SIM_DIR / "stm32n6_rcc.repl").read_text()


@pilot_mark
def test_st_code_unit_tests_run_on_the_host_device_map(ws):  # noqa: F811
    _contract(ws)
    assert cmsis.is_cmsis(ws) and scaffold(ws)["host_device"]
    hd = ws / cmsis.HOST_DIR
    assert {"stm32n6xx.h", "stm32n657xx.h", "core_cm55.h", "forge_host_device.h"} <= {p.name for p in hd.iterdir()}
    assert not (hd / "cmsis_gcc.h").exists()  # the Arm-only compiler header stays out of the host build
    p = ws / unit_test(ws)
    p.write_text(p.read_text().replace(TEST_CASES_MARKER, UT + TEST_CASES_MARKER)
                 .replace(TEST_CALLS_MARKER, "ut_hsi();\n    " + TEST_CALLS_MARKER))
    r = T.run_unit(sdk.ToolContext("forge-tests-mcp", "run_unit", "swe4-author", "SWE.4", ws, "r"), T.RunIn())
    assert r["status"] == "PASS", r


@pilot_mark
def test_header_only_delivery_gets_a_build_only_unit(ws, tmp_path):  # noqa: F811
    u = cmsis.delivered_unit(ws, tmp_path)
    text = u.read_text()
    assert text.count("forge_measure_") == 22 and str(tmp_path) in str(u)  # 11 scope wrappers, outside the workspace
    r = subprocess.run(["arm-none-eabi-gcc", "-mcpu=cortex-m55", "-mthumb", "-std=c11", "-Os", "-Wall", "-Werror",
                        *cmsis.target_flags(ws), f"-I{ws / 'software/ll'}", "-c", str(u), "-o", str(tmp_path / "u.o")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]


@pilot_mark
@pytest.mark.skipif(not shutil.which("renode") and not (shutil.which("arm-none-eabi-gcc")), reason="no Renode")
def test_st_code_runs_on_the_renode_rcc_model(ws):  # noqa: F811
    from forge_factory.mcp.servers import sim

    if sim.renode_bin() is None:
        pytest.skip("Renode not installed")
    (ws / "software/tests/target").mkdir(parents=True, exist_ok=True)
    (ws / "software/tests/target/test_rcc_target.c").write_text(TARGET)
    r = sim.run_renode(sdk.ToolContext("forge-sim-mcp", "run_renode", "swe5-author", "SWE.5", ws, "r"), sim.SimIn())
    assert r["status"] == "PASS" and "5 checks passed, 0 failed" in r["summary"], r


def test_cmsis_test_prompts_use_the_vendor_access():
    g, _ = build("WO-T", layer="LL", trace=True, chunk_lines=150, brownfield="FROZEN", delivery_style="cmsis")
    prompts = dict(re.findall(r'\n  (\w+) \[[^\n]*?prompt="((?:[^"\\]|\\.)*)"', g))
    assert {n for n, p in prompts.items() if re.search(r"ll_rcc_regs|LL_RCC_<REG>|_OFFSET / 4U|LL_RCC_REG_COUNT", p)} == set()
    assert "forge_host_rcc.CSR == RCC_CSR_HSIONS" in prompts["swe4_test_author"]
    assert "RCC->CR & RCC_CR_HSION" in prompts["swe5_target_author"] and "RCC->CR & RCC_CR_HSION" in prompts["swe6_test_author"]
    assert "FORGE_HOST_DEVICE_IMPLEMENTATION" in prompts["swe5_author"]
    g2, _ = build("WO-T", layer="LL", trace=True, chunk_lines=150, brownfield="FROZEN")
    assert "forge_host_rcc" not in g2  # forge-style deliveries keep their prompts (goldens)


def test_robot_policy_accepts_vendor_mask_names(tmp_path):
    suite = tmp_path / "software/tests/software/test_rcc_requirements.robot"
    suite.parent.mkdir(parents=True)
    suite.write_text("*** Settings ***\nLibrary    ForgeTarget\n\n*** Test Cases ***\nSWR-001 HSI enable\n"
                     "    [Tags]    SWR-001\n    Run Target Scenario    scn_hsi.c\n    Target Check Should Pass    1\n")
    (suite.parent / "scn_hsi.c").write_text("TCHECK(1, (RCC->CR & RCC_CR_HSION) != 0U);\n")
    req = {"SWR-001": "When the HSI enable is requested, the RCC driver shall set RCC_CR.HSION."}
    assert robot_policy.unobserved_requirements(suite, suite.parent, req) == []
    (suite.parent / "scn_hsi.c").write_text("TCHECK(1, LL_RCC_HSI_IsReady() == 1U);\n")
    assert robot_policy.unobserved_requirements(suite, suite.parent, req)
