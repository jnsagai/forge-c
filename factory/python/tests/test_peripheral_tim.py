"""Feature 015 (F015-T060): the TIM2 peripheral profile, its behavioural counter Renode model and the ST LL code work
order (ST's CubeN6 TIM LL header delivered FROZEN). The ST sources are local inputs: tests needing them skip without
them."""
import json
import os
import re
from pathlib import Path

import pytest
from forge_factory import peripheral
from forge_factory.common import REPO_ROOT

EX = REPO_ROOT / "examples/0013c-st-cube-tim"
MODEL = REPO_ROOT / "factory/sim/stm32n6/tim_model.py"
ST = Path(os.environ.get("FORGE_DATA_ROOT", "/nonexistent")) / "inputs/st"
LL_H = ST / "stm32n6xx-hal-driver-v1.4.0/src/stm32n6xx-hal-driver-1.4.0/Inc/stm32n6xx_ll_tim.h"
CMSIS = ST / "cmsis-device-n6-v1.4.0/src/cmsis-device-n6-1.4.0/Include"


def test_the_tim_profile_validates_names_tim2_and_states_the_rc_w0_clear():
    p = peripheral.load("tim")
    assert (p["register_prefix"], p["base_address"], p["mm_page"]) == ("TIM", "0x50000000", 181)
    assert not any(re.search(r"\bRCC(?:\b|_)", v) for v in p["prompt"].values())
    assert "TIM_CR1.DIR together with TIM_CR1.CMS" in p["prompt"]["swe1_cover"]
    assert 'op "write" of value 0' in p["prompt"]["swe1_effect_rule"]
    spec = json.loads((EX / "workorder.json").read_text())
    assert spec["delivery"]["code_mode"] == "FROZEN" and spec["peripheral"] == "tim"
    assert spec["delivery"]["files"] == [{"from": "Inc/stm32n6xx_ll_tim.h", "to": "software/ll/stm32n6xx_ll_tim.h"}]
    assert len(spec["delivery"]["scope"]["functions"]) == 22


@pytest.mark.skipif(not (LL_H.is_file() and CMSIS.is_dir()), reason="ST STM32CubeN6 v1.4.0 sources are local inputs")
def test_st_tim_code_is_extracted_with_the_coupled_counter_mode_and_the_rc_w0_clear():
    from forge_factory.brownfield import scope as S

    texts = [LL_H.read_text(errors="replace"), (CMSIS / "stm32n657xx.h").read_text(errors="replace"),
             (CMSIS / "stm32n6xx.h").read_text(errors="replace")]
    macros = S.constant_macros(texts)
    defs = {d.name: d for t, r in ((texts[2], "stm32n6xx.h"), (texts[0], "ll.h")) for d in S.index(t, r)}

    def fx(fn, *a):
        return [(e.register, e.op, e.mask, e.clear) for e in
                S.register_effects(defs[fn], macros, "cmsis", ["TIM2", *a], defs, prefix="TIM")]

    assert fx("LL_TIM_SetCounterMode", "LL_TIM_COUNTERMODE_DOWN") == [("TIM_CR1", "modify", 0x10, 0x70)]
    assert fx("LL_TIM_SetCounterMode", "LL_TIM_COUNTERMODE_CENTER_UP") == [("TIM_CR1", "modify", 0x40, 0x70)]
    assert fx("LL_TIM_ClearFlag_UPDATE") == [("TIM_SR", "write", 0xFFFFFFFE, None)]
    assert fx("LL_TIM_SetAutoReload", "999U") == [("TIM_ARR", "write", 999, None)]
    assert fx("LL_TIM_GenerateEvent_UPDATE") == [("TIM_EGR", "set", 0x1, None)]


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


def test_the_tim_model_counts_wraps_and_follows_urs_udis_opm_and_rc_w0():
    m = _model()
    assert (m("read", 0x2C), m("read", 0x00), m("read", 0x10)) == (0xFFFFFFFF, 0, 0)
    m("write", 0x28, 0)                  # PSC 0
    m("write", 0x2C, 3)                  # ARR 3
    m("write", 0x00, 0x4)                # URS
    m("write", 0x14, 0x1)                # UG: loads the shadows, no UIF (URS)
    assert m("read", 0x10) == 0
    m("write", 0x00, 0x5)                # URS + CEN, up-counting
    assert [m("read", 0x24) for _ in range(4)] == [1, 2, 3, 0]
    assert m("read", 0x10) & 0x1         # overflow: UIF
    m("write", 0x10, 0xFFFFFFFE)         # rc_w0 clear of UIF only
    assert not m("read", 0x10) & 0x1
    m("write", 0x00, 0x0)
    m("write", 0x24, 0)
    m("write", 0x00, 0x9)                # OPM + CEN
    while m("read", 0x00) & 0x1:
        m("read", 0x24)
    assert m("read", 0x10) & 0x1 and m("read", 0x24) == 0
    m("write", 0x10, 0)
    m("write", 0x00, 0x0)
    m("write", 0x00, 0x10)               # down-counting
    m("write", 0x14, 0x1)                # UG: counter to ARR, UIF (URS 0)
    assert m("read", 0x10) & 0x1
    m("write", 0x10, 0)
    m("write", 0x00, 0x11)
    assert [m("read", 0x24) for _ in range(4)] == [2, 1, 0, 3]
    m("write", 0x00, 0x13)               # UDIS: no update event at underflow
    m("write", 0x10, 0)
    for _ in range(8):
        m("read", 0x24)
    assert not m("read", 0x10) & 0x1


def test_an_rc_w0_flag_clear_is_conformant_only_when_the_requirement_writes_zero(tmp_path):
    """ST LL_TIM_ClearFlag_UPDATE writes ~TIM_SR_UIF: 0 to UIF, 1 (no change, rc_w0) elsewhere. On the real SPI package
    copy with one synthetic function: accepted when the requirement writes 0 to the field, a contradiction otherwise."""
    import shutil

    from forge_factory.brownfield import conformance as C

    src = Path(os.environ.get("FORGE_STATE_DIR", "/nonexistent")) / "workorders/WO-AFO-7a6810a8baf9b9c4-a1/workspace"
    if not (src / C.CALLS).is_file():
        pytest.skip("local SPI run state not present")
    for value, kinds in ((0, []), (1, ["CONTRADICTION"])):
        ws = tmp_path / f"ws{value}"
        shutil.copytree(src, ws, ignore=shutil.ignore_patterns("build"))
        h = ws / "software/ll/stm32n6xx_ll_spi.h"
        h.chmod(0o644)
        h.write_text(h.read_text() + "\n__STATIC_INLINE void LL_SPI_ClearI2SModRcw0(SPI_TypeDef *SPIx)\n{\n"
                     "  WRITE_REG(SPIx->I2SCFGR, ~(SPI_I2SCFGR_I2SMOD));\n}\n")
        eff, calls = json.loads((ws / C.EFFECTS).read_text()), json.loads((ws / C.CALLS).read_text())
        eff["effects"].append({"case": "RCW0", "swr": "SWR-099", "register": "SPI_I2SCFGR", "field": "I2SMOD",
                               "op": "write", "value": value})
        calls["calls"]["RCW0"] = {"function": "LL_SPI_ClearI2SModRcw0", "args": ["SPI1"]}
        (ws / C.EFFECTS).write_text(json.dumps(eff))
        (ws / C.CALLS).write_text(json.dumps(calls))
        r = C.check(ws, "SWE.3", write=False)
        assert sorted({f["kind"] for f in r["findings"]}) == kinds, (value, r["findings"][:3])
