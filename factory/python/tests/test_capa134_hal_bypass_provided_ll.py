"""CAPA-134 (L27 follow-up): with ST's LL the generated test double keeps the device header, so a HAL that reaches
the registers directly (L27: `extern volatile uint32_t CRC_registers[]` + WRITE_REG/MODIFY_REG) still builds; the
SWE.3 implementation check now refuses register access that bypasses a provided CMSIS LL."""
import hashlib
import json

import pytest
from forge_factory.inspection.implementation import check_implementation

LL = ("#include \"stm32n6xx.h\"\n__STATIC_INLINE void LL_CRC_FeedData32(CRC_TypeDef *CRCx, uint32_t InData)\n{\n"
      "  WRITE_REG(CRCx->DR, InData);\n}\n#define LL_CRC_WriteReg(__INSTANCE__, __REG__, __VALUE__) "
      "WRITE_REG(__INSTANCE__->__REG__, __VALUE__)\n")
GREEN_LL = ("#include <stdint.h>\nextern volatile uint32_t ll_crc_regs[256];\n"
            "static inline void LL_CRC_FeedData32(uint32_t InData)\n{\n  ll_crc_regs[0] = InData;\n}\n")
HAL_H = ("#ifndef STM32N6XX_HAL_CRC_H\n#define STM32N6XX_HAL_CRC_H\n#include <stdint.h>\n#include \"stm32n6xx_ll_crc.h\"\n"
         "void HAL_CRC_Feed(uint32_t w);\n#endif /* STM32N6XX_HAL_CRC_H */\n")
BODY = "#include \"stm32n6xx_hal_crc.h\"\n{decl}void HAL_CRC_Feed(uint32_t w)\n{{\n    /* CRC->DR = w; */\n    {stmt}\n}}\n"


def _findings(tmp_path, stmt, decl="", ll=LL):
    ws = tmp_path / f"ws{abs(hash((stmt, decl, ll)))}"
    for rel, text in {"software/ll/stm32n6xx_ll_crc.h": ll, "software/hal/stm32n6xx_hal_crc.h": HAL_H,
                      "software/hal/stm32n6xx_hal_crc.c": BODY.format(decl=decl, stmt=stmt)}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text)
    (ws / ".forge-run").mkdir()
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL", "peripheral": "crc", "provided": [
        {"path": "software/ll/stm32n6xx_ll_crc.h", "sha256": hashlib.sha256(ll.encode()).hexdigest()}]}))
    return [f for f in check_implementation(ws)["major_findings"] if f.startswith("IMPL:HAL_BYPASSES_LL:")]


@pytest.mark.parametrize("stmt,decl,token", [
    ("CRC->DR = w;", "", "CRC->"),
    ("WRITE_REG(CRC->DR, w);", "", "WRITE_REG("),
    ("LL_CRC_WriteReg(CRC, DR, w);", "", "LL_CRC_WriteReg("),
    ("forge_host_crc.DR = w;", "", "forge_host_crc"),
    ("CRC_registers[0] = w;", "extern volatile uint32_t CRC_registers[];\n", "volatile uint32_t CRC_registers["),
    ("*(volatile uint32_t *)CRC_BASE = w;", "", "CRC_BASE"),
])
def test_direct_register_access_is_refused(tmp_path, stmt, decl, token):
    f = _findings(tmp_path, stmt, decl)
    assert any("software/hal/stm32n6xx_hal_crc.c:" in x and f":{token} (" in x for x in f), f


def test_calls_through_the_provided_ll_and_comments_are_fine(tmp_path):
    assert _findings(tmp_path, "LL_CRC_FeedData32(CRC, w);") == []


def test_greenfield_provided_ll_is_not_checked(tmp_path):
    assert _findings(tmp_path, "ll_crc_regs[0] = w;", ll=GREEN_LL) == []  # the unit build refuses it there
