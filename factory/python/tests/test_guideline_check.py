"""SWE3-07 verification node: deterministic ST Cube2 HAL guideline conformance (user requirement 2026-10-14)."""
import pytest
from forge_factory.inspection.guideline import check_workspace, strip_c

LL_H = """/* LL RCC */
#ifndef STM32N6XX_LL_RCC_H
#define STM32N6XX_LL_RCC_H
#include <stdint.h>
#define LL_RCC_HSI_DIV_1 (0x0UL)
typedef struct
{
  uint32_t cr;
} ll_rcc_regs_t;
__STATIC_INLINE void LL_RCC_HSI_Enable(ll_rcc_regs_t *p_rcc)
{
  p_rcc->cr |= 1UL;
}
#endif /* STM32N6XX_LL_RCC_H */
"""
HAL_H = """#ifndef STM32N6XX_HAL_RCC_H
#define STM32N6XX_HAL_RCC_H
#include "stm32n6xx_ll_rcc.h"
typedef enum
{
  HAL_OK = 0U,
  HAL_ERROR = 1U,
  HAL_TIMEOUT = 2U
} hal_status_t;
typedef struct
{
  uint32_t hsi_div;
} hal_rcc_hsi_config_t;
hal_status_t HAL_RCC_HSI_SetConfig(const hal_rcc_hsi_config_t *p_config, uint32_t timeout_ms);
#endif /* STM32N6XX_HAL_RCC_H */
"""
HAL_C = """#include "stm32n6xx_hal_rcc.h"
static uint32_t rcc_ready(void) { return 1U; }
hal_status_t HAL_RCC_HSI_SetConfig(const hal_rcc_hsi_config_t *p_config, uint32_t timeout_ms)
{
  uint32_t count = 0U;
  uint8_t small[16];
  (void)p_config; (void)small;
  while ((rcc_ready() == 0U) && (count < timeout_ms))
  {
    count++;
  }
  return (count < timeout_ms) ? HAL_OK : HAL_TIMEOUT;
}
"""


def make(ws, hal_h=HAL_H, hal_c=HAL_C, ll_h=LL_H, extra=None):
    (ws / "software/hal").mkdir(parents=True)
    (ws / "software/ll").mkdir(parents=True)
    (ws / "software/hal/stm32n6xx_hal_rcc.h").write_text(hal_h)
    (ws / "software/hal/stm32n6xx_hal_rcc.c").write_text(hal_c)
    (ws / "software/ll/stm32n6xx_ll_rcc.h").write_text(ll_h)
    for k, v in (extra or {}).items():
        (ws / k).write_text(v)
    return check_workspace(ws)


def rules(rep):
    return {v["rule"] for v in rep["violations"]}


def test_conformant_fixture_passes(tmp_path):
    rep = make(tmp_path)
    assert rep["guideline_hash_ok"] is True
    assert rep["verdict"] == "PASS", rep["violations"]


@pytest.mark.parametrize("mutate,rule", [
    (lambda h, c, ll: (h.replace("#ifndef STM32N6XX_HAL_RCC_H", "#ifndef _STM32N6XX_HAL_RCC_H"), c, ll), "GL-GUARD-01"),
    (lambda h, c, ll: (h.replace("hal_rcc_hsi_config_t;", "RCC_HsiConfig_t;"), c, ll), "GL-TYPE-01"),
    (lambda h, c, ll: (h.replace("} hal_rcc_hsi_config_t;", "} rcc_hsi_config_t;"), c, ll), "GL-TYPE-02"),
    (lambda h, c, ll: (h.replace("HAL_TIMEOUT = 2U", "RCC_TIMEOUT = 2U"), c, ll), "GL-ENUM-02"),
    (lambda h, c, ll: (h, c, ll.replace("typedef struct", "typedef enum { LL_A } ll_e_t;\ntypedef struct")), "GL-ENUM-01"),
    (lambda h, c, ll: (h, c.replace("static uint32_t rcc_ready", "uint32_t Rcc_Ready2(void);\nstatic uint32_t rcc_ready"), ll),
     "GL-API-01"),
    (lambda h, c, ll: (h, c, ll.replace("__STATIC_INLINE void LL_RCC_HSI_Enable", "void LL_RCC_HSI_Enable")), "GL-API-02"),
    (lambda h, c, ll: (h.replace("uint32_t timeout_ms);", "uint32_t TimeoutMs);"), c, ll), "GL-ARG-01"),
    (lambda h, c, ll: (h.replace("(const hal_rcc_hsi_config_t *p_config, uint32_t timeout_ms);",
                                 "(hal_rcc_hsi_config_t *p_config, uint32_t timeout_ms);"), c, ll), "GL-CONST-01"),
    (lambda h, c, ll: (h, "#if defined(STM32N657xx)\n#endif\n" + c, ll), "GL-RPN-01"),
    (lambda h, c, ll: (h, c.replace("while ((rcc_ready() == 0U) && (count < timeout_ms))", "while (rcc_ready() == 0U)"), ll),
     "GL-LOOP-01"),
    (lambda h, c, ll: (h, c.replace("uint8_t small[16];", "uint32_t big[64];"), ll), "GL-ARRAY-01"),
    (lambda h, c, ll: (h, c, ll.replace("#define LL_RCC_HSI_DIV_1", "#define __LL_RCC_X 1\n#define LL_RCC_HSI_DIV_1")),
     "GL-MACRO-01"),
    (lambda h, c, ll: (h.replace("#endif /* STM32N6XX_HAL_RCC_H */",
                                 "#define HAL_RCC_ENABLE(x) (RCC->CR |= (x))\n#endif /* STM32N6XX_HAL_RCC_H */"), c, ll),
     "GL-MACRO-02"),
])
def test_each_rule_detects_violation(tmp_path, mutate, rule):
    h, c, ll = mutate(HAL_H, HAL_C, LL_H)
    rep = make(tmp_path, h, c, ll)
    assert rule in rules(rep), rep["violations"]
    assert rep["verdict"] == "FAIL"


def test_layout_rules(tmp_path):
    rep = make(tmp_path, extra={"software/ll/stm32n6xx_ll_rcc.c": "int x;\n"})
    assert "GL-FILE-02" in rules(rep)
    empty = check_workspace(tmp_path / "nothing")
    assert empty["verdict"] == "FAIL" and "GL-FILE-01" in rules(empty)


def test_comments_and_strings_do_not_trigger():
    s = strip_c('/* while(1) */ x = "for(;;)"; // #define _BAD 1\n')
    assert "while" not in s and "for(;;)" not in s and "_BAD" not in s
