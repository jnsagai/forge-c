"""RPR-041 (r123/r126/r127): HAL unit tests ran on a plain RAM register array; a status flag could never become set
after N polls and the driver's LL call order was invisible, so authors invented write-capture helpers that observed
only their own writes and SWE.4 failed. Symptom: a HAL work order's scaffold gives no way to script readiness and
count polls (a probe test using the LL test double does not build or does not pass)."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SIG = "HAL unit test cannot observe LL polls"
LL = ("#ifndef LLH\n#define LLH\n#include <stdint.h>\n#define LL_RCC_REG_COUNT 4U\n"
      "extern volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];\n"
      "static inline void LL_RCC_HSE_Enable(void)\n{\n  ll_rcc_regs[0] |= 0x10U;\n}\n"
      "static inline uint32_t LL_RCC_HSE_IsReady(void)\n{\n  return ((ll_rcc_regs[1] & 0x10U) != 0U) ? 1U : 0U;\n}\n#endif\n")
HAL_H = ('#ifndef HALH\n#define HALH\n#include <stdint.h>\n#include "stm32n6xx_ll_rcc.h"\n'
         "uint32_t HAL_Wait(uint32_t t);\n#endif\n")
HAL_C = ('#include "stm32n6xx_hal_rcc.h"\nuint32_t HAL_Wait(uint32_t t)\n{\n  uint32_t n = 0U;\n  LL_RCC_HSE_Enable();\n'
         "  while ((n < t) && (LL_RCC_HSE_IsReady() == 0U)) { n++; }\n  return n;\n}\n")
PROBE = ("static void ut_probe(void)\n{\n    ut_reset();\n    ll_fake_return_from(LL_FAKE_LL_RCC_HSE_IsReady, 3U, 1U);\n"
         "    (void)HAL_Wait(10U);\n    CHECK(\"UT-001\", ll_fake_calls(LL_FAKE_LL_RCC_HSE_IsReady) == 3U);\n}\n")


def main() -> int:
    from forge_factory.workflow import scaffold

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "WO" / "workspace"
        for rel, text in {"software/ll/stm32n6xx_ll_rcc.h": LL, "software/hal/stm32n6xx_hal_rcc.h": HAL_H,
                          "software/hal/stm32n6xx_hal_rcc.c": HAL_C,
                          ".forge-run/manifest.json": json.dumps({"layer": "HAL", "hal_unit_isolation": "ll-fake-v1"})}.items():
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            (ws / rel).write_text(text)
        scaffold.scaffold(ws)
        t = ws / scaffold.UNIT_TEST
        src = t.read_text().replace(scaffold.TEST_CASES_MARKER, PROBE + scaffold.TEST_CASES_MARKER)
        t.write_text(src.replace(scaffold.TEST_CALLS_MARKER, "ut_probe();\n    " + scaffold.TEST_CALLS_MARKER))
        incs = [f"-I{ws / d}" for d in ("software/tests/unit/ll_fake", "software/hal", "software/ll") if (ws / d).is_dir()]
        exe = Path(td) / "probe"
        b = subprocess.run(["clang", "-std=c11", *incs, str(t), str(ws / "software/hal/stm32n6xx_hal_rcc.c"), "-o",
                            str(exe)], capture_output=True, text=True)
        ok = b.returncode == 0 and "UT-001 PASS" in subprocess.run([str(exe)], capture_output=True, text=True).stdout
    if not ok:
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
