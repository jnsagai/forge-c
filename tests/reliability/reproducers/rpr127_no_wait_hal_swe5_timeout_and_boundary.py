"""RPR-127 (Fabro run WO-F014-SWE2-CRCHAL-20261103-L26, local line, Omniverse2, CRC HAL order 0014m on run/gen8d,
2026-11-03, follow-up of CAPA-124/126 before the CRC HAL reaches SWE.5): two SWE.5/SWE.6 defects for HALs that are not
RCC.
(1) The SWE.5 author prompt of the CRC HAL (no wait, config/factory/peripherals/crc.yaml) still tells the author, when
no target test exists, to write test_crc_target_timeout.c with "scenario never_ready for the timeout file" and to
report "(timeout paths, measured sizes)"; the SWE.6 test author prompt says "add scenario=never_ready for timeout
behaviour". The CRC has no timeout and its target tests are test_crc_target.c / test_crc_target_errors.c.
(2) The SWE.5 BOUNDARY_INTEGRATION verifier (assurance/target.py integration_categories, verifiers.v_integration)
recognised only the RCC boundary arguments (TIMEOUT_VALUE + 1, (0U), 1000, 1001). A correct CRC HAL integration test
(a word count of 0) and a correct IWDG HAL test (HAL_IWDG_TIMEOUT_MS + 1U) got INTEGRATION_CATEGORY_MISSING:boundary.

Scenario: the real workflow builder of the revision under test renders the native HAL graphs (layer HAL, trace
profile, LL test double) of the tracked CRC and IWDG profiles; the swe5_author and swe6_test_author prompts are read
from the graph. The real v_integration runs on synthetic HAL workspaces in scratch (manifest only, no RM inputs):
CRC with HAL_CRC_Calculate(words, 0U, &crc), IWDG with HAL_IWDG_Init(&cfg, HAL_IWDG_TIMEOUT_MS + 1U). Symptom: a CRC
SWE.5/SWE.6 prompt names the timeout file, the never_ready scenario or timeout paths, or either correct test gets
INTEGRATION_CATEGORY_MISSING:boundary. Controls: the IWDG SWE.5 prompt still names its timeout target file; an RCC
test with HAL_RCC_HSI_Enable(1001U) passes the boundary category; RCC, IWDG and CRC tests without a boundary
argument are still flagged (a loosened check is reported as an error, not as ABSENT)."""
import json
import re
import sys
import tempfile
from pathlib import Path

SIG = "a no-wait HAL's SWE.5/SWE.6 prompts ask for timeout tests, or a correct non-RCC boundary test is not recognised"
MISSING = "INTEGRATION_CATEGORY_MISSING:boundary"

TESTS = {  # peripheral -> (test with a boundary argument, test without one)
    "crc": ("st = HAL_CRC_Calculate(words, 0U, &crc);\nCHECK(\"IT-03\", st == HAL_ERROR);\n",
            "st = HAL_CRC_Calculate(words, 2U, &crc);\nCHECK(\"IT-03\", st == HAL_OK);\n"),
    "iwdg": ("st = HAL_IWDG_Init(&cfg, HAL_IWDG_TIMEOUT_MS + 1U);\nCHECK(\"IT-05\", st == HAL_ERROR);\n",
             "st = HAL_IWDG_Init(&cfg, 10U);\nCHECK(\"IT-05\", st == HAL_OK);\n"),
    "rcc": ("st = HAL_RCC_HSI_Enable(1001U);\nCHECK(\"IT-05\", st == HAL_ERROR);\n",
            "st = HAL_RCC_HSI_Enable(10U);\nCHECK(\"IT-05\", st == HAL_OK);\n"),
}


def node_prompt(dot: str, node: str) -> str:
    m = re.search(rf'  {re.escape(node)} \[.*?prompt="((?:\\.|[^"\\])*)"', dot, re.S)
    return m.group(1) if m else ""


def main() -> int:
    from forge_factory.assurance import verifiers
    from forge_factory.workflow import builder

    def prompts(pid: str) -> tuple[str, str]:
        dot, _ = builder.build("WO-RPR-127", chunk_lines=150, layer="HAL", trace=True, isolation=True, peripheral=pid)
        return node_prompt(dot, "swe5_author"), node_prompt(dot, "swe6_test_author")

    (crc5, crc6), (iwdg5, _) = prompts("crc"), prompts("iwdg")
    if not (crc5 and crc6 and iwdg5):
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:swe5_author/swe6_test_author prompt not found in the graph")
        return 2
    if "test_iwdg_target_timeout.c" not in iwdg5:
        print("REPRODUCER_ERROR:CHECK_LOOSENED:iwdg: the SWE.5 prompt no longer names its timeout target file")
        return 2
    prompt_symptom = bool(re.search(r"_timeout\.c|never_ready|timeout paths", crc5 + crc6))

    with tempfile.TemporaryDirectory() as td:
        def boundary_missing(pid: str, text: str, n: int) -> bool:
            ws = Path(td) / f"{pid}-{n}"
            (ws / ".forge-run").mkdir(parents=True)
            (ws / ".forge-run/manifest.json").write_text(json.dumps({"peripheral": pid, "layer": "HAL"}))
            (ws / "software/tests/integration").mkdir(parents=True)
            (ws / f"software/tests/integration/test_{pid}_integration.c").write_text(text)
            return MISSING in verifiers.v_integration(ws)["findings"]

        res = {(pid, n): boundary_missing(pid, TESTS[pid][n], n) for pid in TESTS for n in (0, 1)}
    if res[("rcc", 0)]:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:rcc: the RCC boundary argument 1001U is not recognised")
        return 2
    loosened = [pid for pid in TESTS if not res[(pid, 1)]]
    if loosened:
        print(f"REPRODUCER_ERROR:CHECK_LOOSENED:{','.join(loosened)}: a test without a boundary argument passes")
        return 2
    if prompt_symptom or res[("crc", 0)] or res[("iwdg", 0)]:
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
