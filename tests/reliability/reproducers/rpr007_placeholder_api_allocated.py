"""RPR-007 (r80): the SWE.2 architecture check accepted a placeholder API (LL_RCC_<Peripheral>_Enable) in the
requirement allocation table, so peripheral requirements could pass SWE.3 without any concrete function."""
import sys
import tempfile
from pathlib import Path

SIG = "architecture check accepts a placeholder API in the allocation table"


def main() -> int:
    from forge_factory.inspection.architecture import check_architecture

    ws = Path(tempfile.mkdtemp(prefix="rpr007-"))
    (ws / "workproducts/SWE.2").mkdir(parents=True)
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(
        "# Software architecture\n## Requirement allocation table\n| SWR | Function |\n|---|---|\n"
        "| SWR-001 | `LL_RCC_<Peripheral>_Enable` |\n")
    findings = check_architecture(ws)["major_findings"]
    if not any("PLACEHOLDER" in f for f in findings):
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
