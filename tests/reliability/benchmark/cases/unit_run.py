"""Run the factory's own run_unit tool (forge-tests-mcp) on the prepared workspace."""
import json
import sys
from pathlib import Path

from forge_factory.mcp.sdk import ToolContext
from forge_factory.mcp.servers import tests as TM

ws = Path(sys.argv[1]) / "ws"
r = TM.run_unit(ToolContext("forge-tests-mcp", "run_unit", "swe4-author", "SWE.4", ws, "bench"), TM.RunIn(coverage=False))
print(json.dumps({"observed": {"status": r["status"], "issues": r.get("issues", [])[:12],
                               "passed": r.get("metrics", {}).get("passed"), "failed": r.get("metrics", {}).get("failed")}}))
