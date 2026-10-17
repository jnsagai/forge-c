"""RPR-029 (r109): the SWE.2 owner-trace gate wrote matrix 1 into traceability/, a folder of the frozen SWE.1
baseline; SWE.1 became stale and every SWE.2 freeze failed with UPSTREAM_NOT_FROZEN:SWE.1."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "trace matrix written into the frozen SWE.1 baseline"
REQS = "".join(f"- **SWR-{i:03d}** When the HSI enable is requested, the RCC driver shall set RCC_CR.HSION.\n"
               f"  - Source: RM0486 p.480\n" for i in range(1, 4))
ARCH = """@startuml
component "RCC_LL\\nstm32n6xx_ll_rcc" <<SWC>> as SWC_LL
component "RCC" as RCC
note right of SWC_LL
Allocated: SWR-001, SWR-002, SWR-003
end note
SWC_LL --> RCC : IF-01 register access
@enduml
"""


def main() -> int:
    from forge_factory.inspection import swtrace
    from forge_factory.inspection.engine import InspectionError, Store
    from forge_factory.layer import TRACE_PROFILE

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "WO" / "workspace"
        files = {".forge-run/manifest.json": json.dumps({"layer": "LL", "trace_profile": TRACE_PROFILE}),
                 "workproducts/SWE.1/software_requirements.md": "# Software requirements\n" + REQS,
                 "traceability/requirements_to_tests.csv": "requirement_id,test_id,test_file\nSWR-001,UT-001,t.c\n",
                 "workproducts/SWE.2/architecture_static.puml": ARCH,
                 "workproducts/SWE.2/software_architecture.md": "# Software architecture\n"}
        for rel, text in files.items():
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            (ws / rel).write_text(text)
        st = Store(ws)
        st.freeze("SWE.1", "swe1-author")
        swtrace.check_phase(ws, "SWE.2")
        try:
            st.freeze("SWE.2", "swe2-author")
        except InspectionError as exc:
            if "UPSTREAM_NOT_FROZEN:SWE.1" in str(exc):
                print(f"SYMPTOM_PRESENT:{SIG}")
                return 1
            raise
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
