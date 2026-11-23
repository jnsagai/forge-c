#!/usr/bin/env python3
"""forge-c-hi MCP server: the `hi` gate functions as MCP tools over stdio (JSON-RPC 2.0, one message per line).

Standard library only. Implements initialize, ping, tools/list and tools/call. Tool results carry the same compact JSON
payload as the CLI, as text content and as structuredContent. A gate FAIL is a normal result; only usage or
configuration errors set isError.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # never write __pycache__ into the installed skills (scope gate)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from forge_hi import __version__, api  # noqa: E402
from forge_hi.config import ConfigError, find_root  # noqa: E402

PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
STAGE = {"type": "string", "description": "V-model stage id, e.g. sys-req, sw-req"}
ROOT = {"type": "string", "description": "project root (default: nearest folder with .hi/project.json)"}


def _obj(props: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": dict(props, root=ROOT), "required": required or [],
            "additionalProperties": False}


TOOLS = {
    "hi_init": (
        "Create .hi/project.json (profile, integrity level, input class, inputs, role bindings) and hash the inputs.",
        _obj({"level": {"type": "string"}, "profile": {"type": "string"}, "input_class": {"type": "string"},
              "entry": {"type": "string"}, "inputs": {"type": "array", "items": {"type": "string"}},
              "project_id": {"type": "string"}, "author": {"type": "string"}, "inspector": {"type": "string"},
              "author_model": {"type": "string"}, "inspector_model": {"type": "string"},
              "author_family": {"type": "string"}, "inspector_family": {"type": "string"},
              "from_file": {"type": "string"}, "force": {"type": "boolean"}, "ears": {"type": "boolean"},
              "driver_level": {"type": "string", "enum": ["interface", "functional"]},
              "allowed_terms": {"type": "array", "items": {"type": "string"}}}),
        lambda r, a: api.init(r, **a),
    ),
    "hi_doc_index": (
        "Section/page outline of a reference document you supply (never redistributed).",
        _obj({"pdf": {"type": "string"}, "doc_id": {"type": "string"}}, ["pdf", "doc_id"]),
        lambda r, a: api.doc_index(r, a["pdf"], a["doc_id"]),
    ),
    "hi_validate": (
        "Schema and envelope check of one workproduct file.",
        _obj({"file": {"type": "string"}}, ["file"]),
        lambda r, a: api.validate(r, a["file"]),
    ),
    "hi_quality_rules": (
        "Deterministic requirement-quality rules for a requirement stage.",
        _obj({"stage": STAGE}, ["stage"]),
        lambda r, a: api.quality(r, a["stage"]),
    ),
    "hi_governance_check": (
        "Governance package coverage of the entry stage: every need (and in-scope document section) in a use case, "
        "out of scope or an open point; every use case realised by a requirement.",
        _obj({"stage": STAGE, "before_requirements": {"type": "boolean"}}, ["stage"]),
        lambda r, a: api.governance(r, a["stage"], realization=not a.get("before_requirements")),
    ),
    "hi_trace_check": (
        "Bidirectional traceability: dangling, orphan, uncovered and suspect links; renders hi/trace-matrix.md.",
        _obj({"stage": STAGE}),
        lambda r, a: api.trace(r, a.get("stage")),
    ),
    "hi_scope_check": (
        "Check that the files changed by a role lie inside its write scope.",
        _obj({"role": {"type": "string", "enum": ["author", "inspector", "release", "intake"]}, "stage": STAGE,
              "snapshot": {"type": "string"}}, ["role", "stage"]),
        lambda r, a: api.scope(r, a["role"], a["stage"], a.get("snapshot")),
    ),
    "hi_gate": (
        "Run every gate the standard profile requires for this stage at the project's integrity level.",
        _obj({"stage": STAGE}, ["stage"]),
        lambda r, a: api.gate(r, a["stage"]),
    ),
    "hi_status": (
        "V-model position, gate verdicts, open findings and open points.",
        _obj({}),
        lambda r, a: api.status(r),
    ),
    "hi_seal_package": (
        "Seal a READY_FOR_OFFLINE_REVIEW or BLOCKED review package.",
        _obj({}),
        lambda r, a: api.seal(r),
    ),
}


def _reply(msg_id, result=None, error=None) -> dict:
    out = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        out["error"] = error
    else:
        out["result"] = result
    return out


def call_tool(name: str, args: dict) -> dict:
    _, _, fn = TOOLS[name]
    args = dict(args or {})
    root_arg = args.pop("root", None)
    root = Path(root_arg).resolve() if root_arg else (Path.cwd() if name == "hi_init" else find_root())
    try:
        code, payload = fn(root, args)
    except (ConfigError, ValueError, FileNotFoundError, KeyError, TypeError) as exc:
        code, payload = 2, {"cmd": name, "status": "ERROR", "error": str(exc)[:500]}
    payload = api.compact(payload)
    return {"content": [{"type": "text", "text": json.dumps(payload, separators=(",", ":"), sort_keys=True)}],
            "structuredContent": payload, "isError": code == 2}


def handle(msg: dict) -> dict | None:
    method, msg_id = msg.get("method"), msg.get("id")
    if msg_id is None:  # notification
        return None
    if method == "initialize":
        asked = (msg.get("params") or {}).get("protocolVersion")
        return _reply(msg_id, {
            "protocolVersion": asked if asked in PROTOCOLS else PROTOCOLS[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "forge-c-hi", "version": __version__},
            "instructions": "Deterministic forge-c-hi gates. Verdicts are PASS, FAIL or NOT_RUN; NOT_RUN is a gap.",
        })
    if method == "ping":
        return _reply(msg_id, {})
    if method == "tools/list":
        return _reply(msg_id, {"tools": [{"name": n, "description": d, "inputSchema": s} for n, (d, s, _) in TOOLS.items()]})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        if name not in TOOLS:
            return _reply(msg_id, error={"code": -32602, "message": f"Unknown tool: {name}"})
        return _reply(msg_id, call_tool(name, params.get("arguments") or {}))
    return _reply(msg_id, error={"code": -32601, "message": f"Method not found: {method}"})


def main() -> int:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
            if not isinstance(msg, dict):
                raise ValueError("not an object")
        except ValueError:
            out = _reply(None, error={"code": -32700, "message": "Parse error"})
        else:
            out = handle(msg)
        if out is not None:
            sys.stdout.write(json.dumps(out, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
