"""RPR-134 (CAPA-128 follow-up for WO-F014-SWE3-CRCHAL-20261103-L27, 2026-11-03): a HAL built on a PROVIDED ST (CMSIS)
LL can reach the registers without the LL - the L27 SWE.3 author wrote `extern volatile uint32_t CRC_registers[]` and
indexed it, and `CRC->DR = word;` compiles too - and nothing deterministic refuses it: with ST's LL the generated LL
test double keeps the device header (CRC_TypeDef, the CRC macro, WRITE_REG), so the greenfield guarantee "a HAL that
bypasses the LL does not build in its unit test" does not hold, and the SWE.3 implementation check has no rule for it.

Scenario (synthetic HAL workspace in a scratch dir): a provided ST-style CRC LL header (__STATIC_INLINE, CRC_TypeDef
*CRCx), a HAL header and a HAL source through the real inspection/implementation.check_implementation of the revision
under test. Symptom: no finding names the direct register access of a HAL that writes CRC->DR, uses WRITE_REG on the
instance or declares its own register array. Control: the same HAL calling only LL_CRC_FeedData32(CRC, ...) gets no
such finding (a noisy check is an error, not ABSENT)."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

SIG = "SWE.3 does not refuse a HAL that accesses the registers directly instead of calling its provided ST (CMSIS) LL"
LL = ("#include \"stm32n6xx.h\"\n__STATIC_INLINE void LL_CRC_FeedData32(CRC_TypeDef *CRCx, uint32_t InData)\n{\n"
      "  WRITE_REG(CRCx->DR, InData);\n}\n")
HAL_H = ("#ifndef STM32N6XX_HAL_CRC_H\n#define STM32N6XX_HAL_CRC_H\n#include <stdint.h>\n#include \"stm32n6xx_ll_crc.h\"\n"
         "void HAL_CRC_Feed(uint32_t w);\n#endif /* STM32N6XX_HAL_CRC_H */\n")
GOOD = "#include \"stm32n6xx_hal_crc.h\"\nvoid HAL_CRC_Feed(uint32_t w)\n{\n    LL_CRC_FeedData32(CRC, w);\n}\n"
BAD = {
    "arrow": "#include \"stm32n6xx_hal_crc.h\"\nvoid HAL_CRC_Feed(uint32_t w)\n{\n    CRC->DR = w;\n}\n",
    "macro": "#include \"stm32n6xx_hal_crc.h\"\nvoid HAL_CRC_Feed(uint32_t w)\n{\n    WRITE_REG(CRC->DR, w);\n}\n",
    "array": ("#include \"stm32n6xx_hal_crc.h\"\nextern volatile uint32_t CRC_registers[];\nvoid HAL_CRC_Feed(uint32_t w)\n"
              "{\n    CRC_registers[0] = w;\n}\n"),
}


def findings(td: Path, name: str, hal_c: str) -> list[str]:
    from forge_factory.inspection.implementation import check_implementation

    ws = td / name
    files = {"software/ll/stm32n6xx_ll_crc.h": LL, "software/hal/stm32n6xx_hal_crc.h": HAL_H,
             "software/hal/stm32n6xx_hal_crc.c": hal_c}
    for rel, text in files.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text)
    (ws / ".forge-run").mkdir()
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL", "peripheral": "crc", "provided": [
        {"path": "software/ll/stm32n6xx_ll_crc.h", "sha256": hashlib.sha256(LL.encode()).hexdigest(),
         "role": "provided_ll_driver", "source_work_order": "WO-RPR133-LL"}]}))
    return check_implementation(ws)["major_findings"]


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        good = findings(Path(td), "good", GOOD)
        bad = {k: findings(Path(td), k, v) for k, v in BAD.items()}
    base = set(good)
    if any("BYPASS" in f or "DIRECT" in f for f in good):
        print(f"REPRODUCER_ERROR:CHECK_NOISY:a HAL calling only the LL is flagged: {good[:3]}")
        return 2
    token = {"arrow": "CRC->", "macro": "WRITE_REG", "array": "CRC_registers"}
    silent = [k for k, f in bad.items() if not any(token[k] in x for x in set(f) - base)]
    if silent:
        print(f"observed: no new finding for {silent}")
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
