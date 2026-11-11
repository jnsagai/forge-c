"""CAPA-243 (WO-F014-SWE2-SPIH-20261109-L46): the native HAL SWE.2 author on a PROVIDED ST (CMSIS) LL read the whole
provided header (SPI 121 kB) and parts of it again; 2 of 3 author cycles were refused CAPABILITY_LIMIT at ~115k input
tokens. The factory now writes an index of the provided LL (constant groups and functions by line range) and the HAL
SWE.2 prompt reads the header only by those ranges. Every other work order is unchanged."""
from __future__ import annotations

import json
import re

from forge_factory.brownfield.api_index import PROVIDED_INDEX, provided_text, write_provided
from forge_factory.brownfield.cmsis import provided_api
from forge_factory.workflow import builder

ST_HDR = """/** @defgroup CRC_LL CRC
  * @{
  */
/** @defgroup CRC_LL_EC_POLYLENGTH Polynomial length
  * @{
  */
#define LL_CRC_POLYLENGTH_32B 0x00000000U
/**
  * @}
  */
/** @defgroup CRC_LL_EF_Configuration Configuration
  * @{
  */
/**
  * @brief  Reset the CRC calculation unit.
  * @param  CRCx CRC Instance
  */
__STATIC_INLINE void LL_CRC_ResetCRCCalculationUnit(CRC_TypeDef *CRCx)
{
  SET_BIT(CRCx->CR, CRC_CR_RESET);
}

/**
  * @brief  Write given 32-bit data to the CRC calculator
  */
__STATIC_INLINE void LL_CRC_FeedData32(CRC_TypeDef *CRCx, uint32_t InData)
{
  WRITE_REG(CRCx->DR, InData);
}

__STATIC_INLINE uint32_t LL_CRC_ReadData32(const CRC_TypeDef *CRCx)
{
  return (uint32_t)(READ_REG(CRCx->DR));
}
"""
GREEN_HDR = "extern volatile uint32_t ll_crc_regs[];\nstatic inline void LL_CRC_Reset(void) { ll_crc_regs[0] = 1U; }\n"


def _ws(tmp_path, header, layer="HAL"):
    ws = tmp_path / f"ws-{layer}-{len(header)}"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / "software/ll").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": layer, "peripheral": "crc"}))
    (ws / "software/ll/stm32n6xx_ll_crc.h").write_text(header)
    return ws


def _prompts(dot):
    return dict(re.findall(r'\n  (\w+) \[[^\n]*?prompt="((?:[^"\\]|\\.)*)"', dot))


def test_index_lists_groups_and_functions_by_line_range():
    t = provided_text("software/ll/stm32n6xx_ll_crc.h", ST_HDR)
    lines = ST_HDR.splitlines()
    assert "- CRC_LL_EC_POLYLENGTH (Polynomial length): 4-10" in t
    assert "- `void LL_CRC_ResetCRCCalculationUnit(CRC_TypeDef *CRCx)`: 14-21" in t  # doc comment to closing brace
    assert lines[13].startswith("/**") and lines[20] == "}"
    assert "- `uint32_t LL_CRC_ReadData32(const CRC_TypeDef *CRCx)`: 31-34" in t
    assert t.count("\n- `") == 3 and "__STATIC_INLINE" not in t
    assert "never read the whole header" in t


def test_written_only_for_a_hal_on_a_provided_cmsis_ll(tmp_path):
    ws = _ws(tmp_path, ST_HDR)
    assert write_provided(ws) == PROVIDED_INDEX and (ws / PROVIDED_INDEX).is_file()
    for other in (_ws(tmp_path, GREEN_HDR), _ws(tmp_path, ST_HDR, layer="LL")):
        assert write_provided(other) is None and not (other / PROVIDED_INDEX).exists()


def test_hal_swe2_author_reads_the_index_not_the_whole_header(tmp_path):
    api = provided_api(_ws(tmp_path, ST_HDR))
    dot, _ = builder.build("WO-T", chunk_lines=150, layer="HAL", trace=True, isolation=True, peripheral="crc",
                           uspec_gtest=True, provided_api=api)
    p = _prompts(dot)["swe2_author"]
    assert "read_file .forge-run/provided-ll-api.md" in p
    assert "never the whole header" in p
    assert "stm32n6xx_ll_crc.h (PROVIDED LL, frozen)" not in p


def test_greenfield_hal_swe2_prompt_is_unchanged(tmp_path):
    dot, _ = builder.build("WO-T", chunk_lines=150, layer="HAL", trace=True, isolation=True, peripheral="crc",
                           uspec_gtest=True)
    p = _prompts(dot)["swe2_author"]
    assert "stm32n6xx_ll_crc.h (PROVIDED LL, frozen) and" in p
    assert "provided-ll-api.md" not in p
