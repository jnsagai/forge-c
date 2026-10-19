"""RPR-026 (r93 SWE4-02): a traced unit test exercised a different function than the API allocated to its
requirement (mapping shift); validate_trace passed and only the SWE.4 inspector found it."""
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "validate_trace accepts a traced test that never calls the allocated API"


def main() -> int:
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import evidence as EV

    ws = Path(tempfile.mkdtemp(prefix="rpr026-"))
    files = {".forge-run/manifest.json": json.dumps({"layer": "LL"}),
             "workproducts/SWE.2/software_architecture.md": "# A\n## Requirement allocation\n| SWR | Function |\n"
             "|---|---|\n| SWR-001 | LL_RCC_HSI_Enable |\n| SWR-002 | LL_RCC_HSI_IsReady |\n",
             "workproducts/SWE.1/software_requirements.md":
                 "- **SWR-001** When the HSI enable function is called, the RCC LL driver shall set RCC_CR.HSION.\n"
                 "- **SWR-002** When the HSI ready query is called, the RCC LL driver shall return 1U.\n",
             "traceability/requirements_to_tests.csv": "requirement_id,test_id,test_file\n"
             "SWR-001,UT-001,software/tests/unit/test_rcc.c\nSWR-002,UT-002,software/tests/unit/test_rcc.c\n",
             "software/tests/unit/test_rcc.c": 'static void ut_a(void)\n{\n    LL_RCC_HSI_IsReady();\n'
             '    CHECK("UT-001", 1);\n}\nstatic void ut_b(void)\n{\n    LL_RCC_HSI_Enable();\n    CHECK("UT-002", 1);\n}\n'}
    for rel, txt in files.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(txt)
    os.environ.update({"FORGE_MCP_TRUST": "env", "FORGE_WORKSPACE": str(ws), "FORGE_EVENTS_DIR": str(ws / ".ev"),
                       "FORGE_STATE_DIR": str(ws / ".st"), "FORGE_ROLE": "swe4-author", "FORGE_PHASE": "SWE.4"})
    out = sdk.invoke("forge-evidence-mcp", next(o for o in EV.OPERATIONS if o.name == "validate_trace"), {})
    if out["status"] == "PASS":
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
