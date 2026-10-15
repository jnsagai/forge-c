"""Human-approved upstream inputs (HSI contract, software safety allocation, budgets) for a work order.

The file is authored and approved by a human (Safety/Owner; specs/001-factory T-001/T-002). The factory only
*reads* it: it is used as an approved input when `status: APPROVED`, an approver and date are recorded and no
placeholder remains. Anything else keeps the inputs NOT_PROVIDED, so SWE.1 fails SWE1-01 honestly.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .common import sha256_file

UPSTREAM_FILE = "upstream/upstream-inputs.yaml"
PLACEHOLDER = re.compile(r"^(FILL|TBD|REPLACE)\b|<fill", re.I)
REQUIRED = ("approval", "target", "hsi_contract", "safety_allocation", "budgets")


def _placeholders(node: Any, path: str = "") -> list[str]:
    if isinstance(node, dict):
        return [p for k, v in node.items() for p in _placeholders(v, f"{path}.{k}" if path else str(k))]
    if isinstance(node, list):
        return [p for i, v in enumerate(node) for p in _placeholders(v, f"{path}[{i}]")]
    return [path] if node is None or (isinstance(node, str) and (not node.strip() or PLACEHOLDER.search(node))) else []


def load_upstream(example: Path) -> dict:
    """{'status': 'APPROVED'|'NOT_PROVIDED', 'issues': [...], 'data': {...}|None, 'sha256': str|None}."""
    p = example / UPSTREAM_FILE
    if not p.is_file():
        return {"status": "NOT_PROVIDED", "issues": ["UPSTREAM_FILE_MISSING"], "data": None, "sha256": None}
    data = yaml.safe_load(p.read_text()) or {}
    issues = [f"MISSING_SECTION:{k}" for k in REQUIRED if k not in data]
    if data.get("status") != "APPROVED":
        issues.append(f"NOT_APPROVED:status={data.get('status')}")
    issues += [f"PLACEHOLDER:{x}" for x in _placeholders({k: data.get(k) for k in REQUIRED if k in data})][:50]
    ok = not issues
    return {"status": "APPROVED" if ok else "NOT_PROVIDED", "issues": issues, "data": data if ok else None,
            "sha256": sha256_file(p), "file": UPSTREAM_FILE}
