"""T010 — typed loader for config/factory/mcp-registry.yaml plus the runtime availability overlay.

The authored registry is the *design* contract (lifecycle strings stay as authored). Runtime truth
(which adapter module implements an op, which backing executable is installed) lives in
`config/factory/mcp-runtime.yaml` and is checked by preflight; nothing is inferred.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

from ..common import CONFIG_DIR

OP_NAME = re.compile(r"^[a-z][a-z0-9_]{1,47}$")
SERVER_ID = re.compile(r"^forge-[a-z]+-mcp$")


class McpOperation(BaseModel):
    name: str
    logical_tool: str
    mandatory: bool
    status: str
    timeout_seconds: int = Field(gt=0, le=600)
    role_grants: list[str] = Field(default_factory=list)
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not OP_NAME.match(v):
            raise ValueError(f"invalid op name {v!r}")
        return v


class McpServer(BaseModel):
    id: str
    transport: str
    lifecycle: str
    open_source_only: bool
    description: str
    server_mandatory: bool
    ops: list[McpOperation]

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not SERVER_ID.match(v):
            raise ValueError(f"invalid server id {v!r}")
        return v


class McpRegistry(BaseModel):
    schema_: str = Field(alias="schema")
    version: str
    policy: str
    server_catalog: list[McpServer]

    def ops(self) -> dict[str, McpOperation]:
        return {f"{s.id}.{o.name}": o for s in self.server_catalog for o in s.ops}

    def server(self, server_id: str) -> McpServer | None:
        return next((s for s in self.server_catalog if s.id == server_id), None)

    def grants_for(self, role: str) -> set[str]:
        return {k for k, o in self.ops().items() if role in o.role_grants}


OVERLAY = CONFIG_DIR / "mcp-registry.v0.5-kpi.yaml"


def apply_overlay(data: dict, overlay: Path = OVERLAY) -> dict:
    """Merge the versioned v0.5 overlay (additive only: new ops; existing ops are never altered)."""
    if not overlay.is_file():
        return data
    ov = yaml.safe_load(overlay.read_text(encoding="utf-8"))
    for srv in data["server_catalog"]:
        add = (ov.get("servers") or {}).get(srv["id"], {}).get("ops", [])
        names = {o["name"] for o in srv["ops"]}
        if any(o["name"] in names for o in add):
            raise ValueError("overlay may not redefine existing ops")
        srv["ops"] = srv["ops"] + add
    return data


def role_tool_additions(overlay: Path = OVERLAY) -> dict[str, list[str]]:
    if not overlay.is_file():
        return {}
    return (yaml.safe_load(overlay.read_text(encoding="utf-8")) or {}).get("role_tool_additions") or {}


def load_registry(path: Path | None = None) -> McpRegistry:
    data = yaml.safe_load((path or CONFIG_DIR / "mcp-registry.yaml").read_text(encoding="utf-8"))
    if path is None:
        data = apply_overlay(data)
    reg = McpRegistry.model_validate(data)
    if reg.policy != "EVERY_AGENT_TOOL_USES_MCP":
        raise ValueError("registry policy must be EVERY_AGENT_TOOL_USES_MCP")
    seen: set[str] = set()
    for s in reg.server_catalog:
        if s.id in seen:
            raise ValueError(f"duplicate server {s.id}")
        seen.add(s.id)
        if not s.open_source_only or s.transport != "stdio":
            raise ValueError(f"{s.id}: only open-source stdio servers are allowed")
        names = [o.name for o in s.ops]
        if len(names) != len(set(names)):
            raise ValueError(f"{s.id}: duplicate op")
    return reg


def fabro_tool_name(op_key: str) -> str:
    """forge-build-mcp.compile -> mcp__forge_build_mcp__compile (Fabro 0.362 naming, ADR-0002)."""
    server, op = op_key.split(".", 1)
    return f"mcp__{re.sub(r'[^A-Za-z0-9_]', '_', server)}__{re.sub(r'[^A-Za-z0-9_]', '_', op)}"


def op_from_fabro_tool(tool_name: str, reg: McpRegistry) -> str | None:
    lookup = {fabro_tool_name(k): k for k in reg.ops()}
    return lookup.get(tool_name)
