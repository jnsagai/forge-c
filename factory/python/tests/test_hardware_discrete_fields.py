"""RM repeated one-bit fields whose bit positions are comma-separated across lines."""
import pytest
from forge_factory.assurance.hardware import parse_section


def section(high=False, continuation="15, 11, 7, 3"):
    suffix, upper, lower = ("H", 15, 8) if high else ("L", 7, 0)
    offset = "0x4C" if high else "0x48"
    diagram = "\n".join(" ".join(f"{value:>4}" for value in row)
                        for row in (range(31, 15, -1), ["rw"] * 16, range(15, -1, -1), ["rw"] * 16))
    return f"""#### GPIO advanced configuration (GPIOx_ADVCFGR{suffix})
Address offset: {offset}
Reset value: 0x0000 0000
{diagram}
Bits 31, 27, 23, 19, RETy: test selection (y = {upper} to {lower})
        {continuation}  0: disabled
Bits 30, 26, 22, 18, INVCLKy: test inversion (y = {upper} to {lower})
        14, 10, 6, 2  0: normal
Bits 29, 25, 21, 17, DEy: test edge selection (y = {upper} to {lower})
        13, 9, 5, 1  0: single
Bits 28, 24, 20, 16, DLYPATHy: test path selection (y = {upper} to {lower})
        12, 8, 4, 0  0: output
"""


@pytest.mark.parametrize("high,start", [(False, 0), (True, 8)])
def test_comma_separated_pin_fields_use_explicit_bit_positions(high, start):
    register = parse_section(section(high), "GPIO")
    assert len(register["fields"]) == 32
    for offset in range(8):
        for field, bit in (("RET", 3), ("INVCLK", 2), ("DE", 1), ("DLYPATH", 0)):
            value = register["fields"][f"{field}{start + offset}"]
            assert value == {"msb": offset * 4 + bit, "lsb": offset * 4 + bit, "access": ["rw"]}
    assert register["reserved_mask"] == 0


@pytest.mark.parametrize("continuation", ["15, 11, 7", "15, 11, 7, 7", "35, 11, 7, 3"])
def test_ambiguous_duplicate_or_out_of_range_positions_are_not_guessed(continuation):
    register = parse_section(section(continuation=continuation), "GPIO")
    assert not any(name.startswith("RET") for name in register["fields"])
