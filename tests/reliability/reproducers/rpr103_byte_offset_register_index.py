"""RPR-103 (Fabro run WO-F014-SWE5-IWDG-20261101-L5, Omniverse2, 2026-11-02): the structured SWE.5 integration test
indexed the register block by the byte offset (ll_iwdg_regs[LL_IWDG_PR_OFFSET]); it passed validation, failed on correct
code, and the triage filed a wrong CODE defect against SWE.3 (DEF-001).

Scenario: an integration test file using block[LL_IWDG_PR_OFFSET], through the real swe5.validate_file (the header and
interface lookups are stubbed: not part of the symptom). Symptom: the file is accepted without an offset finding."""
import sys
import tempfile
from pathlib import Path

SIG = "a structured test indexing the register block by a byte offset passes validation"
CODE = ('/** @file test_iwdg_integration.c */\n/** @test IT-001 @verifies IF-01 SWC_LL */\nint main(void) {\n'
        '  unsigned failures = 0U;\n  CHECK("IT-001", (ll_iwdg_regs[LL_IWDG_PR_OFFSET] & LL_IWDG_PR_PR_MSK) == 5U);\n'
        '  return (failures == 0U) ? 0 : 1;\n}\n')


def main() -> int:
    from forge_factory.lrtx import swe3, swe5
    with tempfile.TemporaryDirectory() as td:
        hdr = Path(td) / "stm32n6xx_ll_iwdg.h"
        hdr.write_text("#define LL_IWDG_PR_OFFSET 0x04U\n#define LL_IWDG_PR_PR_MSK 0xFU\n")
        swe5._p = lambda _ws: {"pfx": "IWDG", "block": "ll_iwdg_regs", "header": "stm32n6xx_ll_iwdg.h", "id": "iwdg",
                               "fn": "LL_IWDG_", "prompt": {}}
        swe3._header = lambda _ws: hdr
        swe3.interfaces = lambda _ws: {"functions": []}
        swe5.interface_ids = lambda _ws: ["IF-01"]
        errs = swe5.validate_file(Path(td), "integration", {"code": CODE})
    if any("byte offset" in e for e in errs):
        print("SYMPTOM_ABSENT")
        return 0
    print(f"SYMPTOM_PRESENT:{SIG}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
