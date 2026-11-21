"""Actual immutable source/target/tool predicates shared by MCP and structured packets."""

from __future__ import annotations

import json
from pathlib import Path

from ..afo.durable import digest
from ..governance.level import FUNCTIONAL, swe1_level


def applicability(workspace):
    p = Path(workspace) / ".forge-run/manifest.json"
    manifest = json.loads(p.read_text()) if p.is_file() else {}
    functional = swe1_level(manifest) == FUNCTIONAL
    identity = {
        "inputs": sorted((i["path"], i.get("sha256")) for i in manifest.get("inputs", [])),
        "target": manifest.get("target"),
        "layer": manifest.get("layer"),
        "trace_profile": manifest.get("trace_profile"),
        "register_contract": manifest.get("register_contract"),
    }
    template = manifest.get("swe1_template")
    if functional:
        identity.update(swe1_level=FUNCTIONAL, swe1_template=template)
    valid = bool(manifest.get("inputs")) and (not functional or isinstance(template, str) and bool(template))
    return {
        "target": (manifest.get("target") or {}).get("part_number"),
        "source_version": digest(identity) if valid else None,
        "tool_versions": manifest.get("tool_versions") or {},
        "holdout": bool(manifest.get("evaluation_holdout")),
        **({"require_exact_source": True} if functional else {}),
    }
