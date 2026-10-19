"""RPR-050 (r103 SWE3-02, r159 SWE3-01): the SWE.3 inspector was never told that the register block is the extern
ll_rcc_regs array placed by the linker, failed the mandated design ("no RCC base 0x56028000 in the code"), and the LL
author answered with an authored integer-to-pointer address unit that the LL implementation gate accepted."""
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "SWE.3 inspector not told the register-block design and LL gate accepts an authored compile unit"


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        os.environ["FORGE_STATE_DIR"] = str(Path(td) / "state")
        os.environ["FORGE_EVENTS_DIR"] = str(Path(td) / "state/events")
        from forge_factory import layer as LY
        from forge_factory.inspection.implementation import check_implementation
        from forge_factory.workflow import prompts
        from forge_factory.workflow.builder import build

        build("WO-RPR050", layer="LL", chunk_lines=150)
        told = "integer-to-pointer" in prompts.inspector_prompt("SWE.3")
        ws = Path(td) / "ws"
        (ws / ".forge-run").mkdir(parents=True)
        (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL", "provided": []}))
        (ws / "workproducts/SWE.2").mkdir(parents=True)
        (ws / "workproducts/SWE.2/software_architecture.md").write_text(
            "# Software architecture\n## Requirement allocation\n| SWR | Function |\n|---|---|\n"
            "| SWR-001 | LL_RCC_HSI_Enable |\n")
        (ws / "software/ll").mkdir(parents=True)
        (ws / LY.LL_HEADER).write_text(
            "#ifndef STM32N6XX_LL_RCC_H\n#define STM32N6XX_LL_RCC_H\n#include <stdint.h>\n"
            "extern volatile uint32_t ll_rcc_regs[1024U];\n"
            "static inline void LL_RCC_HSI_Enable(void)\n{\n    ll_rcc_regs[0U] |= 1U;\n}\n#endif\n")
        (ws / LY.LL_TU).parent.mkdir(parents=True)
        (ws / LY.LL_TU).write_text(LY.LL_TU_TEXT)
        (ws / "software/src/stm32n6xx_ll_rcc_addr.c").write_text(
            "#include <stdint.h>\nvolatile uint32_t *LL_RCC_MemPtr(uintptr_t a) { return (volatile uint32_t *)a; }\n")
        accepted = not any("stm32n6xx_ll_rcc_addr.c" in f for f in check_implementation(ws)["major_findings"])
    if not told or accepted:
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
