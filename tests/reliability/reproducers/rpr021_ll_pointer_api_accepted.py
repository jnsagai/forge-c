"""RPR-021 (r84): the LL implementation check accepted a header that dropped the generated ll_rcc_regs block for a
pointer API (as the LL example scope text demanded), so SWE.2 and SWE.3 contradicted each other until the upstream
loop budget was exhausted."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "LL check accepts a pointer API without the generated register block"


def main() -> int:
    from forge_factory.inspection.implementation import check_implementation

    ws = Path(tempfile.mkdtemp(prefix="rpr021-"))
    (ws / ".forge-run").mkdir()
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL"}))
    (ws / "workproducts/SWE.2").mkdir(parents=True)
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(
        "# A\n## Requirement allocation\n| SWR | Function |\n|---|---|\n| SWR-001 | LL_RCC_HSI_Enable |\n")
    (ws / "software/ll").mkdir(parents=True)
    (ws / "software/ll/stm32n6xx_ll_rcc.h").write_text(
        "#ifndef STM32N6XX_LL_RCC_H\n#define STM32N6XX_LL_RCC_H\n#include <stdint.h>\n"
        "static inline void LL_RCC_HSI_Enable(volatile uint32_t *rcc)\n{\n    rcc[0U] |= 8U;\n}\n"
        "#endif /* STM32N6XX_LL_RCC_H */\n")
    if check_implementation(ws)["verdict"] == "PASS":
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
