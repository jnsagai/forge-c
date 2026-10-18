"""CAPA-038 (r123/r126/r127): HAL unit tests run on a generated test double of the provided LL API, so poll counts,
call order and the never-ready / ready-after-N paths are observable; the double cannot be edited and a HAL that
bypasses the LL does not build."""
import json
import os
import subprocess

import pytest
from forge_factory.common import canonical_json
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import tests
from forge_factory.workflow import ll_fake, scaffold

LL = """#ifndef STM32N6XX_LL_RCC_H
#define STM32N6XX_LL_RCC_H
#include <stdint.h>
#define LL_RCC_REG_COUNT 1024U
extern volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];
#define LL_RCC_CR_OFFSET 0x000U
#define LL_RCC_CR_HSEON_MSK 0x00000010U
#define LL_RCC_SR_OFFSET 0x004U
#define LL_RCC_SR_HSERDY_MSK 0x00000010U
#define LL_RCC_AHB1ENR_OFFSET 0x250U
#define LL_RCC_AHB1ENR_ADC12EN_MSK 0x00000020U
/** @brief Set AHB1ENR.ADC12EN. */
static inline void LL_RCC_ADC12_Enable(void)
{
  ll_rcc_regs[LL_RCC_AHB1ENR_OFFSET / 4U] |= LL_RCC_AHB1ENR_ADC12EN_MSK;
}
/** @brief Clear AHB1ENR.ADC12EN. */
static inline void LL_RCC_ADC12_Disable(void)
{
  ll_rcc_regs[LL_RCC_AHB1ENR_OFFSET / 4U] &= ~LL_RCC_AHB1ENR_ADC12EN_MSK;
}
/** @brief 1U when AHB1ENR.ADC12EN is set. */
static inline uint32_t LL_RCC_ADC12_IsEnabled(void)
{
  return ((ll_rcc_regs[LL_RCC_AHB1ENR_OFFSET / 4U] & LL_RCC_AHB1ENR_ADC12EN_MSK) != 0U) ? 1U : 0U;
}
/** @brief Set RCC_CR.HSEON. */
static inline void LL_RCC_HSE_Enable(void)
{
  ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= LL_RCC_CR_HSEON_MSK;
}
/** @brief Clear RCC_CR.HSEON. */
static inline void LL_RCC_HSE_Disable(void)
{
  ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] &= ~LL_RCC_CR_HSEON_MSK;
}
/** @brief 1U when RCC_SR.HSERDY is set. */
static inline uint32_t LL_RCC_HSE_IsReady(void)
{
  return ((ll_rcc_regs[LL_RCC_SR_OFFSET / 4U] & LL_RCC_SR_HSERDY_MSK) != 0U) ? 1U : 0U;
}
#endif
"""
HAL_H = """#ifndef HAL_H
#define HAL_H
#include <stdint.h>
#include "stm32n6xx_ll_rcc.h"
typedef enum { HAL_OK = 0, HAL_ERROR = 1, HAL_TIMEOUT = 2 } hal_status_t;
hal_status_t HAL_RCC_HSE_Enable(uint32_t timeout);
#endif
"""
HAL_C = """#include "stm32n6xx_hal_rcc.h"
hal_status_t HAL_RCC_HSE_Enable(uint32_t timeout)
{
    hal_status_t st = HAL_TIMEOUT;
    uint32_t n = 0U;
    LL_RCC_HSE_Enable();
    while ((n < timeout) && (st != HAL_OK))
    {
        if (LL_RCC_HSE_IsReady() != 0U) { st = HAL_OK; } else { n++; }
    }
    if (st != HAL_OK) { LL_RCC_HSE_Disable(); }
    return st;
}
"""
CASE = """static void ut_hse(void)
{
    hal_status_t st;
    ut_reset();
    ll_fake_return_from(LL_FAKE_LL_RCC_HSE_IsReady, 3U, 1U);
    st = HAL_RCC_HSE_Enable(10U);
    CHECK("UT-001", st == HAL_OK);
    CHECK("UT-001-POLLS", ll_fake_calls(LL_FAKE_LL_RCC_HSE_IsReady) == 3U);
    CHECK("UT-001-ORDER", ll_fake_index_of(LL_FAKE_LL_RCC_HSE_Enable, 1U) < ll_fake_index_of(LL_FAKE_LL_RCC_HSE_IsReady, 1U));
    ut_reset();
    st = HAL_RCC_HSE_Enable(10U);
    CHECK("UT-002", st == HAL_TIMEOUT);
    CHECK("UT-002-POLLS", ll_fake_calls(LL_FAKE_LL_RCC_HSE_IsReady) == 10U);
    CHECK("UT-002-ROLLBACK", ll_fake_index_of(LL_FAKE_LL_RCC_HSE_Disable, 1U) == 11);
}
"""


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    w = tmp_path / "WO-0002B-X" / "workspace"
    for rel, text in {"software/ll/stm32n6xx_ll_rcc.h": LL, "software/hal/stm32n6xx_hal_rcc.h": HAL_H,
                      "software/hal/stm32n6xx_hal_rcc.c": HAL_C,
                      ".forge-run/manifest.json": json.dumps({"layer": "HAL", "hal_unit_isolation": "ll-fake-v1"})}.items():
        (w / rel).parent.mkdir(parents=True, exist_ok=True)
        (w / rel).write_text(text)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=w, check=True)
    monkeypatch.setenv("FORGE_MCP_TRUST", "env")
    monkeypatch.setenv("FORGE_WORKSPACE", str(w))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "ev"))
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    return w


