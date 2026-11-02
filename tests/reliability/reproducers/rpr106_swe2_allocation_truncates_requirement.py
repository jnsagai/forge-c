"""RPR-106 (Fabro run WO-F014-CMP-SWE2-OBL-20261102-01, loop10 cloud comparison line, 2026-11-02): CRC IDR greenfield
SWE.2. The deterministic SWE.2 renderer wrote component-level constraint requirements into the requirement allocation
table cut at 120 characters; the instruction/time budgets of SWR-012/SWR-013 vanished from the architecture and the
inspector failed SWE2-05 three times (BLOCKED STUCK).

Scenario: the real swe2.render with one function and one component-level requirement longer than 120 characters (the
workspace readers are stubbed: not part of the symptom). Symptom: the allocation table does not hold the whole
requirement."""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

SIG = "the SWE.2 allocation table truncates a component-level requirement"
REQ = ("When a scoped API is measured in the pinned Renode profile at 100 MIPS without injected interrupts or bus stalls, "
       "the CRC LL driver shall complete each measured call within 64 executed target instructions.")


def main() -> int:
    from forge_factory.assurance import hardware
    from forge_factory.inspection import engine
    from forge_factory.lrtx import swe2
    swe2._manifest = lambda _ws: {"work_order": "WO-RPR106",
                                  "budgets": {"flash_bytes": 4096, "static_ram_bytes": 0, "stack_bytes": 64}}
    swe2._ident = lambda _ws: {"pfx": "CRC", "fn": "LL_CRC_", "header": "stm32n6xx_ll_crc.h", "stem": "stm32n6xx_ll_crc",
                               "block": "ll_crc_regs", "base": "0x56024C00", "mm": None, "void": False, "prompt": {}}
    swe2.requirements = lambda _ws: {"SWR-001": "The CRC LL driver shall write CRC_IDR.IDR.", "SWR-012": REQ}
    swe2.component_level = lambda _ws: ["SWR-012"]
    swe2._section_files = lambda _ws: {}
    hardware.index = lambda _p: {}
    engine.Store = lambda _ws: SimpleNamespace(latest_baseline=lambda _ph: {})
    iface = {"functions": [{"name": "LL_CRC_Write_IDR", "returns": "void", "operation": "writes IDR", "fields": [],
                            "params": [{"name": "in_data", "type": "uint32_t"}]}],
             "allocation": [{"swr": "SWR-001", "functions": ["LL_CRC_Write_IDR"], "responsibility": "write"}], "calls": []}
    design = {k: "x" for k in ("components", "register_access", "timing_and_error_handling", "memory_and_stack",
                               "concurrency_and_reentrancy", "safety_and_dependencies")} | {
        "decisions": ["d"], "sequences": [{"title": "write", "steps": []}]}
    with tempfile.TemporaryDirectory() as td:
        try:
            files = swe2.render(Path(td), iface, design)
        except (KeyError, TypeError) as exc:
            print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:render needs {type(exc).__name__}:{str(exc)[:80]}")
            return 2
    md = next((t for p, t in files.items() if p.endswith("software_architecture.md")), "")
    row = next((ln for ln in md.splitlines() if ln.startswith("| SWR-012 |")), None)
    if row is None:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:no SWR-012 allocation row")
        return 2
    if REQ in row:
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
