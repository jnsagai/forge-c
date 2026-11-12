"""Feature 014 operation-24 campaign (owner 2026-10-27 "RNG, LPTIM, WWDG"): the WWDG peripheral profile, its behavioural
Renode model and the ST LL code work order (ST's CubeN6 WWDG LL header delivered FROZEN). The ST sources are local
inputs: tests needing them skip without them."""
import json
import os
import re
from pathlib import Path

import pytest
from forge_factory import peripheral
from forge_factory.common import REPO_ROOT

EX = REPO_ROOT / "examples/0016c-st-cube-wwdg"
MODEL = REPO_ROOT / "factory/sim/stm32n6/wwdg_model.py"
ST = Path(os.environ.get("FORGE_DATA_ROOT", "/nonexistent")) / "inputs/st"
LL_H = ST / "stm32n6xx-hal-driver-v1.4.0/src/stm32n6xx-hal-driver-1.4.0/Inc/stm32n6xx_ll_wwdg.h"
CMSIS = ST / "cmsis-device-n6-v1.4.0/src/cmsis-device-n6-1.4.0/Include"


def test_the_wwdg_profile_validates_and_names_the_secure_instance():
    p = peripheral.load("wwdg")
    assert (p["register_prefix"], p["base_address"], p["mm_page"], p["rm"]["chapter"]) == ("WWDG", "0x50002C00", 181, 60)
    assert not any(re.search(r"\bRCC(?:\b|_)", v) and "(RCC)" not in v for v in p["prompt"].values())
    assert "WWDG_CR.WDGA" in p["prompt"]["swe1_cover"] and "write 0 to WWDG_SR.EWIF" in p["prompt"]["swe1_cover"]
    spec = json.loads((EX / "workorder.json").read_text())
    assert spec["delivery"]["code_mode"] == "FROZEN" and spec["peripheral"] == "wwdg"
    assert spec["delivery"]["files"] == [{"from": "Inc/stm32n6xx_ll_wwdg.h", "to": "software/ll/stm32n6xx_ll_wwdg.h"}]
    assert len(spec["delivery"]["scope"]["functions"]) == 12
    assert all((EX / i["path"]).resolve().parent.is_dir() for i in spec["inputs"])
    m = json.loads((REPO_ROOT / "examples/0016-wwdg-st/inputs/inputs-manifest.json").read_text())
    assert [(d["markdown"], d["pages"]) for d in m["documents"]] == [
        ("RM0486-rev4-ch60-wwdg.md", [2995, 3001]), ("RM0486-rev4-memory-map-excerpt-wwdg.md", [181, 181])]


@pytest.mark.skipif(not (LL_H.is_file() and CMSIS.is_dir()), reason="ST STM32CubeN6 v1.4.0 sources are local inputs")
def test_st_wwdg_code_is_extracted_as_field_writes_and_a_complement_flag_clear():
    """ST: SET_BIT(WWDGx->CR, WWDG_CR_WDGA), MODIFY_REG(WWDGx->CR, WWDG_CR_T, Counter), MODIFY_REG(WWDGx->CFR,
    WWDG_CFR_W, Window), WRITE_REG(WWDGx->SR, ~WWDG_SR_EWIF) (EWIF is cleared by writing 0, RM0486 60.6.3)."""
    from forge_factory.brownfield import scope as S

    texts = [LL_H.read_text(errors="replace"), (CMSIS / "stm32n657xx.h").read_text(errors="replace"),
             (CMSIS / "stm32n6xx.h").read_text(errors="replace")]
    macros = S.constant_macros(texts)
    defs = {d.name: d for t, r in ((texts[2], "stm32n6xx.h"), (texts[0], "ll.h")) for d in S.index(t, r)}

    def fx(fn, *a):
        return [(e.register, e.op, e.mask, e.clear) for e in
                S.register_effects(defs[fn], macros, "cmsis", ["WWDG", *a], defs, prefix="WWDG")]

    assert fx("LL_WWDG_Enable") == [("WWDG_CR", "set", 0x80, None)]
    assert fx("LL_WWDG_SetCounter", "0x7FU") == [("WWDG_CR", "modify", 0x7F, 0x7F)]
    assert fx("LL_WWDG_SetWindow", "0x50U") == [("WWDG_CFR", "modify", 0x50, 0x7F)]
    assert fx("LL_WWDG_SetPrescaler", "LL_WWDG_PRESCALER_8") == [("WWDG_CFR", "modify", 0x1800, 0x3800)]
    assert fx("LL_WWDG_EnableIT_EWKUP") == [("WWDG_CFR", "set", 0x200, None)]
    assert fx("LL_WWDG_ClearFlag_EWKUP") == [("WWDG_SR", "write", 0xFFFFFFFE, None)]


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


def test_the_wwdg_model_has_set_only_bits_a_polled_countdown_and_an_rc_w0_flag():
    m = _model()
    assert (m("read", 0x004), m("read", 0x008)) == (0x7F, 0)
    m("write", 0x004, 0x1800 | 0x200 | 0x50)                # WDGTB 3, EWI, W 0x50
    m("write", 0x004, 0x50)                                 # a write of 0 keeps EWI
    assert m("read", 0x004) == 0x200 | 0x50
    assert m("read", 0x000) == 0x7F                         # not active: no countdown
    m("write", 0x000, 0x80 | 0x42)                          # activate with T = 0x42
    assert [m("read", 0x000) & 0x7F for _ in range(4)] == [0x41, 0x40, 0x40, 0x40]
    assert m("read", 0x008) == 1                            # early wake-up flag at 0x40
    m("write", 0x008, 0xFFFFFFFF)                           # writing 1 has no effect
    assert m("read", 0x008) == 1
    m("write", 0x008, 0xFFFFFFFE)                           # ST's ~EWIF clear
    assert m("read", 0x008) == 0
    m("write", 0x000, 0x7F)                                 # refresh without WDGA: stays active
    assert m("read", 0x000) == 0x80 | 0x7E