def _run_unit():
    os.environ["FORGE_ROLE"], os.environ["FORGE_PHASE"] = "swe4-author", "SWE.4"
    out = sdk.invoke("forge-tests-mcp", next(o for o in tests.OPERATIONS if o.name == "run_unit"), {})
    assert len(canonical_json(out)) <= sdk.MAX_RESULT_BYTES
    return out


def _insert(ws, case=CASE, call="ut_hse();"):
    p = ws / scaffold.UNIT_TEST
    t = p.read_text().replace(scaffold.TEST_CASES_MARKER, case + "\n" + scaffold.TEST_CASES_MARKER)
    p.write_text(t.replace(scaffold.TEST_CALLS_MARKER, call + "\n    " + scaffold.TEST_CALLS_MARKER))


def test_capa038_poll_count_order_and_rollback_are_observable(ws):
    r = scaffold.scaffold(ws)
    assert r["ll_fake"] and not ll_fake.modified(ws)
    fake = (ws / ll_fake.FAKE_HEADER).read_text()
    assert "extern volatile uint32_t ll_rcc_regs" not in fake and "#define LL_RCC_CR_HSEON_MSK 0x00000010U" in fake
    assert fake.count("ll_fake_record(LL_FAKE_LL_RCC_HSE_") == 2 and "return ll_fake_query(LL_FAKE_LL_RCC_HSE_IsReady" in fake
    assert "ll_rcc_regs" not in (ws / scaffold.UNIT_TEST).read_text()
    _insert(ws)
    out = _run_unit()
    assert out["status"] == "PASS", out


def test_capa038_edited_double_fails_and_hal_bypass_does_not_build(ws):
    scaffold.scaffold(ws)
    _insert(ws)
    f = ws / ll_fake.FAKE_HEADER
    f.chmod(0o644)
    f.write_text(f.read_text().replace("return ((ll_fake_from_[fn] != 0U)", "return 1U; return ((ll_fake_from_[fn] != 0U)"))
    out = _run_unit()
    assert out["status"] == "FAIL" and any(i.startswith("GENERATED_TEST_DOUBLE_MODIFIED") for i in out["issues"])
    ll_fake.write(ws)                                                    # restored
    (ws / "software/hal/stm32n6xx_hal_rcc.c").write_text(HAL_C.replace(
        "    LL_RCC_HSE_Enable();", "    ll_rcc_regs[0] |= LL_RCC_CR_HSEON_MSK;"))
    out = _run_unit()
    assert out["status"] == "FAIL" and any("BUILD_FAIL" in i for i in out["issues"])


def test_capa038_older_work_orders_keep_the_register_array_harness(ws):
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL"}))
    r = scaffold.scaffold(ws)
    assert not r.get("ll_fake") and not (ws / ll_fake.FAKE_DIR).exists()
    assert "volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];" in (ws / scaffold.UNIT_TEST).read_text()


def test_capa038_easa_mutation_and_api_execution_build_on_the_double(ws):
    from forge_factory.assurance import verifiers as V

    scaffold.scaffold(ws)
    _insert(ws)
    m = V.v_mutation(ws)
    assert m["campaign"]["invalid"] < m["campaign"]["eligible"] and m["campaign"]["killed"] >= 1, m
    a = V.v_api_execution(ws)
    assert a["status"] in ("PASS", "FAIL") and not any("build" in f.lower() for f in a["findings"]), a


STATE = """static void ut_state(void)
{
    ut_reset();
    CHECK("UT-003", LL_RCC_ADC12_IsEnabled() == 0U);
    LL_RCC_ADC12_Enable();
    CHECK("UT-003-ON", LL_RCC_ADC12_IsEnabled() == 1U);
    LL_RCC_ADC12_Disable();
    CHECK("UT-003-OFF", LL_RCC_ADC12_IsEnabled() == 0U);
    ll_fake_return_from(LL_FAKE_LL_RCC_ADC12_IsEnabled, 1U, 1U);
    CHECK("UT-003-SCRIPT", LL_RCC_ADC12_IsEnabled() == 1U);
    ut_reset();
    LL_RCC_HSE_Enable();
    CHECK("UT-004", LL_RCC_HSE_IsReady() == 0U);
}
"""


def test_capa038_iteration2_state_queries_follow_the_bits_hardware_flags_stay_scripted(ws):
    """CAPA-038 iteration 2 (r135 DEF-001/DEF-004): IsEnabled always returned 0U after Enable; a query of a bit an
    LL function writes now follows it, a hardware-set flag (IsReady) stays scripted, a script still overrides."""
    scaffold.scaffold(ws)
    _insert(ws, STATE, "ut_state();")
    out = _run_unit()
    assert out["status"] == "PASS", out
