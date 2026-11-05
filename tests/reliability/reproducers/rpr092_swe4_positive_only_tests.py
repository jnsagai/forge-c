"""RPR-092 (Fabro run WO-F014-SWE4-IWDG-20261101-L1, Omniverse2, 2026-11-01): structured SWE.4 for IWDG LL resumed from
WO-F014-SWE3-IWDG-20261101-L1. Every structured test checked only the single case value of its register-effect case; the
report labelled all 11 tests 'positive' and the inspector failed SWE4-02 (no negative, boundary or error tests; e.g.
LL_IWDG_SetPrescaler checked only prescaler value 5, not the 4-bit field extremes).

Scenario: a structured SWE.4 test of a value-taking LL function (LL_CRC_Write_IDR(uint32_t)) that checks one case value
only, validated by the real swe4.validate_test (the harness compile and the identity/spec lookups are stubbed: they are
not part of the symptom). Symptom: the test is accepted."""
import sys
import tempfile
from pathlib import Path

SIG = "a structured SWE.4 test of a value-taking function that checks only the single case value is accepted"
CODE = ("/** @test UT-001 @verifies USPEC-LL-01-01 */\nstatic void ut_ut_001(void)\n{\n    ut_reset_regs();\n"
        "    LL_CRC_Write_IDR(0xA5A5A5A5U);\n    CHECK(\"UT-001\", (ll_crc_regs[LL_CRC_IDR_OFFSET / 4U] & LL_CRC_IDR_IDR_MSK) "
        "== 0xA5A5A5A5U);\n}")


def main() -> int:
    from forge_factory.lrtx import swe3, swe4
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        hdr = ws / "stm32n6xx_ll_crc.h"
        hdr.write_text("#define LL_CRC_IDR_OFFSET 0x04U\n#define LL_CRC_IDR_IDR_MSK 0xFFFFFFFFU\n")
        swe3._ident = lambda _ws: {"block": "ll_crc_regs", "pfx": "CRC"}
        swe3._header = lambda _ws: hdr
        swe4._unit_specs = lambda _ws, _u: [{"id": "USPEC-LL-01-01", "behaviour": "writes IDR", "traces": ["SWR-001"]}]
        swe4._compile_test = lambda *_a: []
        c = {"ut": "UT-001", "swr": "SWR-001", "statement": "The driver shall write the 32-bit value to CRC_IDR.IDR.",
             "effects": [{"case": "WRITE_IDR", "swr": "SWR-001", "register": "CRC_IDR", "field": "IDR", "op": "write",
                          "value": "0xA5A5A5A5"}],
             "unit": {"id": "SWU-LL-01", "swrs": ["SWR-001"],
                      "function": {"name": "LL_CRC_Write_IDR", "returns": "void", "fields": ["CRC_IDR.IDR"],
                                   "params": [{"name": "in_data", "type": "uint32_t"}]}}}
        errs = swe4.validate_test(ws, {"code": CODE}, c)
    if errs:
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
