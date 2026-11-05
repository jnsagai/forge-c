"""RPR-128 (local run WO-F014-SWE3-CRCHAL-20261103-L27, Omniverse2, CRC HAL order 0014m on run/gen9 378aa68a,
2026-11-03): a HAL work order built on an ST-delivered (FROZEN brownfield) LL is not buildable on the native HAL path.
(1) workflow/ll_fake.generate raises "no static inline LL function in the provided header" on ST's LL headers, which
declare their functions with the CMSIS macro __STATIC_INLINE and take the instance pointer (CRC_TypeDef *CRCx), so the
HAL unit tests (which assume the generated LL test double) get no double. (2) workorder.prepare copies only the provided
LL header (which includes stm32n6xx.h) into the HAL workspace: no inputs/vendor/include, no host device directory with
the host CMSIS core stub, no defines - the first target compile failed with "stm32n6xx.h: No such file or directory".

Scenario (synthetic, ST style, no vendor files, no git-ignored inputs; writes only to a scratch dir):
(a) the real ll_fake.generate of the revision under test on a minimal ST-style CRC LL header (__STATIC_INLINE,
WRITE_REG / MODIFY_REG / SET_BIT on CRCx->..., a CRC_TypeDef stub device header); the double, when generated, must build
and record the scalar arguments in C and compile as C++ (the GoogleTest unit test includes it).
(b) the real workorder.prepare of a HAL work order (tracked IWDG RM inputs) with --provided-from a synthetic FROZEN
CMSIS LL work order (ST-style IWDG LL, a vendor stm32n6xx.h and an Arm-only core_cm55.h, all six gates PASS); the HAL
workspace must hold the vendor includes byte-identical, host and target flags must name them, and a HAL unit test on
the generated double (HAL calling LL_IWDG_Enable(IWDG)) must build and run on the host.
Symptom: (a) raises or the double does not build/record, or (b) the vendor inputs/flags are missing or the HAL unit test
does not build. Controls: the double of a greenfield `static inline` LL is byte-identical to the baseline's (frozen
sha256); the brownfield LL work order's own host flags are unchanged (an altered control is an error, not ABSENT)."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SIG = "a HAL work order on an ST (CMSIS) LL gets no LL test double and no vendor build inputs"
GREEN = ("#ifndef STM32N6XX_LL_CRC_H\n#define STM32N6XX_LL_CRC_H\n#include <stdint.h>\n#define LL_CRC_REG_COUNT 256U\n"
         "extern volatile uint32_t ll_crc_regs[LL_CRC_REG_COUNT];\n#define LL_CRC_DR_OFFSET 0x000U\n"
         "#define LL_CRC_CR_OFFSET 0x008U\n#define LL_CRC_CR_RESET_MSK 0x00000001U\n"
         "/** @brief Set CRC_CR.RESET. */\nstatic inline void LL_CRC_ResetCRCCalculationUnit(void)\n{\n"
         "  ll_crc_regs[LL_CRC_CR_OFFSET / 4U] |= LL_CRC_CR_RESET_MSK;\n}\n"
         "/** @brief Write CRC_DR. */\nstatic inline void LL_CRC_FeedData32(uint32_t InData)\n{\n"
         "  ll_crc_regs[LL_CRC_DR_OFFSET / 4U] = InData;\n}\n"
         "/** @brief Read CRC_DR. */\nstatic inline uint32_t LL_CRC_ReadData32(void)\n{\n"
         "  return ll_crc_regs[LL_CRC_DR_OFFSET / 4U];\n}\n#endif\n")
GREEN_SHA = "a7a3fba4f4d3fd0eaf6c92fe87ab8f68edf9650dde0994a6bb809315fdb60a8a"  # generate(GREEN, "ll_crc_regs") on the baseline a88b61a5
ST_CRC = ("#ifndef STM32N6xx_LL_CRC_H\n#define STM32N6xx_LL_CRC_H\n#ifdef __cplusplus\nextern \"C\" {\n#endif\n"
          "#include \"stm32n6xx.h\"\n#if defined(CRC)\n#define LL_CRC_POLYLENGTH_16B CRC_CR_POLYSIZE_0\n"
          "/**\n  * @brief  Reset the CRC calculation unit.\n  * @param  CRCx CRC Instance\n  */\n"
          "__STATIC_INLINE void LL_CRC_ResetCRCCalculationUnit(CRC_TypeDef *CRCx)\n{\n  SET_BIT(CRCx->CR, CRC_CR_RESET);\n}\n"
          "__STATIC_INLINE void LL_CRC_SetPolynomialSize(CRC_TypeDef *CRCx, uint32_t PolySize)\n{\n"
          "  MODIFY_REG(CRCx->CR, CRC_CR_POLYSIZE, PolySize);\n}\n"
          "__STATIC_INLINE void LL_CRC_FeedData32(CRC_TypeDef *CRCx, uint32_t InData)\n{\n  WRITE_REG(CRCx->DR, InData);\n}\n"
          "__STATIC_INLINE uint32_t LL_CRC_ReadData32(const CRC_TypeDef *CRCx)\n{\n"
          "  return (uint32_t)(READ_REG(CRCx->DR));\n}\n"
          "__STATIC_INLINE uint16_t LL_CRC_ReadData16(const CRC_TypeDef *CRCx)\n{\n  return (uint16_t)READ_REG(CRCx->DR);\n}\n"
          "#endif\n#ifdef __cplusplus\n}\n#endif\n#endif\n")
CRC_DEV = ("#ifndef STM32N6XX_H\n#define STM32N6XX_H\n#include <stdint.h>\n#define __IO volatile\n"
           "#define __STATIC_INLINE static inline\ntypedef struct { __IO uint32_t DR; __IO uint32_t IDR; __IO uint32_t CR; "
           "uint32_t RESERVED; __IO uint32_t INIT; __IO uint32_t POL; } CRC_TypeDef;\n#define CRC_CR_RESET 0x1UL\n"
           "#define CRC_CR_POLYSIZE 0x18UL\n#define CRC_CR_POLYSIZE_0 0x8UL\n#define CRC ((CRC_TypeDef *)0x56024C00UL)\n"
           "#define SET_BIT(REG, BIT) ((REG) |= (BIT))\n#define READ_REG(REG) ((REG))\n"
           "#define WRITE_REG(REG, VAL) ((REG) = (VAL))\n"
           "#define MODIFY_REG(REG, CLEARMASK, SETMASK) WRITE_REG((REG), (((READ_REG(REG)) & (~(CLEARMASK))) | (SETMASK)))\n"
           "#endif\n")
CRC_TEST = ("#include <stdio.h>\n#define LL_FAKE_IMPLEMENTATION\n#include \"stm32n6xx_ll_crc.h\"\nint main(void)\n{\n"
            "    ll_fake_reset();\n    LL_CRC_ResetCRCCalculationUnit(CRC);\n    LL_CRC_SetPolynomialSize(CRC, 2U);\n"
            "    LL_CRC_FeedData32(CRC, 0x1234U);\n    ll_fake_return_from(LL_FAKE_LL_CRC_ReadData32, 1U, 0xABCDU);\n"
            "    int ok = (ll_fake_calls(LL_FAKE_LL_CRC_FeedData32) == 1U) && (ll_fake_last_arg(LL_FAKE_LL_CRC_FeedData32, 0U)"
            " == 0x1234U) && (ll_fake_last_arg(LL_FAKE_LL_CRC_SetPolynomialSize, 0U) == 2U) && (LL_CRC_ReadData32(CRC) == "
            "0xABCDU) && (ll_fake_index_of(LL_FAKE_LL_CRC_ResetCRCCalculationUnit, 1U) < "
            "ll_fake_index_of(LL_FAKE_LL_CRC_FeedData32, 1U));\n    printf(\"%s\\n\", ok ? \"FAKE_OK\" : \"FAKE_WRONG\");\n"
            "    return 0;\n}\n")
ST_IWDG = ("#ifndef STM32N6xx_LL_IWDG_H\n#define STM32N6xx_LL_IWDG_H\n#include \"stm32n6xx.h\"\n"
           "#define LL_IWDG_KEY_ENABLE 0x0000CCCCU\n"
           "__STATIC_INLINE void LL_IWDG_Enable(IWDG_TypeDef *IWDGx)\n{\n  WRITE_REG(IWDGx->KR, LL_IWDG_KEY_ENABLE);\n}\n"
           "__STATIC_INLINE uint32_t LL_IWDG_IsReady(const IWDG_TypeDef *IWDGx)\n{\n"
           "  return ((READ_BIT(IWDGx->SR, 0x7FU) == 0U) ? 1UL : 0UL);\n}\n#endif\n")
IWDG_DEV = ("#ifndef STM32N6XX_H\n#define STM32N6XX_H\n#include \"core_cm55.h\"\n"
            "typedef struct { __IO uint32_t KR; __IO uint32_t PR; __IO uint32_t RLR; __IO uint32_t SR; } IWDG_TypeDef;\n"
            "#define IWDG ((IWDG_TypeDef *)0x56004800UL)\n#define WRITE_REG(REG, VAL) ((REG) = (VAL))\n"
            "#define READ_BIT(REG, BIT) ((REG) & (BIT))\n#endif\n")
ARM_CORE = "#ifndef __arm__\n#error \"CMSIS core header: Arm only\"\n#endif\n"
HAL_H = "#ifndef HAL_H\n#define HAL_H\n#include \"stm32n6xx_ll_iwdg.h\"\nvoid HAL_IWDG_Start(void);\n#endif\n"
HAL_C = "#include \"stm32n6xx_hal_iwdg.h\"\nvoid HAL_IWDG_Start(void)\n{\n    LL_IWDG_Enable(IWDG);\n}\n"
HAL_TEST = ("#include <stdio.h>\n#define LL_FAKE_IMPLEMENTATION\n#include \"stm32n6xx_hal_iwdg.h\"\nint main(void)\n{\n"
            "    ll_fake_reset();\n    HAL_IWDG_Start();\n"
            "    printf(\"%s\\n\", ll_fake_calls(LL_FAKE_LL_IWDG_Enable) == 1U ? \"HAL_OK\" : \"HAL_WRONG\");\n"
            "    return 0;\n}\n")


def _sha(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def _build_run(argv: list[str], exe: Path, cwd: Path) -> str:
    b = subprocess.run(argv + ["-o", str(exe)], capture_output=True, text=True, cwd=cwd, timeout=120)
    if b.returncode:
        return "BUILD_FAIL:" + (b.stderr.strip().splitlines() or ["?"])[-1][:120]
    return subprocess.run([str(exe)], capture_output=True, text=True, cwd=cwd, timeout=60).stdout.strip()


def fake_symptom(ll_fake, d: Path) -> str | None:
    try:
        fake = ll_fake.generate(ST_CRC, "ll_crc_regs")
    except ValueError as exc:
        return f"generate:{exc}"
    (d / "crc").mkdir()
    (d / "crc/stm32n6xx_ll_crc.h").write_text(fake)
    (d / "crc/stm32n6xx.h").write_text(CRC_DEV)
    (d / "crc/t.c").write_text(CRC_TEST)
    (d / "crc/t.cpp").write_text("extern \"C\" {\n#include \"stm32n6xx_ll_crc.h\"\n}\nint main() { return 0; }\n")
    out = _build_run(["clang", "-std=c11", "-Wall", "-Werror=implicit-function-declaration", f"-I{d / 'crc'}",
                      str(d / "crc/t.c")], d / "crc/t", d)
    if out != "FAKE_OK":
        return f"fake_c:{out}"
    cxx = subprocess.run(["clang++", "-std=c++17", "-fsyntax-only", f"-I{d / 'crc'}", str(d / "crc/t.cpp")],
                         capture_output=True, text=True, timeout=120)
    return None if cxx.returncode == 0 else "fake_cxx:" + (cxx.stderr.strip().splitlines() or ["?"])[0][-120:]


def build_symptom(d: Path) -> tuple[str | None, list[str] | None]:
    from forge_factory import workorder as WO
    from forge_factory.brownfield import cmsis
    from forge_factory.common import REPO_ROOT
    from forge_factory.inspection import engine
    from forge_factory.workflow import ll_fake

    spec = json.loads((REPO_ROOT / "examples/0009b-iwdg-hal/workorder.json").read_text())
    rm = REPO_ROOT / "examples/0009-iwdg-st/inputs"
    spec["inputs"] = [{"path": str(rm / "RM0486-rev4-ch59-iwdg.md"), "role": "reference_manual_iwdg_chapter"},
                      {"path": str(rm / "RM0486-rev4-memory-map-excerpt-iwdg.md"), "role": "reference_manual_memory_map"}]
    spec.pop("simulation_performance", None)
    ex = d / "ex-rpr128-iwdg-hal"
    ex.mkdir()
    (ex / "workorder.json").write_text(json.dumps(spec))
    src = Path(os.environ["FORGE_STATE_DIR"]) / "workorders/WO-RPR128-LL/workspace"
    files = {"software/ll/stm32n6xx_ll_iwdg.h": ST_IWDG, "inputs/vendor/include/stm32n6xx.h": IWDG_DEV,
             "inputs/vendor/include/core_cm55.h": ARM_CORE}
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text)
    (src / ".forge-run").mkdir()
    build = {"style": "cmsis", "defines": ["STM32N657xx"], "secure": True}
    (src / ".forge-run/manifest.json").write_text(json.dumps({
        "work_order": "WO-RPR128-LL", "layer": "LL", "peripheral": "iwdg", "code_mode": "FROZEN",
        "delivery": {"code_mode": "FROZEN", "build": build},
        "delivered": [{"path": p, "sha256": _sha(t), "bytes": len(t.encode()),
                       "role": "delivered_code" if p.startswith("software/") else "delivered_dependency"}
                      for p, t in files.items()]}))
    control = cmsis.host_flags(src)
    if control != ["-isystem", str(src / cmsis.HOST_DIR), "-DSTM32N657xx"]:
        return "control", control
    engine.Store.gate = lambda self, ph: {"decision": "PASS"}  # the synthetic source LL passed its six gates
    ws, _man = WO.prepare(ex, "WO-RPR128-HAL", "WO-RPR128-LL")
    vendor = ws / "inputs/vendor/include/stm32n6xx.h"
    if not vendor.is_file() or vendor.read_text() != IWDG_DEV:
        return "vendor_inputs:no inputs/vendor/include in the HAL workspace", None
    host, target = cmsis.host_flags(ws), cmsis.target_flags(ws)
    if str(ws / cmsis.VENDOR_DIR) not in target or "-DSTM32N657xx" not in host:
        return f"flags:host={host[:2]} target={target[:2]}", None
    try:
        ll_fake.write(ws)
    except ValueError as exc:
        return f"hal_fake:{exc}", None
    (ws / "software/hal").mkdir(parents=True, exist_ok=True)
    (ws / "software/hal/stm32n6xx_hal_iwdg.h").write_text(HAL_H)
    (ws / "software/hal/stm32n6xx_hal_iwdg.c").write_text(HAL_C)
    (d / "hal_t.c").write_text(HAL_TEST)
    out = _build_run(["clang", "-std=c11", "-Wall", "-Werror=implicit-function-declaration", *host,
                      f"-I{ws / ll_fake.FAKE_DIR}", f"-I{ws / 'software/hal'}", str(d / "hal_t.c"),
                      str(ws / "software/hal/stm32n6xx_hal_iwdg.c")], d / "hal_t", d)
    return (None if out == "HAL_OK" else f"hal_unit:{out}"), None


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        os.environ["FORGE_STATE_DIR"], os.environ["FORGE_EVENTS_DIR"] = str(d / "state"), str(d / "events")
        from forge_factory.workflow import ll_fake

        if _sha(ll_fake.generate(GREEN, "ll_crc_regs")) != GREEN_SHA:
            print("REPRODUCER_ERROR:CONTROL_CHANGED:the double of a greenfield static inline LL is not byte-identical")
            return 2
        fake = fake_symptom(ll_fake, d)
        build, control = build_symptom(d)
        if build == "control":
            print(f"REPRODUCER_ERROR:CONTROL_CHANGED:brownfield LL host flags {control}")
            return 2
    if fake or build:
        print(f"observed: fake={fake} build={build}")
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
