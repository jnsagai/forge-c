"""RPR-126 (Fabro run WO-F014-SWE2-CRCHAL-20261103-L26, local line, Omniverse2, CRC HAL order 0014m on run/gen8d,
2026-11-03): the frozen SWE.1 baseline of the CRC HAL carries SWR-018, a spurious timing requirement "every wait is
bounded by HAL_CRC_TIMEOUT_VALUE = 1000 polling iterations", and the SWE.2 author then drew an invented polling loop.
The CRC HAL has no wait (config/factory/peripherals/crc.yaml, RM0486 26.3.3), and its hal_failure_responses already
asks for "every HAL_CRC_ function returns without waiting on a CRC flag". workflow/prompts.py:peripheralize removes
the RCC timing requirement, its 'at most HAL_RCC_TIMEOUT_VALUE polling iterations' example and the
'#define HAL_RCC_TIMEOUT_VALUE 1000U' header line only for a profile with hal.time_base (IWDG). For CRC the generated
SWE.1 HAL prompt therefore demands both "returns without waiting" and a polling bound.

Scenario: the real workflow builder of the revision under test renders the native graph of a HAL work order (layer
HAL, trace profile, LL test double) for the tracked CRC, IWDG and RCC profiles; the SWE.1 author prompt (node
swe1_author) and the SWE.3 HAL author prompt (swe3_hal_author) are read from the graph. Symptom: the CRC SWE.1 prompt
names a polling-iteration bound or a TIMEOUT_VALUE, or the CRC SWE.3 HAL prompt names a TIMEOUT_VALUE. Controls: the
CRC SWE.1 prompt keeps its own no-wait timing requirement; the IWDG SWE.1 prompt still names its update timeout
(HAL_TIMEOUT within timeout_ms) and the RCC SWE.1 prompt still names the 1000-iteration bound. A fix that drops a
waiting HAL's timeout requirement is reported as an error, not as ABSENT."""
import re
import sys

SIG = "the SWE.1 HAL prompt of a no-wait HAL (CRC) demands a polling-iteration timeout bound"


def node_prompt(dot: str, node: str) -> str:
    m = re.search(rf'  {re.escape(node)} \[.*?prompt="((?:\\.|[^"\\])*)"', dot, re.S)
    return m.group(1) if m else ""


def main() -> int:
    from forge_factory.workflow import builder

    def prompts(pid: str) -> tuple[str, str]:
        dot, _ = builder.build("WO-RPR-126", chunk_lines=150, layer="HAL", trace=True, isolation=True, peripheral=pid)
        return node_prompt(dot, "swe1_author"), node_prompt(dot, "swe3_hal_author")

    (crc1, crc3), (iwdg1, _), (rcc1, _) = prompts("crc"), prompts("iwdg"), prompts("rcc")
    if not (crc1 and crc3 and iwdg1 and rcc1):
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:swe1_author/swe3_hal_author prompt not found in the graph")
        return 2
    if "returns without waiting on a CRC flag" not in crc1:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:the CRC SWE.1 prompt lost its own no-wait timing requirement")
        return 2
    if not ("update timeout" in iwdg1 and "HAL_TIMEOUT" in iwdg1 and "timeout_ms" in iwdg1):
        print("REPRODUCER_ERROR:CHECK_LOOSENED:iwdg: the SWE.1 prompt no longer names the update timeout requirement")
        return 2
    if "every wait is bounded by HAL_RCC_TIMEOUT_VALUE = 1000 polling iterations" not in rcc1:
        print("REPRODUCER_ERROR:CHECK_LOOSENED:rcc: the SWE.1 prompt no longer names the 1000-iteration timing bound")
        return 2
    if re.search(r"polling iterations|TIMEOUT_VALUE", crc1) or "TIMEOUT_VALUE" in crc3:
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
