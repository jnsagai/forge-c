"""Handoff section9.6: two NO_TESTS preflight refusals exhaust native development
verification allowance before a compiler/test runs. Use real hook tickets and MCP.
All work is temporary; no model, production state or authority is involved.
"""
import asyncio
import io
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "two unexecuted NO_TESTS refusals exhaust development verification allowance before the first actual test"


def main():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ws = root / "workspace"
        (ws / ".forge-run").mkdir(parents=True)
        os.environ.update(FORGE_STATE_DIR=str(root / "state"), FORGE_EVENTS_DIR=str(root / "events"),
                          FORGE_BINDING_ID="RPR153-BIND")
        os.environ.pop("FORGE_MCP_TRUST", None)
        from forge_factory import development_execution as D
        from forge_factory.mcp import sdk
        from forge_factory.mcp.servers import tests
        from forge_factory.policy import fabro_hook
        from forge_factory.policy.authz import Binding

        manifest = {"work_order": "WO-RPR153", "purpose": "ASPICE_ONLY",
                    "development_execution": D.binding(D.NAME, "ASPICE_ONLY")}
        (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))
        binding = root / "binding.json"
        Binding("RPR153-BIND", str(ws), {"swe4_author": {"role": "swe4-author", "phase": "SWE.4"}}).dump(binding)
        server = sdk.build_server("forge-tests-mcp", tests.OPERATIONS)

        def call(number):
            args = {"coverage": False}
            ctx = {"event": "pre_tool_use", "run_id": "RPR153-RUN", "node_id": "swe4_author",
                   "tool_name": "mcp__forge_tests_mcp__run_unit", "tool_input": args,
                   "tool_call_id": f"rpr153-{number}", "workflow_name": "rpr153"}
            stdin, stdout = sys.stdin, sys.stdout
            sys.stdin, sys.stdout = io.StringIO(json.dumps(ctx)), io.StringIO()
            try:
                rc = fabro_hook.main(["--binding", str(binding)])
            finally:
                sys.stdin, sys.stdout = stdin, stdout
            if rc:
                raise RuntimeError("policy hook refused scenario call")
            response = asyncio.run(server.call_tool("run_unit", args))
            return json.loads(response.content[0].text)

        for number in (1, 2):
            out = call(number)
            if out["status"] != "BLOCKED" or "NO_TESTS:software/tests/unit" not in out["issues"]:
                print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:expected missing-tests preflight refusal")
                return 2
        if (ws / "build/tests-unit").exists():
            print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:unexpected verification build")
            return 2
        test = ws / "software/tests/unit/test_first.c"
        test.parent.mkdir(parents=True)
        test.write_text('#include <stdio.h>\nint main(void) {\n'
                        '  volatile int a = 2; int sum = a + 3;\n'
                        '  if (sum != 5) { puts("UT-001 FAIL"); return 1; }\n'
                        '  puts("UT-001 PASS"); return 0;\n}\n')
        out = call(3)
        if out["status"] == "BLOCKED" and "DEVELOPMENT_PHASE_REPAIR_EXHAUSTED" in out["summary"]:
            print(f"SYMPTOM_PRESENT:{SIG}")
            return 1
        if out["status"] != "PASS" or out["metrics"].get("executables") != 1:
            print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:first actual test did not execute successfully")
            return 2
        print("SYMPTOM_ABSENT")
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:140]}")
        sys.exit(2)
