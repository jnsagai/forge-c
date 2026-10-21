"""Factory MCP operations called by the local profile's structured runners (feature 010, ADR-0014).

An agent reaches an operation through its MCP server and a policy-hook ticket. A structured runner is deterministic
factory code acting for the node's role, so it calls the same operation handler directly. It does so only when the
role registry grants that operation to the role, and it journals the result exactly like `mcp.sdk.invoke`
(`evidence/tool-results.jsonl`, the record the gates and the finalizer read). Inputs are validated by the operation's
own input model.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..common import utc_now

SERVERS = {"forge-build-mcp": "build", "forge-analysis-mcp": "analysis", "forge-docs-mcp": "docs",
           "forge-tests-mcp": "tests", "forge-sim-mcp": "sim"}


class ToolRefused(PermissionError):
    pass


def call(ws: Path, server: str, op: str, args: dict, role: str, phase: str, run_id: str | None = None) -> dict:
    from importlib import import_module

    from ..mcp.sdk import ToolContext
    from ..registry.mcp_registry import load_registry

    ws = Path(ws).resolve()
    key = f"{server}.{op}"
    ops = load_registry().ops()
    if key not in ops or role not in ops[key].role_grants:
        raise ToolRefused(f"ROLE_NOT_GRANTED:{role}->{key}")
    mod = import_module(f"forge_factory.mcp.servers.{SERVERS[server]}")
    operation = next(o for o in mod.OPERATIONS if o.name == op)
    run = run_id or json.loads((ws / ".forge-run/manifest.json").read_text())["work_order"]
    ctx = ToolContext(server, op, role, phase, ws, run)
    out = operation.handler(ctx, operation.model.model_validate(args))
    rec = {"ts_utc": utc_now(), "server": server, "op": op, "role": role, "phase": phase, "run_id": run,
           "result": out, "caller": "lrtx-structured-runner"}
    (ws / "evidence").mkdir(parents=True, exist_ok=True)
    with open(ws / "evidence" / "tool-results.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return out
