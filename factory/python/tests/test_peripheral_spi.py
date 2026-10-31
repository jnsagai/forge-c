"""Feature 015 (F015-T020): the SPI1 peripheral profile, its behavioural loopback Renode model and the ST LL code work
order (ST's CubeN6 SPI LL header delivered FROZEN). The RM0486 chapter 67 text is a local input: tests needing it skip
without it."""
import json
import re

import pytest
from forge_factory import peripheral
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT

EX = REPO_ROOT / "examples/0011c-st-cube-spi"
RM = REPO_ROOT / "examples/0011-spi-st/inputs/RM0486-rev4-ch67-spi.md"
MODEL = REPO_ROOT / "factory/sim/stm32n6/spi_model.py"


def test_the_spi_profile_validates_names_spi1_and_follows_st_coupled_fields():
    p = peripheral.load("spi")
    assert (p["register_prefix"], p["base_address"], p["mm_page"]) == ("SPI", "0x52003000", 180)
    assert not any(re.search(r"\bRCC(?:\b|_)", v) for v in p["prompt"].values())
    cover = p["prompt"]["swe1_cover"]
    assert "SPI_CFG1.MBR together with the prescaler" in cover and "SPI_CFG2.SSM together with" in cover
    spec = json.loads((EX / "workorder.json").read_text())
    assert spec["delivery"]["code_mode"] == "FROZEN" and spec["peripheral"] == "spi"
    assert len(spec["delivery"]["scope"]["functions"]) == 22


@pytest.mark.skipif(not RM.is_file(), reason="RM0486 chapter 67 is a local (ST copyrighted) input")
def test_rm0486_chapter_67_parses_into_the_spi_registers():
    from forge_factory.inspection.regmap import parse_section

    files, _index = WO.split_sections(RM.read_text(), RM.stem)
    regs = {r["name"]: r for r in (parse_section(t, "SPI") for t in files.values()) if r}
    assert {k: regs[k]["offset"] for k in ("SPI_CR1", "SPI_CR2", "SPI_CFG1", "SPI_CFG2", "SPI_SR", "SPI_IFCR",
                                           "SPI_TXDR", "SPI_RXDR")} == {
        "SPI_CR1": 0x0, "SPI_CR2": 0x4, "SPI_CFG1": 0x8, "SPI_CFG2": 0xC, "SPI_SR": 0x14, "SPI_IFCR": 0x18,
        "SPI_TXDR": 0x20, "SPI_RXDR": 0x30}
    assert regs["SPI_SR"]["reset"] == "0x00001002" and regs["SPI_CFG1"]["fields"]["MBR"] == (30, 28)


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


def test_the_spi_model_is_a_loopback_master_with_write_protection_eot_and_overrun():
    m = _model()
    assert m("read", 0x014) == 0x00001002 and m("read", 0x008) == 0x00070007
    m("write", 0x00C, 0x400000)  # MASTER while disabled: accepted
    m("write", 0x000, 0x1)       # SPE
    m("write", 0x00C, 0x0)       # CFG2 write-protected while enabled
    assert m("read", 0x00C) == 0x400000
    m("write", 0x004, 2)
    m("write", 0x020, 0xA5)
    m("write", 0x020, 0x5A)
    assert m("read", 0x014) & 0x1008 == 0  # frames wait: no EOT, TXC cleared
    m("write", 0x000, 0x201)               # CSTART
    sr = m("read", 0x014)
    assert sr & 0x1 and sr & 0x8 and sr & 0x10 and not m("read", 0x000) & 0x200
    assert (m("read", 0x030), m("read", 0x030)) == (0xA5, 0x5A) and not m("read", 0x014) & 0x1
    m("write", 0x018, 0x8)  # EOTC
    assert not m("read", 0x014) & 0x8
    m("write", 0x004, 17)
    for i in range(17):
        m("write", 0x020, i)
    m("write", 0x000, 0x201)
    assert m("read", 0x014) & 0x40  # the 17th frame overruns the 16-frame RxFIFO
    m("write", 0x018, 0x40)
    assert not m("read", 0x014) & 0x40
