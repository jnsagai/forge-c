"""RPR-044 (r135): with the generated LL test double, LL_RCC_ADC12_IsEnabled() returned 0U after LL_RCC_ADC12_Enable();
the SWE.4 authors declared two TEST defects to work around it and SWE.3 later ran out of turns in the rework loop."""
import subprocess
import sys
import tempfile
from pathlib import Path

SIG = "state query of the LL test double ignores Enable"
LL = ("#ifndef LLH\n#define LLH\n#include <stdint.h>\n#define LL_RCC_REG_COUNT 4U\n#define LL_RCC_ENR_OFFSET 0x8U\n"
      "#define LL_RCC_ENR_X_MSK 0x20U\nextern volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];\n"
      "static inline void LL_RCC_X_Enable(void)\n{\n  ll_rcc_regs[LL_RCC_ENR_OFFSET / 4U] |= LL_RCC_ENR_X_MSK;\n}\n"
      "static inline uint32_t LL_RCC_X_IsEnabled(void)\n{\n"
      "  return ((ll_rcc_regs[LL_RCC_ENR_OFFSET / 4U] & LL_RCC_ENR_X_MSK) != 0U) ? 1U : 0U;\n}\n#endif\n")
TEST = ('#include <stdio.h>\n#define LL_FAKE_IMPLEMENTATION\n#include "stm32n6xx_ll_rcc.h"\n'
        "int main(void)\n{\n    ll_fake_reset();\n    LL_RCC_X_Enable();\n"
        '    printf("%s\\n", LL_RCC_X_IsEnabled() == 1U ? "ENABLED" : "NOT_ENABLED");\n    return 0;\n}\n')


def main() -> int:
    from forge_factory.workflow import ll_fake

    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        (d / "stm32n6xx_ll_rcc.h").write_text(ll_fake.generate(LL))
        (d / "t.c").write_text(TEST)
        b = subprocess.run(["clang", "-std=c11", f"-I{d}", str(d / "t.c"), "-o", str(d / "t")], capture_output=True,
                           text=True)
        out = subprocess.run([str(d / "t")], capture_output=True, text=True).stdout if b.returncode == 0 else ""
    if "ENABLED" not in out.split():
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
