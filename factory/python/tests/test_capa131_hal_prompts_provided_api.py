"""CAPA-131 (CRC HAL on the ST CRC LL, L27 follow-up): the HAL author prompts showed the greenfield LL API
(LL_CRC_FeedData32(p_data[i])) while the provided ST LL takes the CMSIS instance first. The instance API is derived
from the provided header and the prompt's LL calls get the instance; greenfield HAL graphs are byte-identical."""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import pytest
from forge_factory.brownfield.cmsis import provided_api
from forge_factory.workflow import builder, prompts

ST_HDR = """#include "stm32n6xx.h"
/** @brief reset */
__STATIC_INLINE void LL_CRC_ResetCRCCalculationUnit(CRC_TypeDef *CRCx)
{
  SET_BIT(CRCx->CR, CRC_CR_RESET);
}
__STATIC_INLINE void LL_CRC_FeedData32(CRC_TypeDef *CRCx, uint32_t InData)
{
  WRITE_REG(CRCx->DR, InData);
}
__STATIC_INLINE uint32_t LL_CRC_ReadData32(const CRC_TypeDef *CRCx)
{
  return (uint32_t)(READ_REG(CRCx->DR));
}
"""
GREEN_HDR = ("#include <stdint.h>\nextern volatile uint32_t ll_crc_regs[256];\n"
             "static inline void LL_CRC_FeedData32(uint32_t InData)\n{\n  ll_crc_regs[0] = InData;\n}\n")


@pytest.fixture(autouse=True)
def _reset():
    yield
    prompts.LAYER["layer"] = "LL+HAL"
    prompts.PROVIDED_API["api"] = None


def _ws(tmp_path, header, layer="HAL"):
    ws = tmp_path / f"ws-{layer}-{len(header)}"
    (ws / ".forge-run").mkdir(parents=True)
    (ws / "software/ll").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": layer, "peripheral": "crc"}))
    (ws / "software/ll/stm32n6xx_ll_crc.h").write_text(header)
    return ws


def _prompts(dot):
    return dict(re.findall(r'\n  (\w+) \[[^\n]*?prompt="((?:[^"\\]|\\.)*)"', dot))


def test_instance_api_is_derived_from_the_provided_header(tmp_path):
    api = provided_api(_ws(tmp_path, ST_HDR))
    assert api["instance"] == "CRC" and api["functions"] == ["LL_CRC_FeedData32", "LL_CRC_ReadData32",
                                                             "LL_CRC_ResetCRCCalculationUnit"]
    assert api["signatures"]["LL_CRC_ReadData32"] == "uint32_t LL_CRC_ReadData32(const CRC_TypeDef *CRCx)"
    assert api["calls"]["LL_CRC_FeedData32"] == "LL_CRC_FeedData32(CRC, InData)"
    assert provided_api(_ws(tmp_path, GREEN_HDR)) is None  # greenfield register-array LL
    assert provided_api(_ws(tmp_path, ST_HDR, layer="LL")) is None  # only a HAL work order has a provided LL


def test_hal_author_prompt_calls_the_provided_ll_with_its_instance(tmp_path):
    api = provided_api(_ws(tmp_path, ST_HDR))
    dot, _ = builder.build("WO-T", chunk_lines=150, layer="HAL", trace=True, isolation=True, peripheral="crc",
                           uspec_gtest=True, provided_api=api)
    p = _prompts(dot)["swe3_hal_author"]
    assert "LL_CRC_FeedData32(CRC, p_data[i])" in p and "LL_CRC_ReadData32(CRC)" in p
    assert "LL_CRC_ResetCRCCalculationUnit(CRC)" in p and "LL_CRC_FeedData32(p_data" not in p
    assert "pass the instance macro CRC of the device header, e.g. LL_CRC_FeedData32(CRC, InData)" in p
    assert "signatures are in the provided header, e.g. void LL_CRC_FeedData32(CRC_TypeDef *CRCx, uint32_t InData)" in p


@pytest.mark.parametrize("pid,sha", [
    ("iwdg", "afcf7413ece417ffe1a112b7f115bf85596f6a205afdcef6c197b728937b84b7"),
    ("crc", "1537c161514f38443c31b89210646355bf9201abab3dcd86a4331827373ac35b")])
def test_greenfield_hal_graphs_are_byte_identical(pid, sha):
    """Frozen sha256 of the HAL graphs built by the parent 90ff4f4a/b4686726 (no provided instance API).

    The node scripts carry this host's checkout, state, data root and interpreter; they are replaced by
    placeholders first so the frozen value holds in every worktree and on every factory host."""
    dot, _ = builder.build("WO-G", chunk_lines=150, layer="HAL", trace=True, isolation=True, peripheral=pid,
                           uspec_gtest=True)
    host_free = dot.replace(builder._env(), "<ENV>").replace(sys.executable, "<PY>")
    assert hashlib.sha256(host_free.encode()).hexdigest() == sha


ST = Path(os.path.expandvars("$FORGE_DATA_ROOT/inputs/st/stm32n6xx-hal-driver-v1.4.0/src/stm32n6xx-hal-driver-1.4.0/Inc"))


@pytest.mark.skipif(not (ST / "stm32n6xx_ll_wwdg.h").is_file(), reason="ST downloads not available")
@pytest.mark.parametrize("pid,inst", [("crc", "CRC"), ("wwdg", "WWDG")])
def test_st_headers_give_their_instance(tmp_path, pid, inst):
    ws = tmp_path / pid
    (ws / ".forge-run").mkdir(parents=True)
    (ws / "software/ll").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL", "peripheral": pid}))
    (ws / f"software/ll/stm32n6xx_ll_{pid}.h").write_text((ST / f"stm32n6xx_ll_{pid}.h").read_text())
    api = provided_api(ws)
    assert api["instance"] == inst and all(c.startswith(f"{n}({inst}") for n, c in api["calls"].items())
