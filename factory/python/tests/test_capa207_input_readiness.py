"""CAPA-207 (owner 2026-11-09 "implement the 3 points that could make it faster"): a driver order's run inputs are
checked before launch; SPI LL L41N spent 4 h of SWE.1 before SWE1-04 showed its inputs held no CPU/timing budget."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from forge_factory import input_readiness as IR
from forge_factory.afo import owner_supervised_development as D

EXAMPLES = Path(__file__).resolve().parents[3] / "examples"


def _spec(name):
    return json.loads((EXAMPLES / name / "workorder.json").read_text())


@pytest.mark.parametrize("lineage", ["wwdg-ll", "wwdg-hal", "spi-ll", "tim-ll"])
def test_the_swe1_stage_ladder_inputs_are_ready(lineage):
    ex = D._LINEAGE[lineage]["example"]
    assert IR.gaps(_spec(ex), purpose="ASPICE_ONLY", upstream_approved=False) == []


def test_a_hal_order_without_a_cpu_timing_budget_is_an_input_gap():
    spec = {k: v for k, v in _spec("0016m-wwdg-hal").items() if k != "simulation_performance"}
    assert IR.gaps(spec, purpose="ASPICE_ONLY", upstream_approved=False) == ["CPU_TIMING_BUDGET"]
    ll = _spec("0011l-st-cube-spi-swe1-gen")  # the factory prepares the LL budget only out of context (CAPA-206)
    assert IR.gaps(ll, purpose="DEVELOPMENT", upstream_approved=False) == ["CPU_TIMING_BUDGET"]
    assert IR.gaps(ll, purpose="ASPICE_ONLY", upstream_approved=True) == ["CPU_TIMING_BUDGET"]


def test_missing_documents_budgets_target_and_names_are_input_gaps():
    spec = _spec("0016c-st-cube-wwdg")
    spec["inputs"] = [i for i in spec["inputs"] if i["role"] not in ("datasheet", "reference_manual_wwdg_chapter")]
    spec["budgets"] = {"flash_bytes": 4096, "static_ram_bytes": 0, "stack_bytes": 128}
    spec["target"] = {**spec["target"], "part_number": ""}
    spec["system_names"] = []
    spec["simulation_performance"] = {**spec["simulation_performance"], "instructions_per_call": 0}
    assert IR.gaps(spec, purpose="ASPICE_ONLY", upstream_approved=False) == [
        "INPUT_ROLE_MISSING_DATASHEET", "INPUT_ROLE_MISSING_REFERENCE_MANUAL_CHAPTER", "RESOURCE_BUDGET",
        "TARGET_FIELDS", "SYSTEM_NAMES", "CPU_TIMING_BUDGET_INVALID"]


def test_non_driver_orders_are_not_checked():
    assert IR.gaps({"layer": "APP"}, purpose="ASPICE_ONLY", upstream_approved=False) == []
