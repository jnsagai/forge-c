"""RPR-141 (local run WO-F014-SWE3-CRCHAL-20261103-L31D, Omniverse2, 2026-11-04): the SWE.3 inspection of the CRC HAL on
the provided ST CRC LL (CAPA-128 provided_build, CAPA-130 FROZEN provided file) failed two required items that the HAL
author cannot satisfy: SWE3-07 counted 41 Cube2-guideline violations located INSIDE the provided FROZEN ST LL header
(software/ll/stm32n6xx_ll_crc.h: ST's guard, macro and parameter naming), and SWE3-08 reported
REGMAP:NO_REGISTER_DEFINES because the register-map check looks for generated LL_<PPP>_* defines in the LL header - a
HAL on a provided CMSIS LL generates none and must reach the registers only through the LL (CAPA-134).

Scenario (synthetic workspace in a scratch dir; no vendor text): a CRC HAL work order whose manifest carries a FROZEN
provided LL header (written here in ST's style: CamelCase parameters, mixed-case guard macro) and a CMSIS
provided_build, plus the HAL's own header/source. Symptom: a guideline violation located in the provided file is a
HAL violation, or the register-map check raises REGMAP:NO_REGISTER_DEFINES for that HAL. Controls: a violation in the
HAL's own file is still reported; the same workspace WITHOUT the provided_build/FROZEN marking (a greenfield HAL whose
LL header has no defines) still gets REGMAP:NO_REGISTER_DEFINES (that path is unchanged)."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

SIG = "SWE.3 guideline/register-map checks charge a HAL for its provided FROZEN ST LL"
LL = ("#ifndef STM32N6xx_LL_CRC_H\n#define STM32N6xx_LL_CRC_H\n#include <stdint.h>\n"
      "typedef struct { volatile uint32_t DR; volatile uint32_t CR; } CRC_TypeDef;\n"
      "static inline void LL_CRC_SetInitialData(CRC_TypeDef *CRCx, uint32_t InitCrc)\n{\n    CRCx->DR = InitCrc;\n}\n"
      "#endif /* STM32N6xx_LL_CRC_H */\n")
HAL_H = ("#ifndef STM32N6XX_HAL_CRC_H\n#define STM32N6XX_HAL_CRC_H\n#include <stdint.h>\n#include \"stm32n6xx_ll_crc.h\"\n"
         "typedef enum { HAL_OK = 0, HAL_ERROR = 1 } hal_status_t;\nhal_status_t HAL_CRC_Init(uint32_t init_value);\n"
         "#endif /* STM32N6XX_HAL_CRC_H */\n")
HAL_C = ("#include \"stm32n6xx_hal_crc.h\"\nhal_status_t HAL_CRC_Init(uint32_t init_value)\n{\n"
         "    hal_status_t status = HAL_ERROR;\n    if (init_value != 0U)\n    {\n        status = HAL_OK;\n    }\n"
         "    return status;\n}\n")
STRAY = "#ifndef X\n#define X 1\n#endif\n"  # the HAL author's own badly named/guarded file (a real finding)


def workspace(root: Path, provided: bool) -> Path:
    ws = root / ("provided" if provided else "greenfield")
    man = {"work_order": "WO-RPR141", "layer": "HAL", "peripheral": "crc"}
    if provided:
        man["provided"] = [{"path": "software/ll/stm32n6xx_ll_crc.h", "delivered_code_mode": "FROZEN",
                            "role": "provided_ll_driver", "source_work_order": "WO-LL-ST"}]
        man["provided_build"] = {"style": "cmsis", "defines": [], "files": [], "secure": False,
                                 "source_work_order": "WO-LL-ST", "rule": "read-only"}
    else:
        man["provided"] = [{"path": "software/ll/stm32n6xx_ll_crc.h", "role": "provided_ll_driver",
                            "source_work_order": "WO-LL-GF"}]
    for rel, text in {".forge-run/manifest.json": json.dumps(man), "software/ll/stm32n6xx_ll_crc.h": LL,
                      "software/hal/stm32n6xx_hal_crc.h": HAL_H, "software/hal/stm32n6xx_hal_crc.c": HAL_C,
                      "software/hal/probe.h": STRAY}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text)
    return ws


def main() -> int:
    from forge_factory.inspection.guideline import check_workspace
    from forge_factory.inspection.regmap import check_regmap

    td = Path(tempfile.mkdtemp(prefix="rpr141-"))
    try:
        pws, gws = workspace(td, True), workspace(td, False)
        g = check_workspace(pws)
        own = [v for v in g["violations"] if v["file"] == "software/hal/probe.h"]
        if not own:
            print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the HAL's own stray file has no violation ({g['verdict']})")
            return 2
        ll_hits = [v for v in g["violations"] if v["file"] == "software/ll/stm32n6xx_ll_crc.h"]
        greenfield = check_regmap(gws)
        if "REGMAP:NO_REGISTER_DEFINES" not in greenfield["major_findings"]:
            print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:greenfield regmap control changed: "
                  + json.dumps(greenfield["major_findings"])[:160])
            return 2
        reg = check_regmap(pws)
        symptoms = []
        if ll_hits:
            symptoms.append(f"{len(ll_hits)} guideline violations in the provided FROZEN LL counted for the HAL "
                            f"({sorted({v['rule'] for v in ll_hits})})")
        if "REGMAP:NO_REGISTER_DEFINES" in reg["major_findings"]:
            symptoms.append("REGMAP:NO_REGISTER_DEFINES for a HAL on a provided CMSIS LL")
    finally:
        shutil.rmtree(td, ignore_errors=True)
    if symptoms:
        print("observed: " + "; ".join(symptoms))
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
