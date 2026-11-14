"""Owner 2026-11-13 "run SWE.1 on spi module now on local. use this new way of working": the SPI module order
`0011u-st-cube-spi-module` (ST's frozen SPI HAL + SPI LL, functional template v2) prepares with no model exactly as the
UART module order does (test_f020_uart_order: inputs from the line's content-addressed cache, delivery build check).

The governance inventory classifies every delivered public function by the scope rule (HAL: the functions the
delivered SPI HAL headers declare; LL: every inline function of the delivered LL header, I2S included), the in-scope
lists are the rule's, I2S/PCM, the extended HAL services and DMA pause/resume/stop are delivered-out-of-scope, the
input register holds the SPI chapter, memory map, vector table, datasheet, guideline and device header as requirement
sources and the delivered code only as implementation under analysis; and every packet of the real order fits the
packet bound (D24)."""
from __future__ import annotations

import json
import re

import jsonschema
import pytest
import test_f020_uart_order as U
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT

EX = "0011u-st-cube-spi-module"
WO_ID = "WO-F020-SPI-MODULE"
HAL_IN = {f"HAL_SPI_{n}" for n in (
    "Init", "DeInit", "MspInit", "MspDeInit", "Transmit", "Receive", "TransmitReceive", "Transmit_IT", "Receive_IT",
    "TransmitReceive_IT", "IRQHandler", "Transmit_DMA", "Receive_DMA", "TransmitReceive_DMA", "Abort", "Abort_IT",
    "RegisterCallback", "UnRegisterCallback", "TxCpltCallback", "RxCpltCallback", "TxRxCpltCallback",
    "TxHalfCpltCallback", "RxHalfCpltCallback", "TxRxHalfCpltCallback", "ErrorCallback", "AbortCpltCallback",
    "SuspendCallback", "GetState", "GetError")}
LL_RULE = [r"(Enable|Disable|IsEnabled)", r"(Set|Get)Mode",
           r"(Set|Get)(Standard|ClockPhase|ClockPolarity|BaudRatePrescaler|TransferBitOrder|TransferDirection|DataWidth|"
           r"NSSMode|NSSPolarity|TransferSize|FIFOThreshold)",
           r"(StartMasterTransfer|IsActiveMasterTransfer|SuspendMasterTransfer|GetRemainingDataFrames)",
           r".*CRC.*", r"(Enable|Disable|IsEnabled)DMAReq_(RX|TX)", r"(Enable|Disable|IsEnabled)IT_.*",
           r"(IsActiveFlag|ClearFlag)_.*", r"(Transmit|Receive)Data(8|16|32)"]
FR002 = {"RM0486-rev4-ch67-spi.md", "RM0486-rev4-memory-map-excerpt-spi.md", "RM0486-rev4-vector-table.md",
         "DS14791-rev9-stm32n6x5-x7-datasheet.md", "hal_driver_guideline.md", "stm32n657xx.h"}
DELIVERED = {"software/hal/stm32n6xx_hal_spi.c", "software/hal/stm32n6xx_hal_spi.h",
             "software/hal/stm32n6xx_hal_spi_ex.c", "software/hal/stm32n6xx_hal_spi_ex.h",
             "software/ll/stm32n6xx_ll_spi.h"}


@pytest.fixture()
def spi(tmp_path, monkeypatch):
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
    ll = {d.name for d in S.index(files["software/ll/stm32n6xx_ll_spi.h"].decode(errors="replace"), "ll")
          if d.kind == "static_inline"}
    return hal, ll


def test_the_spi_module_order_prepares_and_classifies_every_delivered_public_function(spi):
    ws, man, spec = spi
    assert man["swe1_level"] == "functional" and "register_contract" not in man
    inv = json.loads((ws / "inputs/governance-inventory.json").read_text())
    jsonschema.Draft202012Validator(json.loads(U.INV_SCHEMA.read_text())).validate(inv)
    assert inv["module"] == "SPI"
    hal, ll = _public()
    api = {a["function"]: a for a in inv["api"]}
    assert set(api) == hal | ll and any(f.startswith("LL_I2S_") for f in ll)
    assert all(a["scope_class"] in ("in", "out") and a["scope_group"] for a in api.values())
    assert {f for f in hal if api[f]["component"] == "HAL_SPI"} == hal
    assert {f for f in ll if api[f]["component"] == "LL_SPI"} == ll
    assert {f for f in hal if api[f]["scope_class"] == "in"} == HAL_IN
    ll_in = {f for f in ll if api[f]["scope_class"] == "in"}
    by_rule = {f for f in ll if f.startswith("LL_SPI_") and any(re.fullmatch(r, f.removeprefix("LL_SPI_"))
                                                               for r in LL_RULE)}
    assert ll_in == by_rule
    out = {f for f, a in api.items() if a["scope_class"] == "out"}
    assert out == (hal | ll) - HAL_IN - by_rule
    assert {f for f in ll if f.startswith("LL_I2S_")} <= out and {"HAL_SPI_DMAPause", "HAL_SPIEx_FlushRxFifo"} <= out
    assert inv["not_delivered"] == spec["scope_rule"]["not_delivered"]
    regs = {r["name"]: r for r in inv["inputs"]}
    assert FR002 <= {n for n, r in regs.items() if r["role"] == "requirement_source"}
    assert {n for n, r in regs.items() if r["role"] == "implementation_under_analysis"} >= DELIVERED
    feats = {f["feature"]: f["scope_class"] for f in inv["rm_features"]}
    assert feats["67.4.12"] == feats["67.7"] == feats["67.5.3"] == "in" and feats["67.9"] == "out"
    comps = {c["id"]: c for c in spec["module"]["components"]}
    assert set(comps) == {"HAL_SPI", "LL_SPI"} and all(c["uses"] == [] for c in comps.values())


def test_real_spi_module_packets_fit_the_packet_bound(spi, monkeypatch):
    U.test_real_module_packets_fit_the_packet_bound(spi, monkeypatch)
