"""RPR-018 (r83 DEF-003): the Robot driver keywords compiled only software/hal/*.c, so on an LL work order
'Driver Stack Should Be At Most' failed with 'no call graph produced' and SWR-021 could not be verified."""
import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

SIG = "Robot driver stack keyword finds no call graph for a header-only LL"
LL_H = ("#ifndef STM32N6XX_LL_RCC_H\n#define STM32N6XX_LL_RCC_H\n#include <stdint.h>\n#define LL_RCC_REG_COUNT 1024U\n"
        "extern volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];\n"
        "static inline void LL_RCC_HSI_Enable(void)\n{\n    ll_rcc_regs[0U] |= 8U;\n}\n"
        "#endif /* STM32N6XX_LL_RCC_H */\n")


def main() -> int:
    if not shutil.which("arm-none-eabi-gcc"):
        print("REPRODUCER_ERROR:TOOL_MISSING:arm-none-eabi-gcc")
        return 2
    import forge_factory

    lib_path = Path(forge_factory.__file__).resolve().parents[2] / "sim/stm32n6/ForgeTarget.py"
    spec = importlib.util.spec_from_file_location("ForgeTarget", lib_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ws = Path(tempfile.mkdtemp(prefix="rpr018-"))
    (ws / ".forge-run").mkdir()
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL"}))
    for rel, txt in {"software/ll/stm32n6xx_ll_rcc.h": LL_H,
                     "software/src/stm32n6xx_ll_rcc.c": '#include "stm32n6xx_ll_rcc.h"\n'}.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(txt)
    _, unbounded = mod.ForgeTarget(str(ws))._stack()
    if any("no call graph" in u for u in unbounded):
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
