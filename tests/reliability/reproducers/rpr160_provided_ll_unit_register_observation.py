"""Frozen black-box CPU probe: observe HAL register effects through run_unit.

This small test fixture supplies its own immutable LL and vendor-device inputs;
it is not a driver implementation or a claim about target peripheral behaviour.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

from forge_factory.mcp import sdk
from forge_factory.mcp.servers import tests as T
from forge_factory.workflow import ll_fake


def main():
    ws = Path(os.environ["FORGE_STATE_DIR"]) / "rpr160-workspace"
    files = {
        "inputs/vendor/include/stm32n6xx.h": '''#ifndef DEVICE_H
#define DEVICE_H
#include "core_cm55.h"
typedef struct { __IO uint32_t CR; __IO uint32_t CFR; __IO uint32_t SR; } WWDG_TypeDef;
#define WWDG ((WWDG_TypeDef *)0x50003000UL)
#define WWDG_CR_T 0x7FU
#define READ_REG(R) (R)
#define WRITE_REG(R,V) ((R) = (V))
#define MODIFY_REG(R,C,S) WRITE_REG((R), ((READ_REG(R) & ~(C)) | (S)))
#endif
''',
        "inputs/vendor/include/core_cm55.h": "#error Target-only core header must not execute on host\n",
        "software/ll/stm32n6xx_ll_wwdg.h": '''#ifndef LL_H
#define LL_H
#include "stm32n6xx.h"
__STATIC_INLINE void LL_WWDG_SetCounter(WWDG_TypeDef *WWDGx, uint32_t Counter)
{
    MODIFY_REG(WWDGx->CR, WWDG_CR_T, Counter & WWDG_CR_T);
}
#endif
''',
        "software/hal/stm32n6xx_hal_wwdg.h": '''#ifndef HAL_H
#define HAL_H
#include "stm32n6xx_ll_wwdg.h"
uint32_t HAL_WWDG_Refresh(uint32_t counter);
#endif
''',
        "software/hal/stm32n6xx_hal_wwdg.c": '''#include "stm32n6xx_hal_wwdg.h"
uint32_t HAL_WWDG_Refresh(uint32_t counter)
{
    LL_WWDG_SetCounter(WWDG, counter);
    return 0U;
}
''',
        "software/tests/unit/test_wwdg_registers.cpp": '''// FORGE_UNIT_BACKEND: provided-ll-ram-v1
#include <gtest/gtest.h>
extern "C" {
#include "stm32n6xx_hal_wwdg.h"
}
/** @test UT-001 @verifies USPEC-HAL-01-01 */
TEST(HalRegisterObservation, UT_001) {
    WWDG->CR = 0xA5000080U;
    EXPECT_EQ(HAL_WWDG_Refresh(0x50U), 0U);
    EXPECT_EQ(WWDG->CR, 0xA50000D0U);
}
''',
    }
    for rel, raw in files.items():
        p = ws / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(raw)
    def hashed(rel):
        return hashlib.sha256((ws / rel).read_bytes()).hexdigest()
    ll = "software/ll/stm32n6xx_ll_wwdg.h"
    manifest = {"work_order": "WO-RPR160", "peripheral": "wwdg", "layer": "HAL",
        "unit_verification": "uspec-gtest-v1", "hal_unit_isolation": "ll-fake-v1",
        "provided": [{"path": ll, "role": "provided_ll_driver", "sha256": hashed(ll)}],
        "provided_build": {"style": "cmsis", "defines": ["STM32N657xx"], "secure": True,
            "files": [{"path": rel, "sha256": hashed(rel)} for rel in files if rel.startswith("inputs/")]}}
    (ws / ".forge-run").mkdir()
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
    ll_fake.write(ws)
    ctx = sdk.ToolContext("forge-tests-mcp", "run_unit", "swe4-author", "SWE.4", ws, "rpr160")
    result = T.run_unit(ctx, T.RunIn(coverage=False))
    if result["status"] == "PASS":
        assert hashed(ll) == manifest["provided"][0]["sha256"]
        print("SYMPTOM_ABSENT")
        return 0
    if any("GTEST_FAIL:test_wwdg_registers.cpp#UT-001" in issue for issue in result["issues"]):
        print("SYMPTOM_PRESENT:provided LL unit register observation unavailable")
        return 1
    print("ERROR: fixture did not reach register assertion " + str(result["issues"])[:300])
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("ERROR: " + type(exc).__name__)
        sys.exit(2)
