"""Owner 2026-11-14 "after finishing SPI, i want omniverse to place TIM to do the same SWE 1 work": the TIM module order
`0013u-st-cube-tim-module` (ST's frozen TIM HAL + TIM LL for the general-purpose timers TIM2-TIM5, functional template
v2) prepares with no model exactly as the SPI and UART module orders do (test_f020_uart_order: inputs from the line's
content-addressed cache, delivery build check).

The governance inventory classifies every delivered public function by the scope rule (HAL: the functions the
delivered TIM HAL headers declare, the vendor-internal helpers they declare included; LL: every inline function of the
delivered LL header); the in-scope sets are the six timer modes, clock/synchronisation, interrupt/event, callbacks and
state queries of the HAL and the TIM2-TIM5 subset of the LL; the extended HAL services, DMA burst, the helpers and the
advanced-control LL features are delivered-out-of-scope; the input register holds the TIM2-5 chapter, memory map,
vector table, datasheet, guideline and device header as requirement sources and the delivered code only as
implementation under analysis; and every packet of the real order fits the packet bound (D24)."""
from __future__ import annotations

import json
import re

import jsonschema
import pytest
import test_f020_uart_order as U
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT

EX = "0013u-st-cube-tim-module"
WO_ID = "WO-F020-TIM-MODULE"
HAL_MODES = ("Base", "OC", "PWM", "IC", "OnePulse", "Encoder")
HAL_IN_EXACT = {"HAL_TIM_ReadCapturedValue", "HAL_TIM_ConfigClockSource", "HAL_TIM_SlaveConfigSynchro",
                "HAL_TIM_SlaveConfigSynchro_IT", "HAL_TIMEx_MasterConfigSynchronization", "HAL_TIM_IRQHandler",
                "HAL_TIM_GenerateEvent", "HAL_TIM_GetActiveChannel", "HAL_TIM_GetChannelState"}
LL_EV = r"(UPDATE|CC[1-4]|TRIG)"
LL_RULE = [r"(Enable|Disable|IsEnabled)(Counter|UpdateEvent|ARRPreload|ExternalClock|MasterSlaveMode)",
           r"(Set|Get)(UpdateSource|OnePulseMode|CounterMode|ClockDivision|Counter|Prescaler|AutoReload)", "GetDirection",
           r"CC_((Enable|Disable|IsEnabled)(Preload|Channel)|SetUpdate|(Set|Get)DMAReqTrigger)",
           r"OC_(ConfigOutput|(Set|Get)(Mode|Polarity)|(Enable|Disable|IsEnabled)(Fast|Preload)|(Set|Get)CompareCH[1-4])",
           r"IC_(Config|(Set|Get)(ActiveInput|Prescaler|Filter|Polarity)|GetCaptureCH[1-4])",
           r"Set(ClockSource|EncoderMode|TriggerOutput|SlaveMode|TriggerInput)", "ConfigETR",
           rf"(Enable|Disable|IsEnabled)(DMAReq|IT)_{LL_EV}", r"(IsActiveFlag|ClearFlag)_(UPDATE|CC[1-4]|TRIG|CC[1-4]OVR)",
           rf"GenerateEvent_{LL_EV}"]
FR002 = {"RM0486-rev4-ch54-tim2-5.md", "RM0486-rev4-memory-map-excerpt-tim.md", "RM0486-rev4-vector-table.md",
         "DS14791-rev9-stm32n6x5-x7-datasheet.md", "hal_driver_guideline.md", "stm32n657xx.h"}
DELIVERED = {"software/hal/stm32n6xx_hal_tim.c", "software/hal/stm32n6xx_hal_tim.h",
             "software/hal/stm32n6xx_hal_tim_ex.c", "software/hal/stm32n6xx_hal_tim_ex.h",
             "software/ll/stm32n6xx_ll_tim.h"}
LL_HDR = "software/ll/stm32n6xx_ll_tim.h"


def _hal_in(f: str) -> bool:
    return f in HAL_IN_EXACT or (f.startswith("HAL_TIM_") and f.endswith("Callback")) or any(
        f.startswith(f"HAL_TIM_{m}_") for m in HAL_MODES)


