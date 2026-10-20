"""RPR-067 (h004): the IWDG HAL v2 bounds its wait with the external time base HAL_GetTick; the Robot stack measurement
rejected the call ('calls function outside the driver: HAL_GetTick') and SWR-012 (stack <= 128 B) stayed unverified."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "driver stack unbounded by the HAL's external time base"
HAL = ("#include <stdint.h>\nuint32_t HAL_GetTick(void);\nuint32_t HAL_IWDG_Wait(uint32_t timeout_ms);\n"
       "uint32_t HAL_IWDG_Wait(uint32_t timeout_ms)\n{\n    uint32_t start = HAL_GetTick();\n"
       "    while ((HAL_GetTick() - start) < timeout_ms)\n    {\n    }\n    return 0U;\n}\n")


def main() -> int:
    from forge_factory.common import REPO_ROOT

    sys.path.insert(0, str(REPO_ROOT / "factory/sim/stm32n6"))
    from ForgeTarget import ForgeTarget

    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / "software/hal").mkdir(parents=True)
        (ws / "software/ll").mkdir(parents=True)
        (ws / "software/hal/stm32n6xx_hal_iwdg.c").write_text(HAL)
        (ws / ".forge-run").mkdir()
        (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL", "peripheral": "iwdg"}))
        try:
            stack = ForgeTarget(str(ws)).driver_stack_should_be_at_most(128)
        except AssertionError as exc:
            print(f"stack: {exc}")
            stack = None
    if stack is None:
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
