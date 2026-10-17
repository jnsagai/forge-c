"""RPR-028 (r108): the SWE.2 author allocated all SWRs in the architecture diagram, wrapping the 'Allocated:' list
over several note lines; the owner-trace check read only the first line and rejected SWE.2 twice (STUCK)."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "multi-line SWC allocation note read partially"
REQS = "".join(f"- **SWR-{i:03d}** The RCC driver shall set RCC_CR.HSION.\n" for i in range(1, 10))
ARCH = """@startuml
component "RCC_LL" <<SWC>> as SWC_LL
component "RCC" as RCC
note right of SWC_LL
Allocated: SWR-001, SWR-002, SWR-003,
SWR-004, SWR-005, SWR-006,
SWR-007, SWR-008, SWR-009
Header-only: stm32n6xx_ll_rcc.h
end note
SWC_LL --> RCC : IF-01 register access
@enduml
"""


def main() -> int:
    from forge_factory.inspection import swtrace

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "WO" / "workspace"
        for rel, text in ((".forge-run/manifest.json", json.dumps({"layer": "LL"})),
                          ("workproducts/SWE.1/software_requirements.md", REQS),
                          ("workproducts/SWE.2/architecture_static.puml", ARCH)):
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            (ws / rel).write_text(text)
        f = swtrace.check_architecture_model(ws)["major_findings"]
    if any(x.startswith("ARCH:SWR_NOT_ALLOCATED") for x in f):
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
