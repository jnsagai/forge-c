"""RPR-015 (r83): the header-only LL compiled to an empty unit, so measure_elf/stack_usage reported 0 bytes and 0
functions; SWE.3 inspection failed SWE3-05 (resource budgets not really measured)."""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

SIG = "LL size and stack measured as 0 bytes / 0 functions"
LL_H = ("#ifndef STM32N6XX_LL_RCC_H\n#define STM32N6XX_LL_RCC_H\n#include <stdint.h>\n#define LL_RCC_REG_COUNT 1024U\n"
        "extern volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];\n"
        "static inline void LL_RCC_HSI_Enable(void)\n{\n    ll_rcc_regs[0U] |= 8U;\n}\n"
        "#endif /* STM32N6XX_LL_RCC_H */\n")


def main() -> int:
    if not shutil.which("arm-none-eabi-gcc"):
        print("REPRODUCER_ERROR:TOOL_MISSING:arm-none-eabi-gcc")
        return 2
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import build as B

    ws = Path(tempfile.mkdtemp(prefix="rpr015-"))
    (ws / ".forge-run").mkdir()
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL"}))
    for rel, txt in {"software/ll/stm32n6xx_ll_rcc.h": LL_H,
                     "software/src/stm32n6xx_ll_rcc.c": '#include "stm32n6xx_ll_rcc.h"\n'}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(txt)
    os.environ.update({"FORGE_MCP_TRUST": "env", "FORGE_WORKSPACE": str(ws), "FORGE_EVENTS_DIR": str(ws / ".ev"),
                       "FORGE_STATE_DIR": str(ws / ".st"), "FORGE_ROLE": "swe3-author", "FORGE_PHASE": "SWE.3"})
    op = {o.name: o for o in B.OPERATIONS}
    if sdk.invoke("forge-build-mcp", op["compile"], {"profile": "target-cm55-gcc"})["status"] != "PASS":
        print("REPRODUCER_ERROR:COMPILE_FAILED")
        return 2
    size = sdk.invoke("forge-build-mcp", op["measure_elf"], {"profile": "target-cm55-gcc"})
    if size["metrics"]["flash_bytes"] == 0:
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
