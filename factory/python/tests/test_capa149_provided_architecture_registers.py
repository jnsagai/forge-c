"""A provided CMSIS LL owns register access; the HAL architecture must describe that actual design."""
import re

import pytest
from forge_factory.workflow import builder


def prompts(peripheral, provided=True):
    inst = peripheral.upper()
    name = f"LL_{inst}_ReadData32" if peripheral == "crc" else "LL_WWDG_IsEnabled"
    api = {"instance": inst, "functions": [name], "calls": {name: f"{name}({inst})"},
           "signatures": {name: f"uint32_t {name}(const {inst}_TypeDef *instance)"}}
    dot, _ = builder.build("WO-C149", chunk_lines=150, layer="HAL", trace=True, isolation=True,
                           peripheral=peripheral, uspec_gtest=True, **({"provided_api": api} if provided else {}))
    return dict(re.findall(r'\n  (\w+) \[[^\n]*?prompt="((?:[^"\\]|\\.)*)"', dot))


@pytest.mark.parametrize("peripheral", ["crc", "wwdg"])
def test_provided_hal_architecture_and_host_test_describe_the_actual_mapping(peripheral):
    p = prompts(peripheral)
    assert "extern volatile uint32_t register-block array placed" not in p["swe2_author"]
    for node in ("swe2_author", "swe5_author"):
        assert "forge_host_device.h" in p[node] and f"forge_host_{peripheral}" in p[node]
        assert "host tests define the array" not in p[node]


def test_greenfield_hal_keeps_its_register_array_architecture():
    p = prompts("crc", provided=False)
    assert "Register access (extern volatile uint32_t register-block array placed at the CRC base by the linker" in p["swe2_author"]
    assert "forge_host_device.h" not in p["swe5_author"]
