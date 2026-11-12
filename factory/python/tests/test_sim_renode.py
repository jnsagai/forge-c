"""Renode target simulation of the RCC driver on the Forge-C STM32N6 (Cortex-M55) model: real PASS and real FAIL."""
import os
import shutil
from pathlib import Path

import pytest
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import sim

pytestmark = pytest.mark.skipif(not (sim.renode_bin() and shutil.which("arm-none-eabi-gcc")),
                                reason="renode / GNU Arm not installed")
LL = """#ifndef STM32N6XX_LL_RCC_H
#define STM32N6XX_LL_RCC_H
#include <stdint.h>
#define LL_RCC_REG_COUNT 1024U
extern volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];
#define LL_RCC_CR_OFFSET 0x000U
#define LL_RCC_SR_OFFSET 0x004U
#define LL_RCC_CR_HSION_MSK 0x00000008U
#define LL_RCC_SR_HSIRDY_MSK 0x00000008U
static inline void LL_RCC_HSI_Enable(void) { ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= LL_RCC_CR_HSION_MSK; }
static inline uint32_t LL_RCC_HSI_IsReady(void)
{ return ((ll_rcc_regs[LL_RCC_SR_OFFSET / 4U] & LL_RCC_SR_HSIRDY_MSK) != 0U) ? 1U : 0U; }
#endif /* STM32N6XX_LL_RCC_H */
"""
HAL_H = ("#ifndef STM32N6XX_HAL_RCC_H\n#define STM32N6XX_HAL_RCC_H\n#include \"stm32n6xx_ll_rcc.h\"\n"
         "typedef enum {HAL_OK = 0U, HAL_ERROR = 1U, HAL_TIMEOUT = 2U} hal_status_t;\n"
         "hal_status_t HAL_RCC_HSI_Enable(uint32_t timeout);\n#endif /* STM32N6XX_HAL_RCC_H */\n")
HAL_C = ("#include \"stm32n6xx_hal_rcc.h\"\nhal_status_t HAL_RCC_HSI_Enable(uint32_t timeout)\n{\n"
         "    uint32_t count = 0U;\n    LL_RCC_HSI_Enable();\n"
         "    while ((LL_RCC_HSI_IsReady() == 0U) && (count < timeout)) { count++; }\n"
         "    return (LL_RCC_HSI_IsReady() != 0U) ? HAL_OK : HAL_TIMEOUT;\n}\n")
TEST = ("#include \"stm32n6xx_hal_rcc.h\"\n#include \"forge_target_test.h\"\nFORGE_MAILBOX_DEFINE;\n"
        "int main(void)\n{\n    FORGE_TEST_BEGIN();\n    TCHECK(1, HAL_RCC_HSI_Enable(1000U) == {expect});\n"
        "    TCHECK(2, (ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] & LL_RCC_CR_HSION_MSK) != 0U);\n"
        "    FORGE_TEST_END();\n    return 0;\n}\n")


def ws(tmp_path, monkeypatch, tests):
    for rel, txt in {"software/ll/stm32n6xx_ll_rcc.h": LL, "software/hal/stm32n6xx_hal_rcc.h": HAL_H,
                     "software/hal/stm32n6xx_hal_rcc.c": HAL_C, **tests}.items():
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text(txt)
    monkeypatch.setenv("FORGE_MCP_TRUST", "env")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / ".ev"))
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / ".state"))
    os.environ["FORGE_ROLE"], os.environ["FORGE_PHASE"] = "swe5-author", "SWE.5"
    return sdk.invoke("forge-sim-mcp", next(o for o in sim.OPERATIONS if o.name == "run_renode"), {})


def test_renode_runs_driver_on_cortex_m55_with_ready_and_timeout_scenarios(tmp_path, monkeypatch):
    out = ws(tmp_path, monkeypatch, {"software/tests/target/test_rcc_target.c": TEST.replace("{expect}", "HAL_OK"),
                                     "software/tests/target/test_rcc_target_timeout.c":
                                         TEST.replace("{expect}", "HAL_TIMEOUT")})
    assert out["status"] == "PASS", out
    assert out["metrics"]["passed"] == 4 and out["metrics"]["failed"] == 0
    assert out["metrics"]["target_evidence"] == "simulated" and out["metrics"]["silicon_verified"] is False


def test_renode_reports_failing_checks_and_missing_tests(tmp_path, monkeypatch):
    out = ws(tmp_path, monkeypatch, {"software/tests/target/test_rcc_target_timeout.c":
                                     TEST.replace("{expect}", "HAL_OK")})  # wrong expectation under never-ready
    assert out["status"] == "FAIL" and "TARGET_FAIL:test_rcc_target_timeout.c:check 1" in out["issues"]
    empty = ws(tmp_path / "e", monkeypatch, {})
    assert empty["status"] == "BLOCKED" and empty["issues"] == ["NO_TESTS:software/tests/target"]


def test_renode_found_from_mcp_server_environment(monkeypatch):
    """MCP servers only receive FORGE_STATE_DIR (r45 run_renode reported 'not installed' without this)."""
    real = sim.renode_bin()
    if os.environ.get("FORGE_DATA_ROOT"):
        # the MCP contract is FORGE_STATE_DIR = <data root>/state; a hermetic run gives each file a private state
        # directory elsewhere (F014 DA-T029, run_full_inherited.py), which is not what an MCP server receives
        monkeypatch.setenv("FORGE_STATE_DIR", str(Path(os.environ["FORGE_DATA_ROOT"]) / "state"))
    monkeypatch.delenv("FORGE_DATA_ROOT", raising=False)
    monkeypatch.delenv("FORGE_RENODE_BIN", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    assert sim.renode_bin() == real
