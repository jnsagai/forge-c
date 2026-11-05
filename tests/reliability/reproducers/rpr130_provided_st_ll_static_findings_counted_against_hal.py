"""RPR-130 (CAPA-128 follow-up for WO-F014-SWE3-CRCHAL-20261103-L27, CRC HAL on the ST CRC LL
WO-F014-SWE6-CRCL-20261103-L24, 2026-11-03): on the HAL path, cppcheck findings located in the PROVIDED, FROZEN ST LL
header (MISRA-20.7 at stm32n6xx_ll_crc.h:145/153, the unparenthesised macro parameters of LL_CRC_WriteReg/ReadReg)
were counted as HAL issues: forge-analysis-mcp.cppcheck FAILED the HAL author for code it may not change, while the LL
work order itself classes the same findings as DELIVERED_CODE (owner findings, never repaired).

Scenario (synthetic, ST style; writes only to a scratch dir; tracked IWDG RM inputs): the real workorder.prepare of a
HAL work order with --provided-from a synthetic FROZEN CMSIS LL work order whose ST-style header has an ST register
macro with unparenthesised parameters (MISRA C:2012 20.7), then the real cppcheck operation on the HAL workspace with a
clean HAL source. Symptom: a MISRA/cppcheck finding located in the provided LL header is a plain issue (not
DELIVERED_CODE) or the result FAILs. Controls: the same LL work order's own cppcheck classes the header finding as
DELIVERED_CODE; a finding in the HAL's own source (MISRA 15.5, a second return) stays a HAL issue and FAILs (a
loosened check is an error, not ABSENT). Needs cppcheck with its MISRA addon (REPRODUCER_ERROR otherwise)."""
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

SIG = "cppcheck findings in the provided FROZEN LL header are counted as HAL issues"
ST_IWDG = ("#ifndef STM32N6xx_LL_IWDG_H\n#define STM32N6xx_LL_IWDG_H\n#include \"stm32n6xx.h\"\n"
           "#define LL_IWDG_WriteReg(__INSTANCE__, __REG__, __VALUE__) WRITE_REG(__INSTANCE__->__REG__, __VALUE__)\n"
           "__STATIC_INLINE void LL_IWDG_Enable(IWDG_TypeDef *IWDGx)\n{\n  WRITE_REG(IWDGx->KR, 0x0000CCCCU);\n}\n"
           "#endif\n")
IWDG_DEV = ("#ifndef STM32N6XX_H\n#define STM32N6XX_H\n#include \"core_cm55.h\"\n"
            "typedef struct { __IO uint32_t KR; } IWDG_TypeDef;\n#define IWDG ((IWDG_TypeDef *)0x56004800UL)\n"
            "#define WRITE_REG(REG, VAL) ((REG) = (VAL))\n#endif\n")
ARM_CORE = "#include <stdint.h>\n#define __IO volatile\n#define __STATIC_INLINE static inline\n"
HAL_H = ("#ifndef STM32N6XX_HAL_IWDG_H\n#define STM32N6XX_HAL_IWDG_H\n#include <stdint.h>\n"
         "#include \"stm32n6xx_ll_iwdg.h\"\nuint32_t HAL_IWDG_Start(uint32_t on);\n#endif /* STM32N6XX_HAL_IWDG_H */\n")
HAL_C = ("#include \"stm32n6xx_hal_iwdg.h\"\nuint32_t HAL_IWDG_Start(uint32_t on)\n{\n    uint32_t status = 1U;\n"
         "    if (on != 0U)\n    {\n        LL_IWDG_Enable(IWDG);\n        status = 0U;\n    }\n    return status;\n}\n")
HAL_C_BAD = ("#include \"stm32n6xx_hal_iwdg.h\"\nuint32_t HAL_IWDG_Start(uint32_t on)\n{\n    if (on != 0U)\n    {\n"
             "        LL_IWDG_Enable(IWDG);\n        return 0U;\n    }\n    return 1U;\n}\n")


