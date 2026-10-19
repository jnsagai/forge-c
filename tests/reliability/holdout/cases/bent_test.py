"""Holdout: a test edited after a runtime failure until it passes must be flagged by the test tool itself."""
import json
import sys
from pathlib import Path

from forge_factory.mcp.sdk import ToolContext
from forge_factory.mcp.servers import tests as TM

ws = Path(sys.argv[1]) / "ws"
t = ws / "software/tests/unit/test_bench.c"
ctx = ToolContext("forge-tests-mcp", "run_unit", "swe4-author", "SWE.4", ws, "holdout")
first = TM.run_unit(ctx, TM.RunIn(coverage=False))
t.write_text(t.read_text().replace("== 41", "== 42"))  # bend the expectation to the code
second = TM.run_unit(ctx, TM.RunIn(coverage=False))
print(json.dumps({"observed": {"first": first["status"], "second": second["status"],
                               "issues": second.get("issues", [])[:6]}}))
