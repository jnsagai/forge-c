"""Feature 009 slice A (PG-T002/T003): multi-bit RM register fields (`Bits 15:0 KEY[15:0]:`) are parsed; RCC's
single-bit fields are unchanged and its previously dropped multi-bit fields (e.g. HSITRIM) now appear."""
import re

from forge_factory.assurance import hardware
from forge_factory.common import REPO_ROOT
from forge_factory.inspection import regmap

IWDG = (REPO_ROOT / "examples/0009-iwdg-st/inputs/RM0486-rev4-ch59-iwdg.md").read_text()


def _fields(text):
    return {m.group(3): (int(m.group(1)), int(m.group(2) or m.group(1))) for m in regmap._BIT.finditer(text)}


def test_iwdg_multi_bit_fields_are_parsed():
    f = _fields(IWDG)
    assert f["KEY"] == (15, 0) and f["PR"] == (3, 0) and f["RL"] == (11, 0) and f["WIN"] == (11, 0)
    assert {"PVU", "RVU", "WVU", "ONF", "EWIF"} <= set(f)


def test_single_bit_rcc_fields_and_multi_bit_rcc_fields():
    assert _fields("  Bit 3 HSION: HSI oscillator enable\n")["HSION"] == (3, 3)
    assert _fields("            Bits 29:28 SYSSWS[1:0]: system clock switch status\n")["SYSSWS"] == (29, 28)
    assert "Reserved" not in _fields("   Bits 31:16 Reserved, must be kept at reset value.\n")


def test_hardware_parser_uses_the_same_field_syntax():
    sec = ("#### 59.7.1 IWDG key register (RCC_KR)\nAddress offset: 0x000\nReset value: 0x0000 0000\n"
           "     Bits 15:0 KEY[15:0]: Key value\n")
    r = hardware.parse_section(sec)
    assert r["fields"]["KEY"]["msb"] == 15 and r["fields"]["KEY"]["lsb"] == 0
    assert re.search(r"KEY\[", sec)
