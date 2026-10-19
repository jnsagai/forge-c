"""RPR-023 (r85): a requirement traced to its Robot test with test_id = its SWR id (CAPA-020) produced a ReqIF test
object with the requirement's xs:ID; the XSD rejected the export and SWE.1 could not freeze."""
import sys
import tempfile
from pathlib import Path

SIG = "ReqIF export duplicates xs:ID for a test named like its requirement"


def main() -> int:
    from forge_factory.inspection.reqif_export import export

    ws = Path(tempfile.mkdtemp(prefix="rpr023-"))
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-001** When the HSI enable function is called, the RCC LL driver shall set RCC_CR.HSION.\n"
        "  - Source: RM0486 p.479\n"
        "- **SWR-019** The RCC LL driver shall use at most 4096 bytes of flash.\n  - Source: work-order budget\n")
    (ws / "traceability").mkdir()
    (ws / "traceability/requirements_to_tests.csv").write_text(
        "requirement_id,test_id,test_file\nSWR-001,UT-001,software/tests/unit/test_rcc.c\n"
        "SWR-019,SWR-019,software/tests/software/test_rcc_requirements.robot\n")
    if export(ws)["verdict"] != "PASS":
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
