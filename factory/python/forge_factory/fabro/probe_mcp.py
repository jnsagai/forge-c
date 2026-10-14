"""T004 capability probe MCP server (stdio). Records each call so the audit can prove MCP reachability."""
from __future__ import annotations

import json
import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from ..common import utc_now

app = MCPServer("forge-probe", version="0.4.0")
LOG = Path(os.environ.get("FORGE_PROBE_LOG", "/tmp/forge-probe-calls.jsonl"))


@app.tool()
def ping(text: str) -> dict:
    """Return a compact status echo for capability probing."""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": utc_now(), "tool": "ping", "text": text[:80]}) + "\n")
    return {"status": "PASS", "echo": text[:80]}


if __name__ == "__main__":
    app.run("stdio")
