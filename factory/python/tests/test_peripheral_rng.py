"""Feature 014 operation-24 campaign (owner 2026-10-27 "RNG, LPTIM, WWDG"): the RNG peripheral profile, its behavioural
Renode model and the ST LL code work order (ST's CubeN6 RNG LL header delivered FROZEN). The ST sources are local
inputs: tests needing them skip without them."""
import json
import os
import re
from pathlib import Path

import pytest
from forge_factory import peripheral
from forge_factory.common import REPO_ROOT

EX = REPO_ROOT / "examples/0017c-st-cube-rng"
MODEL = REPO_ROOT / "factory/sim/stm32n6/rng_model.py"
ST = Path(os.environ.get("FORGE_DATA_ROOT", "/nonexistent")) / "inputs/st"
LL_H = ST / "stm32n6xx-hal-driver-v1.4.0/src/stm32n6xx-hal-driver-1.4.0/Inc/stm32n6xx_ll_rng.h"
CMSIS = ST / "cmsis-device-n6-v1.4.0/src/cmsis-device-n6-1.4.0/Include"


def test_the_rng_profile_validates_and_names_the_secure_instance():
    p = peripheral.load("rng")
    assert (p["register_prefix"], p["base_address"], p["mm_page"], p["rm"]["chapter"]) == ("RNG", "0x54020000", 177, 47)
    assert not any(re.search(r"\bRCC(?:\b|_)", v) and "(RCC)" not in v for v in p["prompt"].values())
    assert "RNG_CR.CONDRST" in p["prompt"]["swe1_cover"] and "rc_w0" in p["prompt"]["swe1_cover"]
    spec = json.loads((EX / "workorder.json").read_text())
    assert spec["delivery"]["code_mode"] == "FROZEN" and spec["peripheral"] == "rng"
    assert spec["delivery"]["files"] == [{"from": "Inc/stm32n6xx_ll_rng.h", "to": "software/ll/stm32n6xx_ll_rng.h"}]
    assert len(spec["delivery"]["scope"]["functions"]) == 17
    assert all((EX / i["path"]).resolve().parent.is_dir() for i in spec["inputs"])
    m = json.loads((REPO_ROOT / "examples/0017-rng-st/inputs/inputs-manifest.json").read_text())
    assert [(d["markdown"], d["pages"]) for d in m["documents"]] == [
        ("RM0486-rev4-ch47-rng.md", [2286, 2302]), ("RM0486-rev4-memory-map-excerpt-rng.md", [177, 177])]


@pytest.mark.skipif(not (LL_H.is_file() and CMSIS.is_dir()), reason="ST STM32CubeN6 v1.4.0 sources are local inputs")
def test_st_rng_code_is_extracted_with_the_condrst_pulse_and_complement_flag_clears():
    """ST: SET_BIT/CLEAR_BIT(RNGx->CR, ...), MODIFY_REG(RNGx->CR, RNG_CR_CED | RNG_CR_CONDRST, ... | RNG_CR_CONDRST)
    then CLEAR_BIT(RNGx->CR, RNG_CR_CONDRST) (RM0486 47.7.1: CED is written only with CONDRST in the same access), and
    WRITE_REG(RNGx->SR, ~RNG_SR_CEIS) (rc_w0, 47.7.2)."""
    from forge_factory.brownfield import scope as S

    texts = [LL_H.read_text(errors="replace"), (CMSIS / "stm32n657xx.h").read_text(errors="replace"),
             (CMSIS / "stm32n6xx.h").read_text(errors="replace")]
    macros = S.constant_macros(texts)
    defs = {d.name: d for t, r in ((texts[2], "stm32n6xx.h"), (texts[0], "ll.h")) for d in S.index(t, r)}

    def fx(fn, *a):
        return [(e.register, e.op, e.mask, e.clear) for e in
                S.register_effects(defs[fn], macros, "cmsis", ["RNG", *a], defs, prefix="RNG")]

    assert fx("LL_RNG_Enable") == [("RNG_CR", "set", 0x4, None)]
    assert fx("LL_RNG_Disable") == [("RNG_CR", "clear", 0x4, None)]
    assert fx("LL_RNG_EnableIT") == [("RNG_CR", "set", 0x8, None)]
    assert fx("LL_RNG_EnableClkErrorDetect") == [("RNG_CR", "modify", 0x40000000, 0x40000020),
                                                 ("RNG_CR", "clear", 0x40000000, None)]
    assert fx("LL_RNG_DisableClkErrorDetect") == [("RNG_CR", "modify", 0x40000020, 0x40000020),
                                                  ("RNG_CR", "clear", 0x40000000, None)]
    assert fx("LL_RNG_ClearFlag_CEIS") == [("RNG_SR", "write", 0xFFFFFFDF, None)]
    assert fx("LL_RNG_ClearFlag_SEIS") == [("RNG_SR", "write", 0xFFFFFFBF, None)]
    assert fx("LL_RNG_ReadRandData32") == [("RNG_DR", "read", None, None)]


def _model(scenario=None):
    src, ns = MODEL.read_text(), {}
    if scenario:
        src = src.replace('SCENARIO = "default"', f'SCENARIO = "{scenario}"')

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


def test_the_rng_model_gates_ced_on_condrst_and_streams_a_fixed_sequence_while_enabled():
    m = _model()
    assert (m("read", 0x000), m("read", 0x004), m("read", 0x008)) == (0x00800D00, 0, 0)
    assert (m("read", 0x00C), m("read", 0x010)) == (0x0003FFFF, 0x000072AC)
    m("write", 0x000, 0x00800D00 | 0x20)                    # CED without CONDRST: ignored
    assert m("read", 0x000) == 0x00800D00
    m("write", 0x000, 0x00800D00 | 0x20 | 0x40000000)       # with CONDRST: taken into account
    m("write", 0x000, 0x00800D00 | 0x20)                    # CONDRST cleared, CED kept
    assert m("read", 0x000) == 0x00800D20
    m("write", 0x000, 0x00800D00 | 0x40000000)              # ST's EnableClkErrorDetect: CED 0 with CONDRST
    m("write", 0x000, 0x00800D00)
    assert m("read", 0x000) == 0x00800D00
    m("write", 0x000, 0x00800D00 | 0x4 | 0x8)               # RNGEN and IE need no CONDRST
    assert m("read", 0x004) & 1
    assert [m("read", 0x008) for _ in range(2)] == [0xE124B63A, 0x8B9A74AB]
    m("write", 0x000, 0x00800D00)                           # disabled: no data
    assert (m("read", 0x004), m("read", 0x008)) == (0, 0)


def test_the_rng_error_flags_are_rc_w0_and_read_only_statuses_keep():
    m = _model("seed_error")
    assert m("read", 0x004) == 0x44                         # SECS and SEIS
    m("write", 0x004, 0xFFFFFFFF)                           # writing 1 has no effect
    assert m("read", 0x004) == 0x44
    m("write", 0x004, 0xFFFFFFBF)                           # ST's ~SEIS clear
    assert m("read", 0x004) == 0x04                         # SECS is read-only status
    m("write", 0x000, 0x00800D00 | 0x40000000)              # CONDRST clears RNG_SR
    assert m("read", 0x004) == 0