def _sha(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def main() -> int:
    if not shutil.which("cppcheck"):
        print("REPRODUCER_ERROR:TOOL_MISSING:cppcheck")
        return 2
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        os.environ["FORGE_STATE_DIR"], os.environ["FORGE_EVENTS_DIR"] = str(d / "state"), str(d / "events")
        from forge_factory import workorder as WO
        from forge_factory.common import REPO_ROOT
        from forge_factory.inspection import engine
        from forge_factory.mcp import sdk
        from forge_factory.mcp.servers import analysis as A

        if not Path(A.MISRA_ADDON).is_file():
            print("REPRODUCER_ERROR:TOOL_MISSING:cppcheck MISRA addon")
            return 2
        spec = json.loads((REPO_ROOT / "examples/0009b-iwdg-hal/workorder.json").read_text())
        rm = REPO_ROOT / "examples/0009-iwdg-st/inputs"
        spec["inputs"] = [{"path": str(rm / "RM0486-rev4-ch59-iwdg.md"), "role": "reference_manual_iwdg_chapter"},
                          {"path": str(rm / "RM0486-rev4-memory-map-excerpt-iwdg.md"),
                           "role": "reference_manual_memory_map"}]
        spec.pop("simulation_performance", None)
        ex = d / "ex-rpr130-iwdg-hal"
        ex.mkdir()
        (ex / "workorder.json").write_text(json.dumps(spec))
        src = d / "state/workorders/WO-RPR130-LL/workspace"
        files = {"software/ll/stm32n6xx_ll_iwdg.h": ST_IWDG, "inputs/vendor/include/stm32n6xx.h": IWDG_DEV,
                 "inputs/vendor/include/core_cm55.h": ARM_CORE}
        for rel, text in files.items():
            (src / rel).parent.mkdir(parents=True, exist_ok=True)
            (src / rel).write_text(text)
        (src / ".forge-run").mkdir()
        (src / ".forge-run/manifest.json").write_text(json.dumps({
            "work_order": "WO-RPR130-LL", "layer": "LL", "peripheral": "iwdg", "code_mode": "FROZEN",
            "delivery": {"code_mode": "FROZEN", "build": {"style": "cmsis", "defines": ["STM32N657xx"], "secure": True}},
            "delivered": [{"path": p, "sha256": _sha(t), "bytes": len(t.encode()),
                           "role": "delivered_code" if p.startswith("software/") else "delivered_dependency"}
                          for p, t in files.items()]}))

        def cppcheck(ws: Path) -> dict:
            return A.cppcheck(sdk.ToolContext("forge-analysis-mcp", "cppcheck", "swe3-author", "SWE.3", ws, "r"),
                              A.AnalyzeIn())

        own = cppcheck(src)
        if not any(i.startswith("DELIVERED_CODE:MISRA-20.7:software/ll/stm32n6xx_ll_iwdg.h") for i in own["issues"]):
            print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:LL work order cppcheck {own['status']} {own['issues'][:3]}")
            return 2
        engine.Store.gate = lambda self, ph: {"decision": "PASS"}
        ws, _ = WO.prepare(ex, "WO-RPR130-HAL", "WO-RPR130-LL")
        (ws / "software/hal").mkdir(parents=True, exist_ok=True)
        (ws / "software/hal/stm32n6xx_hal_iwdg.h").write_text(HAL_H)
        (ws / "software/hal/stm32n6xx_hal_iwdg.c").write_text(HAL_C_BAD)
        bad = cppcheck(ws)
        if bad["status"] != "FAIL" or not any(i.startswith("MISRA-15.5:stm32n6xx_hal_iwdg.c") for i in bad["issues"]):
            print(f"REPRODUCER_ERROR:CHECK_LOOSENED:HAL's own finding not an issue: {bad['status']} {bad['issues'][:4]}")
            return 2
        (ws / "software/hal/stm32n6xx_hal_iwdg.c").write_text(HAL_C)
        r = cppcheck(ws)
    in_ll = [i for i in r["issues"] if "stm32n6xx_ll_iwdg.h" in i and not i.startswith("DELIVERED_CODE:")]
    if in_ll or r["status"] != "PASS":
        print(f"observed: {r['status']} {r['issues'][:4]}")
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
