"""EASA formal verifiers (CBMC bounded proof, Frama-C Eva): harness from facts, seeded defects caught, honest limits."""
import json

import pytest
from forge_factory.assurance import formal

HDR = """#ifndef LL_H
#define LL_H
#include <stdint.h>
#define LL_RCC_REG_COUNT 8U
extern volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];
static inline void LL_RCC_HSI_Enable(void)
{
  ll_rcc_regs[0U] |= 0x8U;
}
static inline uint32_t LL_RCC_HSI_IsReady(void)
{
  return ((ll_rcc_regs[1U] & 0x8U) != 0U) ? 1U : 0U;
}
static inline void LL_RCC_Set(uint32_t word, uint32_t value)
{
  if (word < LL_RCC_REG_COUNT) { ll_rcc_regs[word] = value; }
}
static inline void LL_RCC_Copy(const uint32_t *src)
{
  ll_rcc_regs[2U] = *src;
}
#endif
"""
needs_cbmc = pytest.mark.skipif(formal.tool("cbmc") is None, reason="CBMC not installed")
needs_eva = pytest.mark.skipif(formal.tool("frama-c") is None, reason="Frama-C not installed")


def _ws(tmp_path, hdr=HDR):
    ws = tmp_path / "WO" / "workspace"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL"}))
    (ws / "software/ll").mkdir(parents=True)
    (ws / "software/ll/stm32n6xx_ll_rcc.h").write_text(hdr)
    return ws


def test_api_from_facts(tmp_path):
    a = formal.api(_ws(tmp_path))
    assert [f["name"] for f in a["functions"]] == ["LL_RCC_HSI_Enable", "LL_RCC_HSI_IsReady", "LL_RCC_Set", "LL_RCC_Copy"]
    assert a["regs"] == {"name": "ll_rcc_regs", "count": "LL_RCC_REG_COUNT"}
    assert a["limitations"] == []


HAL_H = """#ifndef HAL_H
#define HAL_H
#include <stdint.h>
#include "stm32n6xx_ll_rcc.h"
typedef enum { HAL_OK = 0, HAL_ERROR = 1 } hal_status_t;
typedef enum { PERIPH_ADC12 = 0, PERIPH_GPDMA1 = 1 } hal_rcc_peripheral_t;
typedef struct { uint32_t timeout; uint32_t word; } hal_rcc_cfg_t;
hal_status_t HAL_RCC_Enable(hal_rcc_peripheral_t p);
hal_status_t HAL_RCC_Config(const hal_rcc_cfg_t *cfg);
hal_status_t HAL_RCC_Callback(void (*cb)(void));
#endif
"""
HAL_C = """#include "stm32n6xx_hal_rcc.h"
hal_status_t HAL_RCC_Enable(hal_rcc_peripheral_t p)
{
    static const uint32_t bit[2] = {1U, 2U};
    if ((uint32_t)p > 1U) { return HAL_ERROR; }
    ll_rcc_regs[3U] |= bit[p];
    return HAL_OK;
}
hal_status_t HAL_RCC_Config(const hal_rcc_cfg_t *cfg)
{
    if (cfg->word >= LL_RCC_REG_COUNT) { return HAL_ERROR; }
    ll_rcc_regs[cfg->word] = cfg->timeout;
    return HAL_OK;
}
hal_status_t HAL_RCC_Callback(void (*cb)(void)) { cb(); return HAL_OK; }
"""


def _hal(tmp_path, c=HAL_C):
    ws = _ws(tmp_path)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL"}))
    (ws / "software/hal").mkdir()
    (ws / "software/hal/stm32n6xx_hal_rcc.h").write_text(HAL_H)
    (ws / "software/hal/stm32n6xx_hal_rcc.c").write_text(c)
    return ws


def test_hal_enum_and_struct_pointer_parameters_are_harnessed_function_pointer_is_not(tmp_path):
    a = formal.api(_hal(tmp_path))
    assert [f["name"] for f in a["functions"]] == ["HAL_RCC_Enable", "HAL_RCC_Config"]
    assert a["limitations"] == ["LIMITATION:UNSUPPORTED_PARAMETER:HAL_RCC_Callback"]


