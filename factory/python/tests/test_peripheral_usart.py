"""Feature 015 (F015-T030): the USART1 peripheral profile, its behavioural loopback Renode model and the ST LL code work
order (ST's CubeN6 USART LL header delivered FROZEN). The RM0486 chapter 65 text and the ST sources are local inputs:
tests needing them skip without them."""
import json
import os
import re
from pathlib import Path

import pytest
from forge_factory import peripheral
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT

EX = REPO_ROOT / "examples/0012c-st-cube-usart"
RM = REPO_ROOT / "examples/0012-usart-st/inputs/RM0486-rev4-ch65-usart.md"
MODEL = REPO_ROOT / "factory/sim/stm32n6/usart_model.py"
ST = Path(os.environ.get("FORGE_DATA_ROOT", "/nonexistent")) / "inputs/st"
LL_H = ST / "stm32n6xx-hal-driver-v1.4.0/src/stm32n6xx-hal-driver-1.4.0/Inc/stm32n6xx_ll_usart.h"
CMSIS = ST / "cmsis-device-n6-v1.4.0/src/cmsis-device-n6-1.4.0/Include"


def test_the_usart_profile_validates_names_usart1_and_follows_st_coupled_fields():
    p = peripheral.load("usart")
    assert (p["register_prefix"], p["base_address"], p["mm_page"]) == ("USART", "0x52001000", 180)
    assert not any(re.search(r"\bRCC(?:\b|_)", v) for v in p["prompt"].values())
    cover = p["prompt"]["swe1_cover"]
    for coupled in ("USART_CR1.TE together with USART_CR1.RE", "USART_CR1.PCE together with USART_CR1.PS",
                    "USART_CR1.M0 together with USART_CR1.M1"):
        assert coupled in cover
    assert "write-1-to-clear" in p["prompt"]["swe1_effect_rule"]
    spec = json.loads((EX / "workorder.json").read_text())
    assert spec["delivery"]["code_mode"] == "FROZEN" and spec["peripheral"] == "usart"
    assert spec["delivery"]["files"] == [{"from": "Inc/stm32n6xx_ll_usart.h", "to": "software/ll/stm32n6xx_ll_usart.h"}]
    assert len(spec["delivery"]["scope"]["functions"]) == 21
    assert all((EX / i["path"]).resolve().parent.is_dir() for i in spec["inputs"])


@pytest.mark.skipif(not RM.is_file(), reason="RM0486 chapter 65 is a local (ST copyrighted) input")
def test_rm0486_chapter_65_parses_into_the_usart_registers_fifo_disabled():
    from forge_factory.inspection.regmap import parse_section

    files, _index = WO.split_sections(RM.read_text(), RM.stem)
    regs = {r["name"]: r for r in (parse_section(t, "USART") for t in files.values()) if r}
    assert {k: regs[k]["offset"] for k in ("USART_CR1", "USART_CR2", "USART_BRR", "USART_ISR", "USART_ICR",
                                           "USART_RDR", "USART_TDR", "USART_PRESC")} == {
        "USART_CR1": 0x0, "USART_CR2": 0x4, "USART_BRR": 0xC, "USART_ISR": 0x1C, "USART_ICR": 0x20,
        "USART_RDR": 0x24, "USART_TDR": 0x28, "USART_PRESC": 0x2C}
    f = regs["USART_CR1"]["fields"]
    assert (f["M1"], f["M0"], f["PCE"], f["PS"], f["TE"], f["RE"], f["UE"]) == (
        (28, 28), (12, 12), (10, 10), (9, 9), (3, 3), (2, 2), (0, 0))
    assert regs["USART_ISR"]["fields"]["TXE"] == (7, 7) and regs["USART_CR2"]["fields"]["STOP"] == (13, 12)


