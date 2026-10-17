"""RPR-024 (r86): run_unit passed a test file that used the same UT id for two checks; the SWE.4 inspector found the
duplicates only after two rework cycles."""
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "host test run accepts duplicate CHECK ids"
H = ("#ifndef STM32N6XX_LL_RCC_H\n#define STM32N6XX_LL_RCC_H\n#include <stdint.h>\n#define LL_RCC_REG_COUNT 1024U\n"
     "extern volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];\n"
     "static inline void LL_RCC_HSI_Enable(void)\n{\n    ll_rcc_regs[0U] |= 8U;\n}\n#endif /* STM32N6XX_LL_RCC_H */\n")
T = ('#include <stdio.h>\n#include <stdint.h>\n#include "stm32n6xx_ll_rcc.h"\nvolatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];\n'
     'static int failures = 0;\n#define CHECK(id, c) do { if (c) { printf("%s PASS\\n", (id)); } else { failures++; } } while (0)\n'
     'int main(void)\n{\n    LL_RCC_HSI_Enable();\n    CHECK("UT-001", (ll_rcc_regs[0] & 8U) != 0U);\n'
     '    CHECK("UT-001", ll_rcc_regs[1] == 0U);\n    return failures;\n}\n')


def main() -> int:
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import tests as TT

    ws = Path(tempfile.mkdtemp(prefix="rpr024-"))
    (ws / ".forge-run").mkdir()
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL"}))
    for rel, txt in {"software/ll/stm32n6xx_ll_rcc.h": H, "software/src/stm32n6xx_ll_rcc.c": '#include "stm32n6xx_ll_rcc.h"\n',
                     "software/tests/unit/test_rcc.c": T}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(txt)
    os.environ.update({"FORGE_MCP_TRUST": "env", "FORGE_WORKSPACE": str(ws), "FORGE_EVENTS_DIR": str(ws / ".ev"),
                       "FORGE_STATE_DIR": str(ws / ".st"), "FORGE_ROLE": "swe4-author", "FORGE_PHASE": "SWE.4"})
    out = sdk.invoke("forge-tests-mcp", next(o for o in TT.OPERATIONS if o.name == "run_unit"), {"coverage": False})
    if out["status"] == "PASS":
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    if not any(i.startswith("DUPLICATE_TEST_ID") for i in out["issues"]):
        print(f"REPRODUCER_ERROR:UNEXPECTED_FAILURE:{out['issues'][:2]}")
        return 2
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
