"""RPR-065 (b007): the Robot driver measurements (flash, static RAM, stack) built only HAL sources and the factory LL
measurement unit; a header-only CMSIS delivery (ST LL, __STATIC_INLINE) built nothing - the stack keyword failed
('no call graph produced') and the flash/RAM keywords measured 0 B and passed vacuously (DEF-004/DEF-005)."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "Robot driver measurement builds nothing for a header-only delivery"
HDR = ("#include <stdint.h>\n#define __STATIC_INLINE static inline\n"
       "__STATIC_INLINE uint32_t LL_X_Get(uint32_t v)\n{\n    return v ^ 0x5AU;\n}\n")


def main() -> int:
    from forge_factory.common import REPO_ROOT

    sys.path.insert(0, str(REPO_ROOT / "factory/sim/stm32n6"))
    from ForgeTarget import ForgeTarget

    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        (ws / "software/ll").mkdir(parents=True)
        (ws / ".forge-run/delivery").mkdir(parents=True)
        (ws / "software/ll/ll_x.h").write_text(HDR)
        (ws / ".forge-run/delivery/scope.json").write_text(json.dumps({"functions": [{"name": "LL_X_Get"}]}))
        (ws / ".forge-run/manifest.json").write_text(json.dumps({
            "layer": "LL", "code_mode": "FROZEN", "delivered": [{"path": "software/ll/ll_x.h", "role": "delivered_code"}],
            "delivery": {"code_mode": "FROZEN", "build": {"style": "cmsis", "defines": [], "secure": False}}}))
        lib = ForgeTarget(str(ws))
        try:
            flash = lib.driver_flash_size_should_be_at_most(4096)
            stack = lib.driver_stack_should_be_at_most(128)
        except AssertionError as exc:
            print(f"measurement: {exc}")
            flash = stack = None
    if not flash or stack is None:
        print(f"flash={flash} stack={stack}")
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
