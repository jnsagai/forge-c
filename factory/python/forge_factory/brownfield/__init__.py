"""Feature 008 - brownfield work orders: the owner delivers existing C code (with origin, licence and a scope) and
the factory produces the remaining SWE.1-SWE.6 / ISO 26262 software work products around it.

Every brownfield branch in the factory is keyed on the manifest's `delivery` block; a manifest without it is a
greenfield work order and keeps its previous behaviour (FR-019).

Code modes: FROZEN (the delivered files are never changed; findings go to the owner) and FIX_ALLOWED (a delivered
file may change only to fix a filed CODE defect, with a change report)."""
from __future__ import annotations

import json
from pathlib import Path

MODES = ("FROZEN", "FIX_ALLOWED")
DELIVERY_DIR = ".forge-run/delivery"


def manifest_of(ws) -> dict:
    p = Path(ws) / ".forge-run/manifest.json"
    try:
        return json.loads(p.read_text()) if p.is_file() else {}
    except (OSError, ValueError):
        return {}


def is_brownfield(manifest: dict | None) -> bool:
    return bool((manifest or {}).get("delivery"))


def code_mode(manifest: dict | None) -> str | None:
    return (manifest or {}).get("code_mode") if is_brownfield(manifest) else None


def delivered_paths(manifest: dict | None, role: str | None = "delivered_code") -> list[str]:
    """Workspace paths of the delivered files (role None: code and dependencies)."""
    if not is_brownfield(manifest):
        return []
    return [d["path"] for d in manifest.get("delivered") or [] if role is None or d.get("role") == role]
