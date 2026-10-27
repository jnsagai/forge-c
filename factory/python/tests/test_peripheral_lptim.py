"""Feature 014 operation-24 campaign (owner 2026-10-27 "RNG, LPTIM, WWDG"): the LPTIM peripheral profile (instance
LPTIM1), its behavioural Renode model and the ST LL code work order (ST's CubeN6 LPTIM LL header delivered FROZEN). The
ST sources are local inputs: tests needing them skip without them."""
import json
import os
import re
from pathlib import Path

import pytest
from forge_factory import peripheral
from forge_factory.common import REPO_ROOT

EX = REPO_ROOT / "examples/0018c-st-cube-lptim"
MODEL = REPO_ROOT / "factory/sim/stm32n6/lptim_model.py"
ST = Path(os.environ.get("FORGE_DATA_ROOT", "/nonexistent")) / "inputs/st"
LL_H = ST / "stm32n6xx-hal-driver-v1.4.0/src/stm32n6xx-hal-driver-1.4.0/Inc/stm32n6xx_ll_lptim.h"
CMSIS = ST / "cmsis-device-n6-v1.4.0/src/cmsis-device-n6-1.4.0/Include"


def test_the_lptim_profile_validates_names_lptim1_and_states_the_write_constraints():
    p = peripheral.load("lptim")
    assert (p["register_prefix"], p["base_address"], p["mm_page"], p["rm"]["chapter"]) == ("LPTIM", "0x50002400", 181, 58)
    assert not any(re.search(r"\bRCC(?:\b|_)", v) and "(RCC)" not in v for v in p["prompt"].values())
    cover = p["prompt"]["swe1_cover"]
    assert "LPTIM_CFGR must only be modified while the LPTIM is disabled" in cover
    assert "LPTIM_ARR and LPTIM_DIER must only be modified" in cover and "write 1 to LPTIM_ICR.ARRMCF" in cover
    assert "forge_host_lptim." in p["prompt"]["ut_example"] and "LPTIM1" not in p["prompt"]["ut_example"]
    spec = json.loads((EX / "workorder.json").read_text())
    assert spec["delivery"]["code_mode"] == "FROZEN" and spec["peripheral"] == "lptim"
    assert spec["delivery"]["files"] == [{"from": "Inc/stm32n6xx_ll_lptim.h", "to": "software/ll/stm32n6xx_ll_lptim.h"}]
    assert len(spec["delivery"]["scope"]["functions"]) == 21
    assert all((EX / i["path"]).resolve().parent.is_dir() for i in spec["inputs"])
    m = json.loads((REPO_ROOT / "examples/0018-lptim-st/inputs/inputs-manifest.json").read_text())
    assert [(d["markdown"], d["pages"]) for d in m["documents"]] == [
        ("RM0486-rev4-ch58-lptim.md", [2928, 2978]), ("RM0486-rev4-memory-map-excerpt-lptim.md", [181, 181])]


@pytest.mark.skipif(not (LL_H.is_file() and CMSIS.is_dir()), reason="ST STM32CubeN6 v1.4.0 sources are local inputs")
def test_st_lptim_code_is_extracted_as_bit_and_field_writes():
    """ST: SET_BIT/CLEAR_BIT(LPTIMx->CR, ENABLE), MODIFY_REG(CR, CNTSTRT | SNGSTRT, mode), MODIFY_REG(ARR, ARR, value),
    MODIFY_REG(CFGR, PRESC, prescaler) and SET_BIT(LPTIMx->ICR, <flag>CF) (ICR is write-only, RM0486 58.7.5)."""
    from forge_factory.brownfield import scope as S

    texts = [LL_H.read_text(errors="replace"), (CMSIS / "stm32n657xx.h").read_text(errors="replace"),
             (CMSIS / "stm32n6xx.h").read_text(errors="replace")]
    macros = S.constant_macros(texts)
    defs = {d.name: d for t, r in ((texts[2], "stm32n6xx.h"), (texts[0], "ll.h")) for d in S.index(t, r)}

    def fx(fn, *a):
        return [(e.register, e.op, e.mask, e.clear) for e in
                S.register_effects(defs[fn], macros, "cmsis", ["LPTIM1", *a], defs, prefix="LPTIM")]

    assert fx("LL_LPTIM_Enable") == [("LPTIM_CR", "set", 0x1, None)]
    assert fx("LL_LPTIM_Disable") == [("LPTIM_CR", "clear", 0x1, None)]
    assert fx("LL_LPTIM_StartCounter", "LL_LPTIM_OPERATING_MODE_CONTINUOUS") == [("LPTIM_CR", "modify", 0x4, 0x6)]
    assert fx("LL_LPTIM_ResetCounter") == [("LPTIM_CR", "set", 0x8, None)]
    assert fx("LL_LPTIM_SetAutoReload", "1000U") == [("LPTIM_ARR", "modify", 1000, 0xFFFF)]
    assert fx("LL_LPTIM_SetPrescaler", "LL_LPTIM_PRESCALER_DIV8") == [("LPTIM_CFGR", "modify", 0x600, 0xE00)]
    assert fx("LL_LPTIM_SetUpdateMode", "LL_LPTIM_UPDATE_MODE_ENDOFPERIOD") == [("LPTIM_CFGR", "modify", 0x400000,
                                                                                 0x400000)]
    assert fx("LL_LPTIM_ClearFlag_ARRM") == [("LPTIM_ICR", "set", 0x2, None)]
    assert fx("LL_LPTIM_ClearFlag_DIEROK") == [("LPTIM_ICR", "set", 0x1000000, None)]
    assert fx("LL_LPTIM_EnableIT_ARRM") == [("LPTIM_DIER", "set", 0x2, None)]


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


