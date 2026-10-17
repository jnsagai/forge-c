"""RPR-012 (r82): the SWE.2 Interfaces section listed LL_RCC_MSI/LSI/LSE/PLLx_IsReady that the allocation table and
the code never had; the architecture check did not compare Interfaces with the allocation (SWE3-01, DEF-001)."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "architecture check accepts interfaces missing from the allocation"


def main() -> int:
    from forge_factory.inspection.architecture import check_architecture

    ws = Path(tempfile.mkdtemp(prefix="rpr012-"))
    (ws / ".forge-run").mkdir(parents=True)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL"}))
    (ws / "workproducts/SWE.2").mkdir(parents=True)
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(
        "# A\n## Components\n- LL\n## Interfaces\n- LL_RCC_HSI_IsReady\n- LL_RCC_MSI_IsReady\n"
        "## Requirement allocation\n| SWR | Function |\n|---|---|\n| SWR-001 | LL_RCC_HSI_IsReady |\n")
    if not any("INTERFACE_NOT_ALLOCATED" in f for f in check_architecture(ws)["major_findings"]):
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
