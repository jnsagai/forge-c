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


def test_iwdg_prompts_name_the_iwdg_key_sections():
    """i001: SWE.1/SWE.2 were handed the RCC section numbers (unavailable in an IWDG work order), so the SWE.2 author
    left every register offset 'unresolved'."""
    g, _ = build("WO-T", layer="LL", trace=True, chunk_lines=150, peripheral="iwdg",
                 sections={"59.7.1": "inputs/sections/RM0486/59.7.1_IWDG_key_register_IWDG_KR.md",
                           "59.7.2": "inputs/sections/RM0486/59.7.2_IWDG_prescaler_register_IWDG_PR.md",
                           "59.7.3": "inputs/sections/RM0486/59.7.3_IWDG_reload_register_IWDG_RLR.md",
                           "59.7.4": "inputs/sections/RM0486/59.7.4_IWDG_status_register_IWDG_SR.md"})
    prompts = dict(re.findall(r'\n  (\w+) \[[^\n]*?prompt="((?:[^"\\]|\\.)*)"', g))
    for node in ("swe1_author", "swe2_author"):
        assert "59.7.1_IWDG_key_register_IWDG_KR.md" in prompts[node] and "unavailable" not in prompts[node], node


# owner request 2026-10-20 ("a watchdog HAL driver"): the HAL layer prompts are IWDG too
HAL_RCC_ONLY = re.compile(r"HSE|HSI(?!_contract)[A-Z_]|RDY|oscillat|selector|IWDG_CR\b|ready flag|AHB1", re.I)


def test_iwdg_hal_prompts_have_no_rcc_content():
    g, _ = build("WO-T", layer="HAL", trace=True, isolation=True, chunk_lines=150, peripheral="iwdg")
    prompts = dict(re.findall(r'\n  (\w+) \[[^\n]*?prompt="((?:[^"\\]|\\.)*)"', g))
    assert len(prompts) >= 15
    bad = {n: sorted(set(RCC_DOMAIN.findall(p) + HSI_RCC.findall(p) + HAL_RCC_ONLY.findall(p))) for n, p in prompts.items()}
    assert {n: b for n, b in bad.items() if b} == {}
    assert "HAL_IWDG_Init(const hal_iwdg_config_t *p_config, uint32_t timeout)" in prompts["swe2_author"]
    assert "// HAL_IWDG API prototypes (SWE.3 HAL author)" in prompts["swe3_hal_author"]
    assert "LL_IWDG_IsActiveFlag_PVU" in prompts["swe3_hal_author"] and "status = HAL_TIMEOUT;" in prompts["swe3_hal_author"]
    assert '\\"busy\\":\\"IWDG_SR.PVU\\"' in prompts["swe1_author"]  # quotes are escaped in the graph
    assert "ut_iwdg_init" in prompts["swe4_test_author"]
    assert "never_ready the update flags never clear" in prompts["swe5_target_author"]
