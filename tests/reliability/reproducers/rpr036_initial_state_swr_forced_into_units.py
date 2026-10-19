"""RPR-036 (r116): 'While no RCC LL driver function has been called after reset, the RCC LL driver shall not write any
RCC register' was required to be refined by a unit-spec item; SWE.3 stopped STUCK on UNIT:SWR_NOT_REFINED:SWR-019."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "initial-state invariant reported NOT_REFINED"
REQS = ("- **SWR-001** When the HSI enable is requested, the RCC driver shall set RCC_CR.HSION.\n"
        "- **SWR-019** While no RCC LL driver function has been called after reset, the RCC LL driver shall not write any "
        "RCC register.\n")
ARCH = ('@startuml\ncomponent "RCC_LL" <<SWC>> as SWC_LL\ncomponent "RCC" as RCC\nnote right of SWC_LL\n'
        "Allocated: SWR-001, SWR-019\nend note\nSWC_LL --> RCC : IF-01 regs\n@enduml\n")
UNITS = "## SWU-LL-01: HSI\n- SWC: SWC_LL\n- Functions: LL_RCC_HSI_Enable\n- **USPEC-LL-01-01** Set HSION. Traces: SWR-001\n"


def main() -> int:
    from forge_factory.inspection import swtrace

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "WO" / "workspace"
        for rel, text in {".forge-run/manifest.json": json.dumps({"layer": "LL"}),
                          "workproducts/SWE.1/software_requirements.md": REQS,
                          "workproducts/SWE.2/architecture_static.puml": ARCH,
                          "workproducts/SWE.3/unit_specifications.md": UNITS}.items():
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            (ws / rel).write_text(text)
        f = swtrace.check_units(ws, render=False, export=False)["major_findings"]
    if any(x.startswith("UNIT:SWR_NOT_REFINED:SWR-019") for x in f):
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
