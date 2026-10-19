"""RPR-014 (r82): report_defect accepted product code (the LL header) as a test file; the anti-bending gate then
rejected every correct fix of the header as DEFECT_TEST_CHANGED and SWE.3 blocked."""
import sys
import tempfile
from pathlib import Path

SIG = "report_defect accepts product code as a cited test file"


def main() -> int:
    from forge_factory.inspection import defects as D

    ws = Path(tempfile.mkdtemp(prefix="rpr014-"))
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-001** When the HSI enable function is called, the RCC LL driver shall set RCC_CR.HSION.\n")
    (ws / "software/ll").mkdir(parents=True)
    (ws / "software/ll/stm32n6xx_ll_rcc.h").write_text("x\n")
    try:
        D.report(ws, detected_phase="SWE.3", reported_by="swe3-inspector", kind="ARCHITECTURE", summary="s",
                 requirement_ids=["SWR-001"], test_files=["software/ll/stm32n6xx_ll_rcc.h"], evidence_refs=[],
                 requirement_quote="the RCC LL driver shall set RCC_CR.HSION")
    except D.DefectError as exc:
        if "TEST_FILES_MUST_BE_TESTS" in str(exc):
            print("SYMPTOM_ABSENT")
            return 0
        raise
    print(f"SYMPTOM_PRESENT:{SIG}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
