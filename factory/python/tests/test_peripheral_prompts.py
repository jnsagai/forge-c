"""Feature 009 SC-001 / FR-006: an IWDG work order's prompts carry no RCC domain content (RCC prompts unchanged: see
test_peripheral_rcc_equivalence). 'HSI' as hardware-software interface (SWE1-01, the HSI contract) is not RCC content."""
import re

import pytest
from forge_factory.workflow.builder import build

RCC_DOMAIN = re.compile(r"LL_RCC|HAL_RCC|ll_rcc|stm32n6xx_\w*rcc|\bRCC|\bHSE\b|GPDMA1|ADC12|AHB1|oscillator|\bPLL|"
                        r"0x56028000|p\.176|test_rcc|rcc_model")
HSI_RCC = re.compile(r"\bHSI(?!\s+(?:and allocated|contract|=))")


@pytest.mark.parametrize("kw", [dict(), dict(brownfield="FROZEN")])
def test_iwdg_prompts_have_no_rcc_content(kw):
    g, nodes = build("WO-T", layer="LL", trace=True, chunk_lines=150, peripheral="iwdg", **kw)
    prompts = dict(re.findall(r'\n  (\w+) \[[^\n]*?prompt="((?:[^"\\]|\\.)*)"', g))
    assert len(prompts) >= 15
    bad = {n: sorted(set(RCC_DOMAIN.findall(p) + HSI_RCC.findall(p))) for n, p in prompts.items()}
    assert {n: b for n, b in bad.items() if b} == {}
    if not kw:  # the brownfield graph has no LL author (the code is delivered)
        assert "// LL_IWDG access functions (SWE.3 LL author)" in prompts["swe3_ll_author"]
    assert "IWDG_KR.KEY" in prompts["swe1_author"] and "0x56004800" in prompts["swe2_author"]
