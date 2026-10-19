"""RPR-038 (r119): the frozen SWE.2 architecture document defined per-function interfaces IF-01..IF-18 in its interface
table and the static diagram IF-19/IF-20; integration tests citing IF-01 were rejected as UNKNOWN_ARCH_REF twice and
SWE.5 stopped STUCK."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "documented interface rejected as unknown architecture element"
ARCH = ('@startuml\ncomponent "RCC_LL" <<SWC>> as SWC_LL\ncomponent "RCC" as RCC\nnote right of SWC_LL\n'
        "Allocated: SWR-001\nend note\nSWC_LL --> RCC : IF-19 register access\n@enduml\n")
DOC = "## Interfaces\n\n| Id | Function | Register |\n|---|---|---|\n| IF-01 | LL_RCC_HSI_Enable | RCC_CR.HSION |\n"
TEST = "/** @test IT-001 @verifies IF-01 IF-19 SWC_LL */\nstatic void it_001(void) { }\n"


def main() -> int:
    from forge_factory.inspection import swtrace

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td) / "WO" / "workspace"
        for rel, text in {".forge-run/manifest.json": json.dumps({"layer": "LL"}),
                          "workproducts/SWE.2/architecture_static.puml": ARCH,
                          "workproducts/SWE.2/software_architecture.md": DOC,
                          "software/tests/integration/test_rcc_integration.c": TEST}.items():
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            (ws / rel).write_text(text)
        f = swtrace.build_all(ws, render=False, doxygen=False)["findings"].get("SWE.5", [])
    if any(x.startswith("IT:UNKNOWN_ARCH_REF:IT-001:IF-01") for x in f):
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
