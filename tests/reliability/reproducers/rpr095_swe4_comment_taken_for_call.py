"""RPR-095 (Fabro run WO-F014-SWE4-OBL-20261101-L3, Omniverse2, 2026-11-01): CRC IDR greenfield SWE.4. The structured
test of UT-002 labelled its checks in comments ("positive: the full 32-bit IDR is read back unchanged (all bits set)");
swe4.validate_test took "unchanged (" for a call and rejected every repair (LRTX_REPAIR_STUCK).

Scenario: a structured SWE.4 test of LL_CRC_Read_IDR whose code is valid and whose comment holds a word before a
parenthesis, through the real swe4.validate_test (compile and identity/spec lookups stubbed: not part of the symptom).
Symptom: the comment word is reported as a call."""
import sys
import tempfile
from pathlib import Path

SIG = "a word before a parenthesis in a comment of a structured SWE.4 test is reported as a call"
CODE = ("/** @test UT-002 @verifies USPEC-LL-01-01 */\nstatic void ut_ut_002(void)\n{\n    uint32_t r_set;\n"
        "    /* positive: the full 32-bit IDR is read back unchanged (all bits set), no bit masking */\n"
        "    ut_reset_regs();\n    ll_crc_regs[LL_CRC_IDR_OFFSET / 4U] = LL_CRC_IDR_IDR_MSK;\n"
        "    r_set = LL_CRC_Read_IDR();\n    CHECK(\"UT-002\", r_set == LL_CRC_IDR_IDR_MSK);\n}")


def main() -> int:
    from forge_factory.lrtx import swe3, swe4
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        hdr = ws / "stm32n6xx_ll_crc.h"
        hdr.write_text("#define LL_CRC_IDR_OFFSET 0x04U\n#define LL_CRC_IDR_IDR_MSK 0xFFFFFFFFU\n")
        swe3._ident = lambda _ws: {"block": "ll_crc_regs", "pfx": "CRC"}
        swe3._header = lambda _ws: hdr
        swe4._unit_specs = lambda _ws, _u: [{"id": "USPEC-LL-01-01", "behaviour": "reads IDR", "traces": ["SWR-002"]}]
        swe4._compile_test = lambda *_a: []
        c = {"ut": "UT-002", "swr": "SWR-002", "statement": "The driver shall return CRC_IDR.IDR.",
             "effects": [{"case": "READ_IDR", "swr": "SWR-002", "register": "CRC_IDR", "field": "IDR", "op": "no_write"}],
             "unit": {"id": "SWU-LL-01", "swrs": ["SWR-002"],
                      "function": {"name": "LL_CRC_Read_IDR", "returns": "uint32_t", "fields": ["CRC_IDR.IDR"], "params": []}}}
        errs = swe4.validate_test(ws, {"code": CODE, "kinds": ["positive"]}, c)
    if any("call to unchanged" in e for e in errs):
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    if errs:
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:{errs[0][:120]}")
        return 2
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
