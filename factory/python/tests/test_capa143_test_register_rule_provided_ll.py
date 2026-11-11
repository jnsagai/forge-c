"""CAPA-143 (WO-F014-SWE5-CRCHAL-20261103-L31B): the HAL prompts of a work order on a provided ST (CMSIS) LL told the
SWE.5 target / SWE.6 scenario authors to check 'll_crc_regs[LL_CRC_<REG>_OFFSET / 4U]' bits and the SWE.2/SWE.3 notes
that the driver uses that extern array; the provided LL has neither, so a target test did not build. The greenfield
register sentences become the provided-LL ones (CMSIS instance, provided LL read functions); greenfield graphs are
byte-identical."""
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest
from forge_factory.brownfield.cmsis import provided_api
from forge_factory.workflow import builder, prompts

ST_HDR = ('#include "stm32n6xx.h"\n'
          "__STATIC_INLINE void LL_CRC_ResetCRCCalculationUnit(CRC_TypeDef *CRCx)\n{\n  SET_BIT(CRCx->CR, CRC_CR_RESET);\n}\n"
          "__STATIC_INLINE void LL_CRC_FeedData32(CRC_TypeDef *CRCx, uint32_t InData)\n{\n  WRITE_REG(CRCx->DR, InData);\n}\n"
          "__STATIC_INLINE uint32_t LL_CRC_ReadData32(const CRC_TypeDef *CRCx)\n{\n"
          "  return (uint32_t)(READ_REG(CRCx->DR));\n}\n")
GREENFIELD = re.compile(r"ll_crc_regs|LL_CRC_<REG>_OFFSET|LL_CRC_REG_COUNT")
NODES = ("swe2_inspector", "swe3_inspector", "swe3_hal_author", "swe5_target_author", "swe6_test_author")
# host-path-free sha256 of the greenfield CRC HAL graph at 01bd80dc (the parent of the fix)
GREEN_SHA = "2469e30060fb801763d20cd29d77e960f8ce7bead84984d1599f8cbae49be285"


@pytest.fixture(autouse=True)
def _reset():
    yield
    prompts.LAYER["layer"] = "LL+HAL"
    prompts.PROVIDED_API["api"] = None


def _api(tmp_path, header=ST_HDR):
    ws = tmp_path / "ws"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / "software/ll").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL", "peripheral": "crc"}))
    (ws / "software/ll/stm32n6xx_ll_crc.h").write_text(header)
    return provided_api(ws)


def _graph(api):
    dot, _ = builder.build("WO-RPR143", chunk_lines=150, layer="HAL", trace=True, isolation=True, peripheral="crc",
                           uspec_gtest=True, **({"provided_api": api} if api else {}))
    return dot.replace(builder._env(), "<ENV>").replace(sys.executable, "<PY>")


def _prompts(dot):
    return dict(re.findall(r'\n  (\w+) \[[^\n]*?prompt="((?:[^"\\]|\\.)*)"', dot))


def test_hal_on_st_ll_prompts_name_the_cmsis_instance_not_a_register_array(tmp_path):
    p = _prompts(_graph(_api(tmp_path)))
    for n in NODES:
        assert not GREENFIELD.search(p[n]), (n, GREENFIELD.search(p[n]).group(0))
    for n in ("swe5_target_author", "swe6_test_author"):
        assert "LL_CRC_ReadData32(CRC)" in p[n] and "CRC-><REG> & the device header's CRC_<REG>_<FIELD>_Msk" in p[n]
        assert "never define a register block or the instance CRC" in p[n]
    assert "reaches the CRC registers only through the provided LL functions with the instance CRC" in p["swe3_inspector"]
    assert "Never define a register block or the instance CRC" in p["swe3_hal_author"]


def test_greenfield_hal_graph_is_byte_identical():
    dot = _graph(None)
    assert hashlib.sha256(dot.encode()).hexdigest() == GREEN_SHA
    assert "ll_crc_regs[LL_CRC_<REG>_OFFSET / 4U] bits" in _prompts(dot)["swe5_target_author"]


def test_provided_registers_is_identity_without_a_greenfield_sentence(tmp_path):
    api = _api(tmp_path)
    text = "Write the test. Use only the HAL API. No printf."
    assert prompts.provided_registers(text, api) == text


def test_without_a_read_function_the_rule_names_the_instance_only(tmp_path):
    hdr = ST_HDR.split("__STATIC_INLINE uint32_t LL_CRC_ReadData32")[0]
    api = _api(tmp_path, hdr)
    out = prompts.provided_registers("on HAL return values and ll_crc_regs[LL_CRC_<REG>_OFFSET / 4U] bits. No printf, "
                                     "no stdlib, no ll_crc_regs definition (the linker places it).", api)
    assert "(e.g." not in out and "CRC-><REG>" in out and "ll_crc_regs" not in out
