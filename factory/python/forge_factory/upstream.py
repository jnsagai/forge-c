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


# Owner 2026-11-09: "by now, it is not needed upstream requirementw for drivers, lets implement them as out of
# context" + "they should be traceable to the reference manual". An ASPICE-only/QM driver work order without an approved
# upstream file is developed out of context: no upstream system or software safety requirement is allocated, and the
# upstream baseline of its requirements is the reference manual (each requirement cites its RM section and page) plus
# the work-order scope and budgets. An approved upstream file still wins; safety work orders keep needing one.
OUT_OF_CONTEXT = "OUT_OF_CONTEXT"
OUT_OF_CONTEXT_PURPOSES = ("ASPICE_ONLY", "QM")
OUT_OF_CONTEXT_LAYERS = ("LL", "HAL", "LL+HAL")
OUT_OF_CONTEXT_DECISION = (
    "owner 2026-11-09: driver developed out of context - no upstream system or software safety requirement is "
    "allocated; the upstream baseline is the reference manual (every requirement traces to the RM section and page it "
    "cites) plus the work-order scope and budgets")


def out_of_context(upstream: dict, *, layer: str, purpose: str) -> dict:
    """The work order's upstream status: APPROVED, OUT_OF_CONTEXT (owner decision above) or NOT_PROVIDED."""
    if upstream["status"] == "APPROVED" or layer not in OUT_OF_CONTEXT_LAYERS or purpose not in OUT_OF_CONTEXT_PURPOSES:
        return upstream
    return {**upstream, "status": OUT_OF_CONTEXT, "issues": [], "template_issues": upstream["issues"],
            "context": OUT_OF_CONTEXT_DECISION}


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