@pytest.mark.skipif(not (LL_H.is_file() and CMSIS.is_dir()), reason="ST STM32CubeN6 v1.4.0 sources are local inputs")
def test_st_usart_code_is_extracted_including_atomic_modify_and_the_split_word_length():
    """ST: LL_USART_SetTransferDirection uses ATOMIC_MODIFY_REG (LDREX/STREX), SetDataWidth MODIFY_REG(CR1, M0|M1, w),
    ClearFlag_ORE a whole USART_ICR write; SetBaudRate computes BRR (no constant)."""
    from forge_factory.brownfield import scope as S

    texts = [LL_H.read_text(errors="replace"), (CMSIS / "stm32n657xx.h").read_text(errors="replace"),
             (CMSIS / "stm32n6xx.h").read_text(errors="replace")]
    macros = S.constant_macros(texts)
    defs = {d.name: d for t, r in ((texts[2], "stm32n6xx.h"), (texts[0], "ll.h")) for d in S.index(t, r)}

    def fx(fn, *a):
        return [(e.register, e.op, e.mask, e.clear) for e in
                S.register_effects(defs[fn], macros, "cmsis", ["USART1", *a], defs, prefix="USART")]

    assert fx("LL_USART_SetTransferDirection", "LL_USART_DIRECTION_RX") == [("USART_CR1", "modify", 0x4, 0xC)]
    assert fx("LL_USART_SetDataWidth", "LL_USART_DATAWIDTH_7B") == [("USART_CR1", "modify", 0x10000000, 0x10001000)]
    assert fx("LL_USART_SetParity", "LL_USART_PARITY_EVEN") == [("USART_CR1", "modify", 0x400, 0x600)]
    assert fx("LL_USART_ClearFlag_ORE") == [("USART_ICR", "write", 0x8, None)]
    assert fx("LL_USART_TransmitData8", "0x41U") == [("USART_TDR", "write", 0x41, None)]
    brr = fx("LL_USART_SetBaudRate", "64000000U", "LL_USART_PRESCALER_DIV1", "LL_USART_OVERSAMPLING_16", "115200U")
    assert brr and all(r == "USART_BRR" and op == "write" and m is None for r, op, m, _c in brr)
    assert S.register_effects(defs["LL_USART_SetTransferDirection"], macros, "cmsis",
                               ["USART1", "LL_USART_DIRECTION_RX"], defs) == []  # RCC prefix: unchanged


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


def test_the_usart_model_loops_back_with_write_protection_acks_and_overrun():
    m = _model()
    assert m("read", 0x01C) == 0x000000C0
    m("write", 0x004, 0x2000)          # STOP = 2 while disabled: accepted
    m("write", 0x00C, 0x22C)           # BRR while disabled
    m("write", 0x000, 0x100D)          # M0, TE, RE, UE
    assert m("read", 0x01C) & 0x600000 == 0x600000  # TEACK, REACK
    m("write", 0x004, 0x0)             # CR2 write-protected while enabled
    m("write", 0x00C, 0x1)             # BRR write-protected while enabled
    m("write", 0x000, 0x000D)          # M0 is locked while enabled; TE/RE/UE writable
    assert (m("read", 0x004), m("read", 0x00C), m("read", 0x000)) == (0x2000, 0x22C, 0x100D)
    m("write", 0x020, 0x40)            # TCCF
    assert not m("read", 0x01C) & 0x40
    m("write", 0x028, 0x41)
    isr = m("read", 0x01C)
    assert isr & 0x40 and isr & 0x20 and not isr & 0x8
    assert m("read", 0x024) == 0x41 and not m("read", 0x01C) & 0x20
    m("write", 0x028, 0x5A)
    m("write", 0x028, 0xA5)            # arrives while RXNE is set: lost, ORE
    assert m("read", 0x01C) & 0x8 and m("read", 0x024) == 0x5A
    m("write", 0x020, 0x8)             # ORECF
    assert not m("read", 0x01C) & 0x8
    m("write", 0x000, 0x0)             # disabled: acks drop
    assert not m("read", 0x01C) & 0x600000
