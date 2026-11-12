"""Authored LL/HAL measurement uses real Arm/Renode evidence, with no model calls."""
import json
import shutil

import pytest
from forge_factory import layer
from forge_factory import simulation_performance as F
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import sim

BUDGET = {"schema": F.SCHEMA, "instructions_per_call": 64, "microseconds_per_call": 100,
          "performance_mips": 100, "test_source": F.TEST}


@pytest.fixture(params=[("rcc", "LL"), ("iwdg", "LL"), ("rcc", "HAL"), ("iwdg", "HAL")])
def authored(tmp_path, request, monkeypatch):
    peripheral, kind = request.param
    (tmp_path / ".forge-run").mkdir()
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps({
        "layer": kind, "peripheral": peripheral, F.FIELD: BUDGET}))
    prefix = layer.api_prefix(kind, tmp_path)
    header = layer.api_header(kind, tmp_path)
    definitions = (f"void {prefix}Write(volatile uint32_t *reg, uint32_t value) {{ *reg = value; }}\n"
                   f"uint32_t {prefix}Read(volatile uint32_t *reg) {{ return *reg; }}\n")
    text = "#include <stdint.h>\n" + (definitions.replace("void " + prefix, "static inline void " + prefix)
            .replace("uint32_t " + prefix, "static inline uint32_t " + prefix) if kind == "LL" else
            f"void {prefix}Write(volatile uint32_t *reg, uint32_t value);\n"
            f"uint32_t {prefix}Read(volatile uint32_t *reg);\n")
    path = tmp_path / header
    path.parent.mkdir(parents=True)
    path.write_text(text)
    if kind == "HAL":
        (tmp_path / layer.hal_c(tmp_path)).write_text(f'#include "{path.name}"\n' + definitions)
    test = tmp_path / F.TEST
    test.parent.mkdir(parents=True)
    call = "forge_measure_" if kind == "LL" else ""
    test.write_text(f'''#include "forge_performance_calls.h"
#include "forge_target_test.h"
FORGE_MAILBOX_DEFINE;
int main(void) {{
 volatile uint32_t value = 0U;
 FORGE_TEST_BEGIN();
 {call}{prefix}Write(&value, 0x1234U);
 TCHECK(1, {call}{prefix}Read(&value) == 0x1234U);
 FORGE_TEST_END(); return 0;
}}
''')
    monkeypatch.setenv("FORGE_MCP_TRUST", "env")
    monkeypatch.setenv("FORGE_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_ROLE", "swe5-author")
    monkeypatch.setenv("FORGE_PHASE", "SWE.5")
    return tmp_path, kind, prefix


def test_authored_public_scope_and_generated_calls(authored):
    ws, kind, prefix = authored
    wanted = [("forge_measure_" if kind == "LL" else "") + prefix + n for n in ("Write", "Read")]
    assert set(F.symbols(ws)) == set(wanted)
    output = ws / "build"
    output.mkdir()
    unit = F.prepare(ws, output)
    assert unit.is_file()
    header = (output / "forge_performance_calls.h").read_text()
    assert layer.api_header(kind, ws).split("/")[-1] in header
    assert not (ws / ".forge-run/delivery").exists()  # No fabricated delivered-code scope.


def test_missing_api_definition_cannot_silently_shrink_measurement_scope(authored):
    ws, kind, prefix = authored
    path = ws / layer.api_header(kind, ws)
    path.write_text(path.read_text() + f"void {prefix}Missing(void);\n")
    with pytest.raises(ValueError, match="SIMULATION_PERFORMANCE_.*SCOPE"):
        F.symbols(ws)


def test_measurement_scope_rejects_unsupported_function_macro(authored):
    ws, kind, prefix = authored
    path = ws / layer.api_header(kind, ws)
    path.write_text(path.read_text() + f"#define {prefix}Hidden(x) ((x)+1U)\n")
    with pytest.raises(ValueError, match="SIMULATION_PERFORMANCE_.*SCOPE"):
        F.symbols(ws)


@pytest.mark.skipif(not (sim.renode_bin() and shutil.which("arm-none-eabi-gcc")), reason="Arm/Renode unavailable")
def test_authored_api_runs_instrumented_and_sealed(authored):
    ws, _, _ = authored
    out = sdk.invoke("forge-sim-mcp", next(o for o in sim.OPERATIONS if o.name == "run_renode"), {})
    assert out["status"] == "PASS", out
    measured = F.verify_result(ws, out)
    assert measured["status"] == "PASS"
    assert measured["hardware_wcet"] == "NOT_MEASURED"
    assert set(measured["samples"]) == set(F.symbols(ws))
    assert all(len(samples) == 1 for samples in measured["samples"].values())
    header = ws / layer.api_header(layer.layer_of(ws), ws)
    header.write_text(header.read_text() + "\n/* changed after measurement */\n")
    with pytest.raises(ValueError, match="INPUT_CHANGED"):
        F.verify_result(ws, out)


@pytest.mark.skipif(not (sim.renode_bin() and shutil.which("arm-none-eabi-gcc")), reason="Arm/Renode unavailable")
def test_cost_pass_never_waives_functional_failure(authored):
    ws, _, _ = authored
    path = ws / F.TEST
    path.write_text(path.read_text().replace("== 0x1234U", "== 0x1235U"))
    out = sdk.invoke("forge-sim-mcp", next(o for o in sim.OPERATIONS if o.name == "run_renode"), {})
    assert out["status"] == "FAIL", out
    assert F.verify_result(ws, out)["status"] == "PASS"  # Measured cost and functional acceptance stay separate.


@pytest.mark.skipif(not (sim.renode_bin() and shutil.which("arm-none-eabi-gcc")), reason="Arm/Renode unavailable")
def test_real_over_budget_calls_fail(authored):
    ws, _, _ = authored
    path = ws / ".forge-run/manifest.json"
    manifest = json.loads(path.read_text())
    manifest[F.FIELD]["instructions_per_call"] = 1
    path.write_text(json.dumps(manifest))
    out = sdk.invoke("forge-sim-mcp", next(o for o in sim.OPERATIONS if o.name == "run_renode"), {})
    assert out["status"] == "FAIL", out
    measured = F.verify_result(ws, out)
    assert measured["status"] == "FAIL" and any("CALL_BUDGET_EXCEEDED" in i for i in measured["issues"])


def test_authored_combined_layer_requires_separate_qualified_scope(authored):
    ws, _, _ = authored
    path = ws / ".forge-run/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["layer"] = "LL+HAL"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="SIMULATION_PERFORMANCE_.*SCOPE"):
        F.symbols(ws)
