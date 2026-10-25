"""Feature 015 (F015-T040): RM0486 register sections of multi-instance peripherals (GPIO chapter 15, TIM2-5 chapter 54)
parse into CMSIS-named registers: placeholder names (GPIOx_MODER, TIMx_CR1) with or without the instance qualifier
"(x = ...)", names wrapped after the heading, per-port reset values, 16-bit reset values and one-line-per-port pin
fields (MODEy). RCC/IWDG/CRC/SPI/USART results are unchanged. The RM text is a local input: those tests skip without it."""
import pytest
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT
from forge_factory.inspection.regmap import parse_section

GPIO_RM = REPO_ROOT / "examples/0010-gpio-st/inputs/RM0486-rev4-ch15-gpio.md"
TIM_RM = REPO_ROOT / "examples/0013-tim-st/inputs/RM0486-rev4-ch54-tim2-5.md"
RCC_RM = REPO_ROOT / "examples/0002-arm_55_rcc_st/inputs/RM0486-rev4-ch14-rcc.md"

MODER = """#### 15.4.1 GPIO port x mode register (GPIOx_MODER) (x = A to H, N to Q)

```text
                  Address offset:0x00
                  Reset value: Port A: 0xABFF EFFF
                  Reset value: Port B: 0xFFFF FAFF
                  Reset value: 0xFFFF FFFF (for the other ports)
                Bits 31:0 MODEy[1:0]: Port x configuration I/O pin y (y = 15 to 0)
```
"""
WRAPPED = """#### 54.5.8 TIMx capture/compare mode register 1 [alternate]

```text
                  (TIMx_CCMR1)(x = 2 to 5)
                  Address offset: 0x018
                  Reset value: 0x0000
                Bit 0 CC1S: Capture/Compare 1 selection
```
"""


def test_placeholder_names_per_port_reset_and_pin_fields():
    r = parse_section(MODER, "GPIO")
    assert (r["name"], r["offset"], r["reset"]) == ("GPIO_MODER", 0x0, "0xABFFEFFF")
    assert len(r["fields"]) == 16 and r["fields"]["MODE0"] == (1, 0) and r["fields"]["MODE15"] == (31, 30)
    w = parse_section(WRAPPED, "TIM")
    assert (w["name"], w["offset"], w["reset"], w["fields"]) == ("TIM_CCMR1", 0x18, "0x0000", {"CC1S": (0, 0)})


def test_rcc_keeps_its_exact_heading_rule():
    rcc = WRAPPED.replace("TIMx_CCMR1)(x = 2 to 5)", "RCC_PRIVCFGR0)").replace("TIMx", "RCC")
    assert parse_section(rcc, "RCC") is None  # a wrapped RCC name stays unparsed, as the RCC pilots saw it
    assert parse_section(MODER.replace("GPIOx_MODER) (x = A to H, N to Q)", "RCC_CR)"), "RCC")["reset"] == "0xFFFFFFFF"


def _regs(rm, pfx):
    files, _ = WO.split_sections(rm.read_text(), rm.stem)
    return {r["name"]: r for r in (parse_section(t, pfx) for t in files.values()) if r}


@pytest.mark.skipif(not GPIO_RM.is_file(), reason="RM0486 chapter 15 is a local (ST copyrighted) input")
def test_rm0486_chapter_15_parses_into_the_gpio_registers():
    g = _regs(GPIO_RM, "GPIO")
    assert {k: g[k]["offset"] for k in ("GPIO_MODER", "GPIO_OTYPER", "GPIO_OSPEEDR", "GPIO_PUPDR", "GPIO_IDR",
                                        "GPIO_ODR", "GPIO_BSRR", "GPIO_LCKR", "GPIO_AFRL", "GPIO_AFRH", "GPIO_BRR")} == {
        "GPIO_MODER": 0x0, "GPIO_OTYPER": 0x4, "GPIO_OSPEEDR": 0x8, "GPIO_PUPDR": 0xC, "GPIO_IDR": 0x10,
        "GPIO_ODR": 0x14, "GPIO_BSRR": 0x18, "GPIO_LCKR": 0x1C, "GPIO_AFRL": 0x20, "GPIO_AFRH": 0x24, "GPIO_BRR": 0x28}
    assert g["GPIO_MODER"]["reset"] == "0xABFFEFFF" and g["GPIO_MODER"]["fields"]["MODE5"] == (11, 10)
    assert g["GPIO_BSRR"]["fields"]["BS3"] == (3, 3) and g["GPIO_BSRR"]["fields"]["BR3"] == (19, 19)
    assert g["GPIO_AFRL"]["fields"]["AFSEL7"] == (31, 28) and "GPIO_RCFGLOCKR" in g  # name wrapped after the heading


@pytest.mark.skipif(not TIM_RM.is_file(), reason="RM0486 chapter 54 is a local (ST copyrighted) input")
def test_rm0486_chapter_54_parses_into_the_tim2_5_registers():
    t = _regs(TIM_RM, "TIM")
    assert {k: t[k]["offset"] for k in ("TIM_CR1", "TIM_DIER", "TIM_SR", "TIM_EGR", "TIM_CNT", "TIM_PSC",
                                        "TIM_ARR")} == {
        "TIM_CR1": 0x0, "TIM_DIER": 0xC, "TIM_SR": 0x10, "TIM_EGR": 0x14, "TIM_CNT": 0x24, "TIM_PSC": 0x28,
        "TIM_ARR": 0x2C}
    assert t["TIM_CR1"]["reset"] == "0x0000" and t["TIM_ARR"]["reset"] == "0xFFFFFFFF"
    assert (t["TIM_CR1"]["fields"]["CEN"], t["TIM_CR1"]["fields"]["DIR"], t["TIM_SR"]["fields"]["UIF"]) == (
        (0, 0), (4, 4), (0, 0))


@pytest.mark.skipif(not RCC_RM.is_file(), reason="RM0486 chapter 14 is a local (ST copyrighted) input")
def test_rm0486_rcc_chapter_parses_as_before():
    r = _regs(RCC_RM, "RCC")
    assert len(r) >= 200 and "RCC_PRIVCFGR0" not in r  # its heading wraps: unparsed before feature 015, still
