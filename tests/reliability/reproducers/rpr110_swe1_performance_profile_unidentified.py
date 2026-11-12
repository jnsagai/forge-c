"""RPR-110 (Fabro run WO-F014-CMP-SWE1-CRCL-20261102-05, cloud comparison line, loop10, 2026-11-02): full CRC LL from
ST code (0014l) with the owner's simulation-performance target. The factory-generated SWE.1 budget requirements said
"measured in the pinned Renode profile" without naming it; the inspector failed SWE1-02/SWE1-04 in rounds 2 and 3
because no Renode version, platform description or configuration hash defined the measurement, and the author cannot
change the generated text: BLOCKED STUCK SAME_ITEM_FAILED_3X.

Scenario: the real swe1.budget_requirements for a work order with that simulation-performance budget (manifest and
peripheral profile stubbed; no file is written). Symptom: neither the statement nor the verification of the two
simulation requirements names the Renode version and the platform description the target runs load."""
import sys
from pathlib import Path

SIG = "a simulation-performance requirement names no Renode version or platform description for its measurement"


def main() -> int:
    from forge_factory import layer, simulation_performance
    from forge_factory.lrtx import swe1

    perf = {"schema": "forge-c/simulation-performance-budget/1", "instructions_per_call": 64,
            "microseconds_per_call": 100, "performance_mips": 100, "test_source": "software/tests/target/test_performance.c"}
    swe1._manifest = lambda _ws: {"budgets": {"flash_bytes": 4096, "static_ram_bytes": 64, "stack_bytes": 128}}
    simulation_performance.selected = lambda _ws: perf
    layer.profile = lambda _ws: {"id": "crc", "sim": {"platform": "stm32n6_crc.repl", "model": "crc_model.py"}}
    reqs = [r for r in swe1.budget_requirements(Path("."), "CRC LL driver") if r["key"].startswith("budget_simulation")]
    if len(reqs) != 2:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no simulation-performance requirements")
        return 2
    text = [r["statement"] + " " + r["verification"] for r in reqs]
    if all("Renode 1." in t and "stm32n6_crc.repl" in t for t in text):
        print("SYMPTOM_ABSENT")
        return 0
    print(f"SYMPTOM_PRESENT:{SIG}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