ISR, ICR, DIER, CFGR, CR, ARR, CNT = 0x000, 0x004, 0x008, 0x00C, 0x010, 0x018, 0x01C


def test_the_lptim_model_enforces_the_enable_constraints_and_raises_the_ok_flags():
    m = _model()
    assert (m("read", ARR), m("read", CNT), m("read", ISR)) == (1, 0, 0)
    m("write", ARR, 3)                                      # disabled: ignored, no ARROK
    assert (m("read", ARR), m("read", ISR)) == (1, 0)
    m("write", CFGR, 0x400000)                              # disabled: PRELOAD accepted
    m("write", CR, 0x1)
    m("write", CFGR, 0)                                     # enabled: ignored
    assert m("read", CFGR) == 0x400000
    m("write", ARR, 3)
    assert m("read", ARR) == 3 and m("read", ISR) & 0x10    # ARROK
    m("write", ICR, 0x10)
    assert not m("read", ISR) & 0x10 and m("read", ICR) == 0  # ICR clears and reads 0
    m("write", DIER, 0x2)
    assert m("read", DIER) == 0x2 and m("read", ISR) & 0x1000000


def test_the_lptim_model_counts_on_polling_in_continuous_and_single_mode():
    m = _model()
    m("write", CR, 0x1)
    m("write", ARR, 3)
    m("write", CR, 0x1 | 0x4)                               # continuous
    assert m("read", CR) == 0x1                             # start bits read back 0
    assert [m("read", CNT) for _ in range(3)] == [1, 2, 3]
    assert m("read", ISR) & 0x2                             # ARRM at ARR (this read wrapped the counter)
    assert m("read", CNT) == 1                              # keeps counting
    m("write", ICR, 0x2)
    assert not m("read", ISR) & 0x2
    m("write", CR, 0x1 | 0x8)                               # COUNTRST
    assert m("read", CNT) == 1 and m("read", CR) == 0x1     # cleared to 0, then this read stepped once
    m("write", CR, 0)                                       # disable: stops, keeps its value
    v = m("read", CNT)
    assert [m("read", CNT) for _ in range(3)] == [v, v, v]
    s = _model()
    s("write", CR, 0x1)
    s("write", ARR, 2)
    s("write", CR, 0x1 | 0x2)                               # single
    assert [s("read", CNT) for _ in range(5)] == [1, 2, 0, 0, 0]
    assert s("read", ISR) & 0x2 and s("read", ISR) & 0x80   # ARRM and the update event


def test_the_lptim_model_scales_time_by_the_prescaler_and_loads_a_preloaded_arr_at_the_update_event():
    m = _model()
    m("write", CFGR, (1 << 9) | 0x400000)                   # PRESC /2, PRELOAD
    m("write", CR, 0x1)
    m("write", ARR, 2)                                      # not running: immediate
    m("write", CR, 0x1 | 0x4)
    assert [m("read", CNT) for _ in range(4)] == [0, 1, 1, 2]
    m("write", ARR, 5)                                      # running with PRELOAD: pending
    assert m("read", ARR) == 2
    assert [m("read", CNT) for _ in range(2)] == [2, 0]     # wrap: update event
    assert m("read", ARR) == 5
