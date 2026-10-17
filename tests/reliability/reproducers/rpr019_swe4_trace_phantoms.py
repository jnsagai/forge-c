"""RPR-019 (r83): validate_trace accepted test ids absent from the cited test file while SWE.4 was being authored
(the check waited for a SWE.4 baseline); the package was BLOCKED on traceability (UT-019..021)."""
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "validate_trace accepts phantom test ids during SWE.4"


def main() -> int:
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import evidence as EV

    ws = Path(tempfile.mkdtemp(prefix="rpr019-"))
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(
        "- **SWR-001** When the HSI enable function is called, the RCC LL driver shall set RCC_CR.HSION.\n"
        "- **SWR-019** The RCC LL driver shall use at most 4096 bytes of flash.\n")
    (ws / "traceability").mkdir()
    (ws / "traceability/requirements_to_tests.csv").write_text(
        "requirement_id,test_id,test_file\nSWR-001,UT-001,software/tests/unit/test_rcc.c\n"
        "SWR-019,UT-019,software/tests/unit/test_rcc.c\n")
    (ws / "software/tests/unit").mkdir(parents=True)
    (ws / "software/tests/unit/test_rcc.c").write_text('CHECK("UT-001", 1);\n')
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