@pytest.fixture()
def tim(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    monkeypatch.setenv("FORGE_LRTX_ROOT", str(tmp_path / "lrtx"))
    monkeypatch.setattr(U, "EX", EX)
    monkeypatch.setattr(U, "WO_ID", WO_ID)
    ex = U._mirror(tmp_path)
    monkeypatch.setattr(WO, "REPO_ROOT", ex.parents[1])
    ws, man = WO.prepare(ex, WO_ID)
    monkeypatch.setattr(WO, "REPO_ROOT", REPO_ROOT)
    return ws, man, json.loads((REPO_ROOT / "examples" / EX / "workorder.json").read_text())


def _public() -> tuple[set[str], set[str]]:
    from forge_factory.brownfield import delivery as BD
    from forge_factory.brownfield import scope as S

    files = BD.stored(WO_ID)
    hdr = "".join(files[p].decode(errors="replace") for p in files if p.startswith("software/hal/") and p.endswith(".h"))
    hal = {d.name for p in files if p.startswith("software/hal/") and p.endswith(".c")
           for d in S.index(files[p].decode(errors="replace"), p) if re.search(rf"\b{d.name}\s*\(", hdr)}
    ll = {d.name for d in S.index(files[LL_HDR].decode(errors="replace"), "ll")
          if d.kind == "static_inline"}
    return hal, ll


def test_the_tim_module_order_prepares_and_classifies_every_delivered_public_function(tim):
    ws, man, spec = tim
    assert man["swe1_level"] == "functional" and "register_contract" not in man
    inv = json.loads((ws / "inputs/governance-inventory.json").read_text())
    jsonschema.Draft202012Validator(json.loads(U.INV_SCHEMA.read_text())).validate(inv)
    assert inv["module"] == "TIM"
    hal, ll = _public()
    api = {a["function"]: a for a in inv["api"]}
    assert set(api) == hal | ll and {"TIM_Base_SetConfig", "HAL_TIMEx_HallSensor_Init"} <= hal
    assert all(a["scope_class"] in ("in", "out") and a["scope_group"] for a in api.values())
    assert {f for f in hal if api[f]["component"] == "HAL_TIM"} == hal
    assert {f for f in ll if api[f]["component"] == "LL_TIM"} == ll
    hal_in = {f for f in hal if _hal_in(f)}
    assert {f for f in hal if api[f]["scope_class"] == "in"} == hal_in and len(hal_in) == 89
    ll_in = {f for f in ll if api[f]["scope_class"] == "in"}
    by_rule = {f for f in ll if any(re.fullmatch(r, f.removeprefix("LL_TIM_")) for r in LL_RULE)}
    assert ll_in == by_rule and len(ll_in) == 139
    out = {f for f, a in api.items() if a["scope_class"] == "out"}
    assert out == (hal | ll) - hal_in - by_rule
    assert {f for f in hal if f.startswith(("TIM_", "TIMEx_", "HAL_TIMEx_", "HAL_TIM_DMABurst"))} - {
        "HAL_TIMEx_MasterConfigSynchronization"} <= out
    assert {"LL_TIM_SetRepetitionCounter", "LL_TIM_OC_SetCompareCH5", "LL_TIM_EnableBRK", "LL_TIM_IsActiveFlag_IDX",
            "LL_TIM_ConfigDMABurst"} <= out
    assert inv["not_delivered"] == spec["scope_rule"]["not_delivered"]
    regs = {r["name"]: r for r in inv["inputs"]}
    assert FR002 <= {n for n, r in regs.items() if r["role"] == "requirement_source"}
    assert {n for n, r in regs.items() if r["role"] == "implementation_under_analysis"} >= DELIVERED
    feats = {f["feature"]: f["scope_class"] for f in inv["rm_features"]}
    assert feats["54.4.3"] == feats["54.4.11"] == feats["54.4.18"] == feats["54.4.30"] == "in"
    assert feats["54.4.26"] == feats["54.4.14"] == feats["54.4.12"] == "out"
    comps = {c["id"]: c for c in spec["module"]["components"]}
    assert set(comps) == {"HAL_TIM", "LL_TIM"} and all(c["uses"] == [] for c in comps.values())


def test_real_tim_module_packets_fit_the_packet_bound(tim, monkeypatch):
    U.test_real_module_packets_fit_the_packet_bound(tim, monkeypatch)
