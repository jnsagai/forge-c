"""RPR-047 (r146, r144): the generated LL test double had no documented way to preset the state a state query reads,
so SWE.4 authors called the internal bit helper with magic indices (r146 UT-009: ll_fake_set_bit(0U, 1U)) and the
inspector rejected the tests in every rework cycle; run_unit accepted the internal calls."""
import subprocess
import sys
import tempfile
from pathlib import Path

SIG = "LL test double has no state preset and accepts internal helper calls"
LL = ("#ifndef LLH\n#define LLH\n#include <stdint.h>\n#define LL_RCC_REG_COUNT 4U\n#define LL_RCC_ENR_OFFSET 0x8U\n"
      "#define LL_RCC_ENR_X_MSK 0x20U\nextern volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];\n"
      "static inline void LL_RCC_X_Enable(void)\n{\n  ll_rcc_regs[LL_RCC_ENR_OFFSET / 4U] |= LL_RCC_ENR_X_MSK;\n}\n"
      "static inline uint32_t LL_RCC_X_IsEnabled(void)\n{\n"
      "  return ((ll_rcc_regs[LL_RCC_ENR_OFFSET / 4U] & LL_RCC_ENR_X_MSK) != 0U) ? 1U : 0U;\n}\n#endif\n")
TEST = ('#include <stdio.h>\n#define LL_FAKE_IMPLEMENTATION\n#include "stm32n6xx_ll_rcc.h"\n'
        "int main(void)\n{\n    ll_fake_reset();\n    (void)ll_fake_set_state(LL_FAKE_LL_RCC_X_IsEnabled, 1U);\n"
        '    printf("%s\\n", LL_RCC_X_IsEnabled() == 1U ? "PRESET" : "NOT_PRESET");\n    return 0;\n}\n')
R146 = "static void ut_009(void)\n{\n    ut_reset();\n    ll_fake_set_bit(0U, 1U);\n}\n"


def main() -> int:
    from forge_factory.workflow import ll_fake

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "stm32n6xx_ll_rcc.h").write_text(ll_fake.generate(LL))
        (d / "t.c").write_text(TEST)
        b = subprocess.run(["clang", "-std=c11", "-Werror=implicit-function-declaration", f"-I{d}", str(d / "t.c"),
                            "-o", str(d / "t")], capture_output=True, text=True)
        out = subprocess.run([str(d / "t")], capture_output=True, text=True).stdout if b.returncode == 0 else ""
    refused = bool(getattr(ll_fake, "internal_calls", lambda _s: [])(R146))
    if "PRESET" not in out.split() or not refused:
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
