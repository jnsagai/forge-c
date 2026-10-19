"""Compile an injected product error with run_unit and classify the result with the candidate's CRE taxonomy."""
import json
import sys
from pathlib import Path

from forge_factory.mcp.sdk import ToolContext
from forge_factory.mcp.servers import tests as TM

ws = Path(sys.argv[1]) / "ws"
r = TM.run_unit(ToolContext("forge-tests-mcp", "run_unit", "swe4-author", "SWE.4", ws, "bench"), TM.RunIn(coverage=False))
diag = [i for i in r.get("issues", []) if "error" in i.lower()]
try:
    from forge_factory.reliability.taxonomy import classify
    c = classify(diag[0] if diag else "")
    routed = {"failure_class": c.failure_class, "route": c.route}
except ImportError:
    routed = {"failure_class": "NOT_AVAILABLE", "route": "NOT_AVAILABLE"}
print(json.dumps({"observed": {"status": r["status"], "issues": r.get("issues", [])[:12], **routed}}))
