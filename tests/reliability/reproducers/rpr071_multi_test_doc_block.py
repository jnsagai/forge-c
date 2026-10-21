"""RPR-071 (rc3 IWDG HAL): the SWE.4 author listed six '@test UT-nnn @verifies USPEC-...' lines in one Doxygen block;
the unit-test trace read only the first @test of a block, so UT-002..UT-006 were dropped and USPEC-HAL-01-02..08
reported UT:SPEC_NOT_VERIFIED although the tests tagged them and passed (identical rejection twice -> BLOCKED STUCK)."""
import sys
import tempfile
from pathlib import Path

SIG = "only the first @test of a multi-test doc block is traced"
BLOCK = ("/**\n * @test UT-001 @verifies USPEC-HAL-01-01\n * @test UT-002 @verifies USPEC-HAL-01-02 USPEC-HAL-01-07\n"
         " * @test UT-003 @verifies USPEC-HAL-01-03\n */\nstatic void ut_init(void) {}\n")


def main() -> int:
    from forge_factory.inspection.swtrace import tagged_tests

    with tempfile.TemporaryDirectory() as d:
        ws = Path(d)
        f = ws / "software/tests/unit/test_x.c"
        f.parent.mkdir(parents=True)
        f.write_text(BLOCK)
        got = {t["test"]: t["verifies"] for t in tagged_tests([f], ws)}
    want = {"UT-001": ["USPEC-HAL-01-01"], "UT-002": ["USPEC-HAL-01-02", "USPEC-HAL-01-07"],
            "UT-003": ["USPEC-HAL-01-03"]}
    if got != want:
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
