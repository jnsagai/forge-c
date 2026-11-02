"""CAPA-110 (run WO-F014-CMP-SWE1-CRCL-20261102-05): the SWE.1 simulation-performance requirements said "measured in the
pinned Renode profile" without identifying it; the inspector failed SWE1-02/SWE1-04 three times because the
measurement configuration was not uniquely defined and the author cannot change the factory-generated text. The
requirements now name the pinned Renode version, the adapter and the platform description and peripheral model files
(with sha256) the target runs load."""
import json

from forge_factory.common import sha256_file
from forge_factory.lrtx import swe1
from forge_factory.mcp.servers import sim


def test_the_measurement_profile_names_renode_adapter_platform_and_model(monkeypatch):
    monkeypatch.setattr("forge_factory.layer.profile", lambda _ws: {"sim": {"platform": "stm32n6_crc.repl",
                                                                          "model": "crc_model.py"}})
    text = sim.measurement_profile(None)
    assert text.startswith(f"Renode {sim.RENODE_VERSION} portable; adapter {sim.ADAPTER_ID}; ")
    assert f"platform description factory/sim/stm32n6/stm32n6_crc.repl, sha256 {sha256_file(sim.SIM_DIR / 'stm32n6_crc.repl')[:16]}" in text
    assert f"peripheral model factory/sim/stm32n6/crc_model.py, sha256 {sha256_file(sim.SIM_DIR / 'crc_model.py')[:16]}" in text


def test_simulation_budget_requirements_carry_the_profile(tmp_path, monkeypatch):
    perf = {"schema": "forge-c/simulation-performance-budget/1", "instructions_per_call": 64, "microseconds_per_call": 100,
            "performance_mips": 100, "test_source": "software/tests/target/test_performance.c"}
    monkeypatch.setattr(swe1, "_manifest", lambda _ws: {"budgets": {"flash_bytes": 1, "static_ram_bytes": 1, "stack_bytes": 1}})
    monkeypatch.setattr("forge_factory.simulation_performance.selected", lambda _ws: perf)
    monkeypatch.setattr("forge_factory.layer.profile", lambda _ws: {"sim": {"platform": "stm32n6_crc.repl", "model": "crc_model.py"}})
    reqs = [r for r in swe1.budget_requirements(tmp_path, "CRC LL driver") if r["key"].startswith("budget_simulation")]
    assert len(reqs) == 2 and all("pinned Renode profile" not in r["statement"] for r in reqs)  # names one configuration
    assert all(r["verification"].startswith(f"Measurement configuration: Renode {sim.RENODE_VERSION} portable") and "stm32n6_crc.repl, sha256 " in r["verification"]
               for r in reqs)
