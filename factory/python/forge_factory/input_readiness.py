"""CAPA-207 (owner 2026-11-09 "implement the 3 points that could make it faster"): check a driver order's run inputs
before it reaches the GPU. SPI LL L41N spent 4 h of SWE.1 before the inspector found that its inputs held no CPU/timing
budget (SWE1-04, CAPA-206). The line now compares the work-order spec with what SWE.1 needs from it - the documents
the requirements trace to, the resource budgets, the target identity, the system names and a CPU/timing budget (the
spec's own or the one the factory prepares) - and holds the step as INPUT_GAP:<code>:<example> instead of launching.
Pure: no files written, no model calls."""
from __future__ import annotations

import re

from . import simulation_performance as SP
from .upstream import OUT_OF_CONTEXT, OUT_OF_CONTEXT_LAYERS, OUT_OF_CONTEXT_PURPOSES

DRIVER_LAYERS = ("LL", "HAL", "LL+HAL")
ROLES = ("datasheet", "reference_manual_memory_map", "reference_manual_register_conventions", "development_guideline")
CHAPTER = re.compile(r"reference_manual_[a-z0-9_]+_chapter$")
BUDGETS = ("flash_bytes", "static_ram_bytes", "stack_bytes")
TARGET = ("core", "part_number", "silicon_revision", "hsi_contract", "safety_allocation", "source_documents")


def gaps(spec: dict, *, purpose: str, upstream_approved: bool) -> list[str]:
    """Input-gap codes of a driver work-order spec for SWE.1 (empty: ready). Other layers are not checked."""
    layer = spec.get("layer", "LL+HAL")
    if layer not in DRIVER_LAYERS:
        return []
    out = []
    roles = [i.get("role") for i in spec.get("inputs") or [] if isinstance(i, dict)]
    out += [f"INPUT_ROLE_MISSING_{r.upper()}" for r in ROLES if r not in roles]
    if not any(CHAPTER.match(str(r)) for r in roles):
        out.append("INPUT_ROLE_MISSING_REFERENCE_MANUAL_CHAPTER")
    b = spec.get("budgets") or {}
    if any(type(b.get(k)) is not int or b[k] <= 0 for k in BUDGETS):
        out.append("RESOURCE_BUDGET")
    t = spec.get("target") or {}
    if any(not t.get(k) for k in TARGET):
        out.append("TARGET_FIELDS")
    if not spec.get("system_names"):
        out.append("SYSTEM_NAMES")
    status = "APPROVED" if upstream_approved else (
        OUT_OF_CONTEXT if purpose in OUT_OF_CONTEXT_PURPOSES and layer in OUT_OF_CONTEXT_LAYERS else "NOT_PROVIDED")
    try:
        budget, _ = SP.prepared(spec, status)
    except ValueError:
        out.append("CPU_TIMING_BUDGET_INVALID")
    else:
        if budget is None:  # SWE1-04 needs a measurable CPU/timing constraint (CAPA-206)
            out.append("CPU_TIMING_BUDGET")
    return out
