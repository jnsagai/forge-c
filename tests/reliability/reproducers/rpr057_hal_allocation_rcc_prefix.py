"""RPR-057 (h001): on an IWDG HAL work order the SWE.3 implementation check read the SWE.2 allocation table with the
RCC prefix (HAL_RCC_) and found no allocated HAL function; SWE.3 was BLOCKED (NO_ALLOCATED_HAL_FUNCTIONS_IN_SWE2)."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "HAL allocation read with the RCC prefix on a non-RCC work order"
ARCH = ("# A\n## Requirement allocation table\n| SWR | SWC | Function | Note |\n| --- | --- | --- | --- |\n"
        "| SWR-002 | SWC_HAL | HAL_IWDG_Init | init |\n| SWR-005 | SWC_HAL | HAL_IWDG_Refresh | refresh |\n")


def main() -> int:
    from forge_factory.inspection.implementation import allocated_functions

    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / ".forge-run").mkdir()
        (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL", "peripheral": "iwdg"}))
        (ws / "workproducts/SWE.2").mkdir(parents=True)
        (ws / "workproducts/SWE.2/software_architecture.md").write_text(ARCH)
        found = allocated_functions(ws)
    if found != ["HAL_IWDG_Init", "HAL_IWDG_Refresh"]:
        print(f"allocated: {found}")
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
