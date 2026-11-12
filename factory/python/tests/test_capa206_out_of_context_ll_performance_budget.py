"""CAPA-206 (SPI LL L41N, 2026-11-09 18:54Z, BLOCKED STUCK SAME_ITEM_FAILED_3X:SWE1-04 "CPU constraint missing"): the
SPI LL and TIM LL work-order specs carry no simulation_performance budget, unlike every other LL order (CRC, RCC, IWDG,
WWDG), so SWE.1 had no measurable CPU/timing requirement and the inspector failed SWE1-04 three times. The factory now
prepares the input itself: an out-of-context LL driver order without a budget gets the factory's LL simulation budget
(the same targets as the other LL orders; timing decisions delegated by the owner 2026-11-03)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from forge_factory import simulation_performance as SP
from forge_factory import upstream as U

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"


def _spec(name):
    return json.loads((EXAMPLES / name / "workorder.json").read_text())


@pytest.mark.parametrize("example", ["0011l-st-cube-spi-swe1-gen", "0013l-st-cube-tim-swe1-gen"])
def test_an_out_of_context_ll_order_without_a_budget_gets_the_factory_ll_budget(example):
    spec = _spec(example)
    assert SP.FIELD not in spec and spec["layer"] == "LL"
    budget, note = SP.prepared(spec, U.OUT_OF_CONTEXT)
    assert budget == SP.validate(dict(SP.OUT_OF_CONTEXT_LL)) == _spec("0016c-st-cube-wwdg")[SP.FIELD]
    assert "CAPA-206" in note and "factory" in note


def test_a_declared_budget_is_kept_and_nothing_is_invented_elsewhere():
    wwdg_hal = _spec("0016m-wwdg-hal")
    assert SP.prepared(wwdg_hal, U.OUT_OF_CONTEXT) == (wwdg_hal[SP.FIELD], None)
    spi = _spec("0011l-st-cube-spi-swe1-gen")
    for status in ("APPROVED", "NOT_PROVIDED"):  # a safety order or an approved upstream allocates its own budget
        assert SP.prepared(spi, status) == (None, None)
    assert SP.prepared({**spi, "layer": "HAL"}, U.OUT_OF_CONTEXT) == (None, None)


def test_the_work_order_preparation_uses_the_prepared_budget():
    src = (Path(SP.__file__).parent / "workorder.py").read_text()
    assert "simulation_performance.prepared(spec, upstream[\"status\"])" in src
