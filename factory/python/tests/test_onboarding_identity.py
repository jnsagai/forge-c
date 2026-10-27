"""Feature 016 OB-T011: identity facts from the real ST inputs, and the CONFLICT / NOT_DERIVED cases."""
import pytest
from forge_factory.common import REPO_ROOT
from forge_factory.onboarding import identity as I
from onboarding_util import example_copy, need_inputs


def _facts(example):
    facts, _ = I.derive(I.context(example))
    return {f.name: f for f in facts}


@pytest.mark.parametrize("example,inst,base,page,prefix,style", [
    ("0012d-st-cube-usart-hal", "USART1", "0x52001000", 180, "USART", "HAL_STANDALONE"),
    ("0010d-st-cube-gpio-hal", "GPIOA", "0x56020000", 176, "GPIO", "HAL_STANDALONE"),
    ("0011c-st-cube-spi", "SPI1", "0x52003000", 180, "SPI", "LL"),
    ("0013d-st-cube-tim-hal", "TIM2", "0x50000000", 181, "TIM", "HAL_STANDALONE"),
    ("0014c-st-cube-crc", "CRC", "0x56024C00", 176, "CRC", "LL"),
    ("0008c-st-cube-rcc", "RCC", "0x56028000", 176, "RCC", "LL")])
def test_identity_facts_from_the_st_inputs(example, inst, base, page, prefix, style):
    need_inputs()
    f = _facts(REPO_ROOT / "examples" / example)
    assert (f["instance"].value, f["base_address"].value, f["mm_page"].value, f["register_prefix"].value,
            f["driver_style"].value) == (inst, base, page, prefix, style)
    assert f["register_index"].status == "DERIVED" and all(s.ref and (s.line or s.page or s.kind != "file")
                                                           for x in f.values() for s in x.sources)


def test_a_scope_naming_several_instances_asks_the_owner():
    need_inputs()
    f = _facts(REPO_ROOT / "examples/0013c-st-cube-tim")              # the scope names TIM2..TIM5
    assert f["instance"].status == "NOT_DERIVED" and "target.instance" in f["instance"].owner_question
    assert "base_address" not in f                                     # nothing is guessed from it


def test_target_instance_against_the_scope_is_a_conflict(tmp_path):
    need_inputs()
    ex = example_copy(tmp_path, "0012d-st-cube-usart-hal", lambda s: s["target"].update(instance="USART2"))
    f = _facts(ex)
    assert f["instance"].status == "CONFLICT" and {s.value for s in f["instance"].sources} == {"USART2", "USART1"}


def test_memory_map_disagreeing_with_the_device_header_is_a_conflict(tmp_path):
    need_inputs()
    ex = example_copy(tmp_path, "0012d-st-cube-usart-hal",
                      replace_inputs={"RM0486-rev4-memory-map-excerpt-usart.md":
                                      lambda t: t.replace("0x52001000 - 0x520013FF", "0x52011000 - 0x520113FF")})
    f = _facts(ex)
    assert f["base_address"].status == "CONFLICT" and f["base_address"].value is None
    assert {s.value for s in f["base_address"].sources} == {"0x52001000", "0x52011000"}


def test_missing_memory_map_row_is_not_derived(tmp_path):
    need_inputs()
    ex = example_copy(tmp_path, "0012d-st-cube-usart-hal",
                      replace_inputs={"RM0486-rev4-memory-map-excerpt-usart.md":
                                      lambda t: t.replace("USART1  ", "UNUSED1 ")})
    f = _facts(ex)
    assert f["base_address"].status == "NOT_DERIVED" and f["mm_page"].status == "NOT_DERIVED"


def test_hal_with_a_provided_ll_is_the_factory_hal_style(tmp_path):
    need_inputs()
    ex = example_copy(tmp_path, "0014d-st-cube-crc-hal", lambda s: s["delivery"].update(provided_ll=True))
    assert _facts(ex)["driver_style"].value == "HAL_ON_LL"


def test_gpio_retime_fields_are_derived_from_the_real_rm_lists():
    need_inputs()
    registers = _facts(REPO_ROOT / "examples/0010e-st-cube-gpio-hal-ob")["register_index"].value
    for register, first in (("GPIO_ADVCFGRL", 0), ("GPIO_ADVCFGRH", 8)):
        fields = registers[register]["fields"]
        assert len(fields) == 32
        assert fields[f"RET{first}"] == {"msb": 3, "lsb": 3, "access": ["rw"]}
        assert fields[f"DLYPATH{first + 7}"] == {"msb": 28, "lsb": 28, "access": ["rw"]}
