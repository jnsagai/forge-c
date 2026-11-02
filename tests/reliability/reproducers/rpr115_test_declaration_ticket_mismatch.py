"""RPR-115 (Fabro runs WO-F014-SWE5-CRCL-20261102-L12 and -L12B, local line, Omniverse2, Ornith native SWE.5 author;
WO-F014-CMP-SWE6-CRCL-20261102-07, cloud line, loop10, Claude native SWE.6 author; 2026-11-02): the author corrected
its own test after a runtime failure and declared the correction with report_defect kind TEST, as the gate and the
test tool told it to. Fabro sent the list arguments as JSON text (test_files '["software/tests/..."]'); every
well-formed declaration came back BLOCKED NO_AUTHORIZATION_TICKET, no defect was recorded, the gate rejected twice
with TEST_CHANGED_AFTER_FAIL and the route stopped BLOCKED STUCK.

Scenario (everything under TMPDIR): a workspace with one requirement and an integration test that failed at runtime,
was edited and passes on the same product code (the real test-integrity records). The swe5-author's declaration
goes through the real policy hook (forge_factory.policy.fabro_hook.main, which issues the one-time ticket from the
call as Fabro sends it) and then through the real MCP server call path of forge-evidence-mcp.report_defect.
Symptom: the declaration is refused NO_AUTHORIZATION_TICKET and the gate still finds the undeclared test change."""
import asyncio
import io
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "native author's report_defect kind TEST declaration refused NO_AUTHORIZATION_TICKET; test stays undeclared"
TEST = "software/tests/integration/test_crc_integration.c"
QUOTE = "When LL_CRC_ReadData32 is called, the CRC LL driver shall return the value currently held in CRC_DR.DR."


def main() -> int:
    td = Path(tempfile.mkdtemp())
    ws, state = td / "ws", td / "state"
    os.environ.update(FORGE_STATE_DIR=str(state), FORGE_EVENTS_DIR=str(state / "events"),
                      FORGE_BINDING_ID="RPR115-BIND")
    os.environ.pop("FORGE_MCP_TRUST", None)
    from forge_factory.inspection import defects
    from forge_factory.mcp import sdk
    from forge_factory.mcp.servers import evidence
    from forge_factory.policy import fabro_hook
    from forge_factory.policy.authz import Binding

    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(f"# Requirements\n\n- **SWR-002**: {QUOTE}\n")
    (ws / "software/ll").mkdir(parents=True)
    (ws / "software/ll/drv.c").write_text("int drv(void) { return 0; }\n")
    t = ws / TEST
    t.parent.mkdir(parents=True)
    t.write_text("int main(void) { return 1; } /* asserted a word the register no longer held */\n")
    defects.record_integrity(ws, "SWE.5", "run_integration", "FAIL", defects.integrity(ws, [t], [t]))
    t.write_text("int main(void) { return 0; } /* corrected: checks the value read after the first feed */\n")
    defects.record_integrity(ws, "SWE.5", "run_integration", "PASS", defects.integrity(ws, [t], []))
    if not defects.bent_tests(ws, "SWE.5"):
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:edited test not flagged before the declaration")
        return 2

    tool = "mcp__forge_evidence_mcp__report_defect"
    args = {"kind": "TEST", "summary": "IT-005 asserted a word CRC_DR no longer held; corrected to the value read "
                                       "after the first feed (SWR-002).",
            "requirement_ids": '["SWR-002"]', "test_files": json.dumps([TEST]), "requirement_quote": QUOTE}
    bpath = td / "binding.json"
    Binding("RPR115-BIND", str(ws), {"swe5_author": {"role": "swe5-author", "phase": "SWE.5"}}).dump(bpath)
    ctx = {"event": "pre_tool_use", "run_id": "RPR115-RUN", "node_id": "swe5_author", "tool_name": tool,
           "tool_input": args, "tool_call_id": "rpr115-call-1", "workflow_name": "rpr115"}
    stdin, stdout = sys.stdin, sys.stdout
    sys.stdin, sys.stdout = io.StringIO(json.dumps(ctx)), io.StringIO()
    try:
        rc = fabro_hook.main(["--binding", str(bpath)])
        hook_out = sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = stdin, stdout
    if rc != 0:
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:policy hook denied the declaration: {hook_out[:200]}")
        return 2
    server = sdk.build_server("forge-evidence-mcp", evidence.OPERATIONS)
    res = asyncio.run(server.call_tool("report_defect", args))
    out = json.loads(res.content[0].text)
    left = defects.bent_tests(ws, "SWE.5")
    print(f"report_defect: {out['status']} {out['summary']}; gate: {left or 'no undeclared test change'}")
    if out["status"] != "PASS" or left:
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    sys.exit(main())
