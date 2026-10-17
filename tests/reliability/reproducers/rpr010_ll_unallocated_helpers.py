"""RPR-010 (r81): the LL implementation check accepted unallocated helpers, HAL code and waiting loops in the LL
header (LL_RCC_*_WaitReady on HAL_RCC_PollSet), which drew SWE.5/6 tests on unrequired, inverted functions."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "LL implementation check accepts unallocated helpers and loops"


def main() -> int:
    from forge_factory.inspection.implementation import check_implementation

    ws = Path(tempfile.mkdtemp(prefix="rpr010-"))
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL", "provided": []}))
    (ws / "workproducts/SWE.2").mkdir(parents=True)
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(
        "# Software architecture\n## Requirement allocation\n| SWR | Function |\n|---|---|\n"
        "| SWR-001 | LL_RCC_HSI_IsReady |\n")
    (ws / "software/ll").mkdir(parents=True)
    (ws / "software/ll/stm32n6xx_ll_rcc.h").write_text(
        "#ifndef STM32N6XX_LL_RCC_H\n#define STM32N6XX_LL_RCC_H\n#include <stdint.h>\n"
        "extern volatile uint32_t ll_rcc_regs[1024U];\n"
        "static inline uint32_t LL_RCC_HSI_IsReady(void)\n{\n    return ((ll_rcc_regs[1U] & 2U) != 0U) ? 1U : 0U;\n}\n"
        "static inline uint32_t HAL_RCC_PollSet(uint32_t t)\n{\n    uint32_t n = 0U;\n"
        "    while ((ll_rcc_regs[1U] == 0U) && (n < t)) { n++; }\n    return n;\n}\n"
        "static inline uint32_t LL_RCC_HSI_WaitReady(uint32_t t)\n{\n    return HAL_RCC_PollSet(t);\n}\n"
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
