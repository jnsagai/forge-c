"""Run the factory's cppcheck operation (forge-analysis-mcp) on the prepared workspace."""
import json
import sys
from pathlib import Path

from forge_factory.mcp.sdk import ToolContext
from forge_factory.mcp.servers import analysis as A

ws = Path(sys.argv[1]) / "ws"
r = A.cppcheck(ToolContext("forge-analysis-mcp", "cppcheck", "swe3-author", "SWE.3", ws, "bench"), A.AnalyzeIn())
print(json.dumps({"observed": {"status": r["status"], "issues": r.get("issues", [])[:20]}}))
