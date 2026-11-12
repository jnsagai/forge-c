"""Measurement capability is separate from style acceptance; cover declared APIs and inputs."""
import json

import pytest
from forge_factory import simulation_performance as F
from forge_factory.common import REPO_ROOT
from forge_factory.layer import ll_measure_unit


@pytest.fixture
def static_header(tmp_path):
    (tmp_path / ".forge-run").mkdir()
    man = {"layer": "LL", "peripheral": "crc",
           "operation_scope": {"schema": "forge-c/operation-scope/1",
                               "functions": ["LL_CRC_Write_IDR", "LL_CRC_Read_IDR"],
                               "register_fields": ["CRC_IDR.IDR"], "primary_sections": ["26.4.2"], "dependencies": []},
           F.FIELD: {"schema": F.SCHEMA, "instructions_per_call": 64, "microseconds_per_call": 100,
                     "performance_mips": 100, "test_source": F.TEST}}
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps(man))
    header = tmp_path / "software/ll/stm32n6xx_ll_crc.h"
    header.parent.mkdir(parents=True)
    header.write_text('#include <stdint.h>\n'
                      'static void LL_CRC_Write_IDR(volatile uint32_t *reg, uint32_t value) { *reg = value; }\n'
                      'static uint32_t LL_CRC_Read_IDR(const volatile uint32_t *reg) { return *reg; }\n')
    return tmp_path, header, man


def test_static_header_functions_can_be_instrumented_without_rewriting_driver(static_header):
    ws, header, _ = static_header
    original = header.read_bytes()
    assert F.symbols(ws) == ["forge_measure_LL_CRC_Write_IDR", "forge_measure_LL_CRC_Read_IDR"]
    unit = ll_measure_unit(header.read_text(), ws)
    assert "forge_measure_LL_CRC_Write_IDR(volatile uint32_t *reg, uint32_t value)" in unit
    assert "forge_measure_LL_CRC_Read_IDR(const volatile uint32_t *reg)" in unit
    output = ws / "build"
    output.mkdir()
    assert F.prepare(ws, output).is_file()
    assert header.read_bytes() == original


def test_missing_declared_api_cannot_shrink_cost_scope(static_header):
    ws, header, _ = static_header
    header.write_text('#include <stdint.h>\nstatic inline void LL_CRC_Write_IDR(volatile uint32_t *reg, '
                      'uint32_t value) { *reg = value; }\n')
    with pytest.raises(ValueError, match="SIMULATION_PERFORMANCE_DECLARED_SCOPE_MISMATCH"):
        F.symbols(ws)


def test_device_build_input_is_bound_in_delivery_first_measurement(tmp_path, monkeypatch):
    # A real prepared work-order contract; no model inference or vendor candidate.
    from forge_factory import development_execution as E
    from forge_factory import workorder as W

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    ws, _ = W.prepare(REPO_ROOT / "examples/0014g-st-crc-idr-qwen-delivery", "WO-MEASURE-INPUT-FIXTURE",
                      purpose="QM", execution_policy=E.DEMO)
    before = F.source_files(ws)
    assert "inputs/forge_crc_device.h" in before
    device = ws / "inputs/forge_crc_device.h"
    device.chmod(0o600)
    device.write_text(device.read_text() + "\n/* changed type/layout input */\n")
    with pytest.raises(ValueError, match="SIMULATION_PERFORMANCE_DECLARED_INPUT_CHANGED"):
        F.source_files(ws)

