"""CAPA-230 (owner SWE.2 review 2026-11-11, no-GPU dry run of the SWE.2 graphs of SPI LL L41P and SPI HAL L46):
- an LL SWE.2 author on ST's delivered CMSIS LL was told the generic factory design ("extern volatile uint32_t
  register-block array ... no integer-to-pointer casts") and "LL functions take no arguments: args []", contradicting
  "describe the architecture the delivered code ACTUALLY has" and the delivered instance-first signatures;
- a HAL SWE.2 author's trace example drew 'SWC_HAL --> SPI : IF-01 register access' (a HAL arrow straight to the
  registers, the L35 IF-02 flaw) next to a second IF-01;
- a HAL on a provided LL was asked for a register table of registers "used" although it reaches them only via the LL."""
import pytest
from forge_factory.peripheral import load
from forge_factory.workflow import prompts as P


@pytest.fixture
def state():
    keep = {k: dict(v) for k, v in (("LAYER", P.LAYER), ("BROWNFIELD", P.BROWNFIELD), ("TRACE", P.TRACE),
                                    ("PERIPHERAL", P.PERIPHERAL), ("STANDALONE", P.STANDALONE))}
    yield
    for k, v in keep.items():
        getattr(P, k).clear()
        getattr(P, k).update(v)


def _set(layer, peripheral, brownfield=None, style=None):
    P.LAYER["layer"] = layer
    P.BROWNFIELD["mode"] = brownfield
    P.BROWNFIELD["style"] = style
    P.TRACE["on"] = True
    P.STANDALONE["on"] = False
    P.PERIPHERAL["profile"] = load(peripheral)


@pytest.mark.parametrize("peripheral,inst,typedef", [("spi", "SPI1", "SPI_TypeDef"), ("tim", "TIM2", "TIM_TypeDef"),
                                                     ("wwdg", "WWDG", "WWDG_TypeDef")])
def test_a_delivered_cmsis_ll_is_described_as_delivered(state, peripheral, inst, typedef):
    _set("LL", peripheral, "FROZEN", "cmsis")
    text = P.author_prompt("SWE.2")
    assert "register-block array placed at" not in text and "LL functions take no arguments" not in text
    assert f"{typedef} pointer {inst}" in text and f'["{inst}"]' in text


def test_a_greenfield_ll_keeps_the_factory_register_array(state):
    _set("LL", "spi")
    text = P.author_prompt("SWE.2")
    assert "register-block array placed at" in text and "LL functions take no arguments: args []" in text


def test_the_hal_trace_example_reaches_the_registers_only_through_the_ll(state):
    _set("HAL", "spi")
    text = P.author_prompt("SWE.2")
    assert "SWC_HAL --> SPI" not in text and "SWC_HAL --> SWC_LL : IF-01" in text
    assert "SWC_LL --> SPI : IF-02 register access" in text
    assert "one row per register/bit the HAL reaches through the LL functions it calls" in text


def test_the_ll_trace_example_is_unchanged(state):
    _set("LL", "spi", "FROZEN", "cmsis")
    assert "'SWC_LL --> SPI : IF-01 register access'" in P.author_prompt("SWE.2")
