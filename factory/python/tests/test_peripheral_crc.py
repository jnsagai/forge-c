"""Feature 015 (F015-T010): the CRC peripheral profile, its behavioural Renode model and the ST LL code work order.

ST's CubeN6 CRC LL header is delivered FROZEN (the factory writes the SWE.1-SWE.6 work products, no code). The RM0486
chapter 26 text is ST copyrighted and stays local (git-ignored, hash manifest tracked): tests that need it skip
without it."""
import json

import pytest
from forge_factory import peripheral
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT

EX = REPO_ROOT / "examples/0014c-st-cube-crc"
RM = REPO_ROOT / "examples/0014-crc-st/inputs/RM0486-rev4-ch26-crc.md"
MODEL = REPO_ROOT / "factory/sim/stm32n6/crc_model.py"
needs_rm = pytest.mark.skipif(not RM.is_file(), reason="RM0486 chapter 26 is a local (ST copyrighted) input")


def test_the_crc_profile_validates_and_names_the_rm0486_instance():
    p = peripheral.load("crc")
    assert (p["register_prefix"], p["base_address"], p["mm_page"]) == ("CRC", "0x56024C00", 176)
    assert p["ll"]["function_prefix"] == "LL_CRC_" and p["sim"]["model"] == "crc_model.py"
    import re

    # word-boundary check: ST's name LL_CRC_ResetCRCCalculationUnit contains the letters RCC
    assert not any(re.search(r"\bRCC(?:\b|_)", v) for v in p["prompt"].values())


def test_the_input_manifest_records_the_converted_pages_and_hashes():
    docs = json.loads((REPO_ROOT / "examples/0014-crc-st/inputs/inputs-manifest.json").read_text())["documents"]
    assert {(d["markdown"], tuple(d["pages"])) for d in docs} == {
        ("RM0486-rev4-ch26-crc.md", (1169, 1175)), ("RM0486-rev4-memory-map-excerpt-crc.md", (176, 176))}
    if RM.is_file():
        from forge_factory.common import sha256_file

        assert sha256_file(RM) == next(d["markdown_sha256"] for d in docs if d["markdown"] == RM.name)


@needs_rm
def test_rm0486_chapter_26_parses_into_the_five_crc_registers():
    from forge_factory.inspection.regmap import parse_section

    files, _index = WO.split_sections(RM.read_text(), RM.stem)
    regs = {r["name"]: r for r in (parse_section(t, "CRC") for t in files.values()) if r}
    assert {k: v["offset"] for k, v in regs.items()} == {"CRC_DR": 0x0, "CRC_IDR": 0x4, "CRC_CR": 0x8, "CRC_INIT": 0x10,
                                                          "CRC_POL": 0x14}
    assert regs["CRC_CR"]["fields"]["POLYSIZE"] == (4, 3) and regs["CRC_DR"]["reset"] == "0xFFFFFFFF"


def _model():
    """Run the Renode Python peripheral script outside Renode with a minimal request object."""
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


def test_the_crc_model_computes_the_stm32_crc32_and_honours_reset_init_and_reversal():
    m = _model()
    m("write", 0x000, 0x12345678)
    assert m("read", 0x000) == 0xDF8A8A2B  # CRC-32 (0x04C11DB7, init 0xFFFFFFFF, no reversal) of one word
    m("write", 0x008, 0x1)  # RESET loads CRC_INIT and reads 0
    assert m("read", 0x000) == 0xFFFFFFFF and m("read", 0x008) == 0
    m("write", 0x004, 0xCAFE)
    m("write", 0x008, 0x1)
    assert m("read", 0x004) == 0xCAFE  # CRC_IDR is not affected by RESET
    m("write", 0x010, 0x0)  # a CRC_INIT write loads the CRC
    assert m("read", 0x000) == 0
    m("write", 0x008, 0x080)  # REV_OUT = 01: bit-reversed output
    m("write", 0x010, 0x1)
    assert m("read", 0x000) == 0x80000000


@needs_rm
def test_the_st_crc_work_order_delivers_the_frozen_st_ll_header(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    spec = json.loads((EX / "workorder.json").read_text())
    src = spec["delivery"]["source"].replace("$FORGE_DATA_ROOT", __import__("os").environ.get("FORGE_DATA_ROOT", ""))
    if not (__import__("pathlib").Path(src) / "Inc/stm32n6xx_ll_crc.h").is_file():
        pytest.skip("ST CubeN6 v1.4.0 is a local input")
    assert spec["delivery"]["code_mode"] == "FROZEN" and spec["peripheral"] == "crc"
    _ws, man = WO.prepare(EX, "WO-CRC-ST-1")
    assert man["peripheral"] == "crc" and len(man["peripheral_profile_sha256"]) == 64


def test_the_crc_model_reproduces_the_rm0486_reversal_examples():
    """RM0486 26.3.3: output 0x11223344 -> 0x22CC4488 (bit level), 0x33441122 / 0x44332211 (RTYPE_OUT, half-word /
    byte reversal by word); input 0x1A2B3C4D -> 0x3C4D1A2B / 0x4D3C2B1A with RTYPE_IN. ST's reversal modes set the
    reversal field and its type bit together (run WO-BENCH-CRC-ST-r1 blocked on a scope that kept them apart)."""
    m = _model()
    m("write", 0x010, 0x11223344)
    for cr, want in ((0x080, 0x22CC4488), (0x400 | 0x080, 0x33441122), (0x400 | 0x100, 0x44332211)):
        m("write", 0x008, cr)
        assert m("read", 0x000) == want, hex(cr)
    ns = {}
    exec(compile(MODEL.read_text().split("if request.IsInit:")[0], str(MODEL), "exec"), ns)  # noqa: S102
    assert ns["_rev_in"](0x1A2B3C4D, 1, 1) == 0x3C4D1A2B and ns["_rev_in"](0x1A2B3C4D, 2, 1) == 0x4D3C2B1A
    assert ns["_rev_in"](0x1A2B3C4D, 1, 0) == 0x58D43CB2 and ns["_rev_in"](0x1A2B3C4D, 3, 0) == 0xB23CD458
