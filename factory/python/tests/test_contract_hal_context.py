"""A vendor HAL module's public header uses the configured framework include context.

The contract gate must still type-check every call: supplying dependency types must
not conceal an invalid function argument list.
"""
import json

import pytest
from forge_factory import workorder as WO
from forge_factory.assurance import register_contract as RC
from forge_factory.brownfield import delivery as D
from forge_factory.common import REPO_ROOT
from onboarding_util import need_inputs


@pytest.mark.parametrize("example,header,function,args", [
    ("0010d-st-cube-gpio-hal", "gpio", "HAL_GPIO_Init", ["GPIOA", "NULL"]),
    ("0011d-st-cube-spi-hal", "spi", "HAL_SPI_Init", ["NULL"]),
    ("0012d-st-cube-usart-hal", "uart", "HAL_UART_Init", ["NULL"]),
    ("0013d-st-cube-tim-hal", "tim", "HAL_TIM_Base_Init", ["NULL"]),
])
def test_real_vendor_contract_calls_compile_and_bad_arity_still_fails(tmp_path, monkeypatch,
                                                                    example, header, function, args):
    need_inputs()
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    ws, _ = WO.prepare(REPO_ROOT / "examples" / example, "WO-CONTRACT-HAL")
    for rel, content in D.stored("WO-CONTRACT-HAL").items():
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    for rel, content in {
        RC.EFFECTS: {"schema": "forge-c/register-effects/1", "effects": [
            {"case": "NULL_INPUT", "swr": "SWR-001", "op": "no_write", "status": "HAL_ERROR"}]},
        RC.CALLS: {"schema": "forge-c/api-calls/1", "calls": {
            "NULL_INPUT": {"function": function, "args": args}}},
    }.items():
        path = ws / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content))
    incs = [ws / "software/hal", ws / "software/ll"]
    assert RC.check_compiles(ws, incs, f"stm32n6xx_hal_{header}.h") == []
    calls = json.loads((ws / RC.CALLS).read_text())
    calls["calls"]["NULL_INPUT"]["args"] = args + ["0U", "0U"]
    (ws / RC.CALLS).write_text(json.dumps(calls))
    errors = RC.check_compiles(ws, incs, f"stm32n6xx_hal_{header}.h")
    assert errors and all(e.startswith("CONTRACT_CALL_DOES_NOT_COMPILE:") for e in errors)
