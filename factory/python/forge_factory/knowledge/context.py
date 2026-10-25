"""Actual immutable source/target/tool predicates shared by MCP and structured packets."""

from __future__ import annotations
import json
from pathlib import Path
from ..afo.durable import digest


def applicability(workspace):
    p = Path(workspace) / ".forge-run/manifest.json"
    manifest = json.loads(p.read_text()) if p.is_file() else {}
    version = (
        digest(
            {
                "inputs": sorted((i["path"], i.get("sha256")) for i in manifest.get("inputs", [])),
                "target": manifest.get("target"),
                "layer": manifest.get("layer"),
                "trace_profile": manifest.get("trace_profile"),
                "register_contract": manifest.get("register_contract"),
            }
        )
        if manifest.get("inputs")
        else None
    )
    return {
        "target": (manifest.get("target") or {}).get("part_number"),
        "source_version": version,
        "tool_versions": manifest.get("tool_versions") or {},
        "holdout": bool(manifest.get("evaluation_holdout")),
    }