@needs_cbmc
@needs_eva
def test_hal_out_of_range_enum_and_struct_field_are_checked(tmp_path):
    ok = formal.cbmc(_hal(tmp_path))
    assert ok["status"] == "PASS" and formal.eva(_hal(tmp_path / "e"))["status"] == "PASS"
    # HAL_RCC_Config dereferences cfg without a NULL check: informational, the verdict assumes a valid pointer
    assert ok["functions"]["HAL_RCC_Config"]["null_argument"] == "FAIL"
    assert "INFO_NULL_ARGUMENT_NOT_HANDLED:HAL_RCC_Config" in ok["findings"]
    guarded = formal.cbmc(_hal(tmp_path / "g", HAL_C.replace("if (cfg->word >= LL_RCC_REG_COUNT)",
                                                             "if ((cfg == 0) || (cfg->word >= LL_RCC_REG_COUNT))")))
    assert guarded["functions"]["HAL_RCC_Config"]["null_argument"] == "PASS"
    bad = HAL_C.replace("if ((uint32_t)p > 1U) { return HAL_ERROR; }\n", "").replace(
        "if (cfg->word >= LL_RCC_REG_COUNT)", "if (cfg->word > LL_RCC_REG_COUNT)")
    c = formal.cbmc(_hal(tmp_path / "b", bad))
    assert c["functions"]["HAL_RCC_Enable"]["status"] == "FAIL" and c["functions"]["HAL_RCC_Config"]["status"] == "FAIL"
    assert formal.eva(_hal(tmp_path / "be", bad))["alarms"] >= 2


def test_missing_tools_are_not_supported_never_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(formal, "tool", lambda name: None)
    assert formal.cbmc(_ws(tmp_path))["status"] == "NOT_SUPPORTED"
    assert formal.eva(_ws(tmp_path / "e"))["status"] == "NOT_SUPPORTED"


@needs_cbmc
def test_cbmc_proves_correct_code_and_catches_out_of_bounds(tmp_path):
    ok = formal.cbmc(_ws(tmp_path))
    assert ok["status"] == "PASS" and ok["functions"]["LL_RCC_Set"]["claims"] >= 1   # constant indices: no property
    bad = formal.cbmc(_ws(tmp_path / "b", HDR.replace("if (word < LL_RCC_REG_COUNT)", "if (word <= LL_RCC_REG_COUNT)")))
    assert bad["status"] == "FAIL" and bad["functions"]["LL_RCC_Set"]["status"] == "FAIL"
    assert any(f.startswith("CBMC_FAILURE:LL_RCC_Set:") for f in bad["findings"])


@needs_cbmc
def test_cbmc_unbounded_poll_is_inconclusive_not_pass(tmp_path):
    hdr = HDR.replace("  return ((ll_rcc_regs[1U] & 0x8U) != 0U) ? 1U : 0U;",
                      "  while ((ll_rcc_regs[1U] & 0x8U) == 0U) { }\n  return 1U;")
    r = formal.cbmc(_ws(tmp_path, hdr), functions=["LL_RCC_HSI_IsReady"])
    assert r["functions"]["LL_RCC_HSI_IsReady"]["status"] == "INCONCLUSIVE" and r["status"] == "UNKNOWN"


@needs_eva
def test_eva_clean_on_correct_code_and_alarms_on_seeded_defects(tmp_path):
    ok = formal.eva(_ws(tmp_path))
    assert ok["status"] == "PASS" and ok["alarms"] == 0
    bad = formal.eva(_ws(tmp_path / "b", HDR.replace("if (word < LL_RCC_REG_COUNT)", "if (word <= LL_RCC_REG_COUNT)")))
    assert bad["status"] == "FAIL" and bad["alarms"] >= 1 and any(f.startswith("EVA_ALARM:") for f in bad["findings"])
    uninit = HDR.replace("static inline uint32_t LL_RCC_HSI_IsReady(void)\n{\n  return",
                         "static inline uint32_t LL_RCC_HSI_IsReady(void)\n{\n  uint32_t r;\n  if (ll_rcc_regs[1U] != 0U) { r = 1U; }\n  return r +")
    u = formal.eva(_ws(tmp_path / "u", uninit))
    assert u["status"] == "FAIL" and any("uninitialized" in f for f in u["findings"])
