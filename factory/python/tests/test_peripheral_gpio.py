"""Feature 015 (F015-T050): the GPIOA peripheral profile, its behavioural port Renode model and the ST LL code work order
(ST's CubeN6 GPIO LL header delivered FROZEN). The ST sources are local inputs: tests needing them skip without them."""
import json
import os
import re
from pathlib import Path

import pytest
from forge_factory import peripheral
from forge_factory.common import REPO_ROOT

EX = REPO_ROOT / "examples/0010c-st-cube-gpio"
MODEL = REPO_ROOT / "factory/sim/stm32n6/gpio_model.py"
ST = Path(os.environ.get("FORGE_DATA_ROOT", "/nonexistent")) / "inputs/st"
LL_H = ST / "stm32n6xx-hal-driver-v1.4.0/src/stm32n6xx-hal-driver-1.4.0/Inc/stm32n6xx_ll_gpio.h"
CMSIS = ST / "cmsis-device-n6-v1.4.0/src/cmsis-device-n6-1.4.0/Include"


def test_the_gpio_profile_validates_names_gpioa_and_numbers_the_pin_fields():
    p = peripheral.load("gpio")
    assert (p["register_prefix"], p["base_address"], p["mm_page"]) == ("GPIO", "0x56020000", 176)
    assert not any(re.search(r"\bRCC(?:\b|_)", v) for v in p["prompt"].values())
    assert "GPIO_MODER.MODE5" in p["prompt"]["swe1_cover"] and "field ODy, value 1" in p["prompt"]["swe1_effect_rule"]
    spec = json.loads((EX / "workorder.json").read_text())
    assert spec["delivery"]["code_mode"] == "FROZEN" and spec["peripheral"] == "gpio"
    assert spec["delivery"]["files"] == [{"from": "Inc/stm32n6xx_ll_gpio.h", "to": "software/ll/stm32n6xx_ll_gpio.h"}]
    assert len(spec["delivery"]["scope"]["functions"]) == 15


@pytest.mark.skipif(not (LL_H.is_file() and CMSIS.is_dir()), reason="ST STM32CubeN6 v1.4.0 sources are local inputs")
def test_st_gpio_code_is_extracted_with_the_pin_position_folded_and_the_afr_array_named():
    """ST: MODIFY_REG(GPIOx->MODER, GPIO_MODER_MODE0 << (POSITION_VAL(Pin) * 2U), Mode << ...), GPIOx->AFR[0]/[1]
    (RM0486 GPIOx_AFRL/AFRH), WRITE_REG(GPIOx->BSRR, PinMask); TogglePin computes its BSRR value from GPIO_ODR."""
    from forge_factory.brownfield import scope as S

    texts = [LL_H.read_text(errors="replace"), (CMSIS / "stm32n657xx.h").read_text(errors="replace"),
             (CMSIS / "stm32n6xx.h").read_text(errors="replace")]
    macros = S.constant_macros(texts)
    defs = {d.name: d for t, r in ((texts[2], "stm32n6xx.h"), (texts[0], "ll.h")) for d in S.index(t, r)}

    def fx(fn, *a, prefix="GPIO"):
        return [(e.register, e.op, e.mask, e.clear) for e in
                S.register_effects(defs[fn], macros, "cmsis", ["GPIOA", *a], defs, prefix=prefix)]

    assert fx("LL_GPIO_SetPinMode", "LL_GPIO_PIN_5", "LL_GPIO_MODE_OUTPUT") == [("GPIO_MODER", "modify", 0x400, 0xC00)]
    assert fx("LL_GPIO_SetAFPin_0_7", "LL_GPIO_PIN_5", "LL_GPIO_AF_7") == [("GPIO_AFRL", "modify", 0x700000, 0xF00000)]
    assert fx("LL_GPIO_SetAFPin_8_15", "LL_GPIO_PIN_9", "LL_GPIO_AF_7") == [("GPIO_AFRH", "modify", 0x70, 0xF0)]
    assert fx("LL_GPIO_SetOutputPin", "LL_GPIO_PIN_5") == [("GPIO_BSRR", "write", 0x20, None)]
    assert fx("LL_GPIO_TogglePin", "LL_GPIO_PIN_5") == [("GPIO_ODR", "read", None, None),
                                                         ("GPIO_BSRR", "write", None, None)]
    assert S.evaluate("POSITION_VAL(0x20U) * 2U", macros) is None  # folded only on request (outside RCC)
    assert S.evaluate("POSITION_VAL(0x20U) * 2U", macros, intrinsics=True) == 10
    assert S.evaluate("__CLZ(__RBIT(0x0U))", macros, intrinsics=True) == 32


def _model():
    src, ns = MODEL.read_text(), {}

    class Req:
        pass

    def call(kind, off=0, val=0):
        r = Req()
        r.IsInit, r.IsRead, r.IsWrite = kind == "init", kind == "read", kind == "write"
        r.Offset, r.Value = off, val
        ns["request"] = r
        exec(compile(src, str(MODEL), "exec"), ns)  # noqa: S102 - the repository's own simulator model
        return r.Value
    call("init")
    return call


def test_the_gpio_model_has_the_port_a_reset_values_and_set_reset_toggle_semantics():
    m = _model()
    assert (m("read", 0x00), m("read", 0x08), m("read", 0x0C)) == (0xABFFEFFF, 0x0C000000, 0x64000000)
    m("write", 0x00, (0xABFFEFFF & ~0xC00) | 0x400)  # PA5 output
    m("write", 0x18, 0x20)                           # BS5
    assert m("read", 0x14) == 0x20 and m("read", 0x10) & 0x20
    m("write", 0x18, 0x00200020)                     # BR5 and BS5: BS wins
    assert m("read", 0x14) == 0x20
    m("write", 0x28, 0x20)                           # BRR: reset PA5
    assert m("read", 0x14) == 0 and not m("read", 0x10) & 0x20
    m("write", 0x00, m("read", 0x00) & ~0xC00)       # PA5 input
    m("write", 0x0C, (m("read", 0x0C) & ~0xC00) | 0x400)   # pull-up
    assert m("read", 0x10) & 0x20
    m("write", 0x0C, (m("read", 0x0C) & ~0xC00) | 0x800)   # pull-down
    assert not m("read", 0x10) & 0x20
    assert m("read", 0x18) == 0 and m("read", 0x28) == 0    # write-only
