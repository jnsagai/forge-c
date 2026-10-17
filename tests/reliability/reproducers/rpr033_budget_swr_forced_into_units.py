"""RPR-033 (r113): the SWE.3 trace gate demanded unit refinement of resource-budget SWRs (flash/RAM/stack); the
author invented 'resource units' and edited the generated LL compile unit to satisfy it."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "budget SWR reported NOT_REFINED"
REQS = ("- **SWR-001** When the HSI enable is requested, the RCC driver shall set RCC_CR.HSION.\n"
        "- **SWR-002** The RCC LL driver shall use no more than 4096 bytes of program flash.\n")
ARCH = ('@startuml\ncomponent "RCC_LL" <<SWC>> as SWC_LL\ncomponent "RCC" as RCC\nnote right of SWC_LL\n'
        "Allocated: SWR-001, SWR-002\nend note\nSWC_LL --> RCC : IF-01 regs\n@enduml\n")
UNITS = ("## SWU-LL-01: HSI\n- SWC: SWC_LL\n- Functions: LL_RCC_HSI_Enable\n"
         "- **USPEC-LL-01-01** Set HSION. Traces: SWR-001\n")


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
    if "UNIT:SWR_NOT_REFINED:SWR-002" in f:
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
