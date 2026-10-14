"""Minimal structural trace + evidence-integrity gate.

This checks link graph completeness/consistency of IDs, NOT the semantic correctness
of requirements or the independence of tests/reviewers. Those need human review.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from gate_common import checked_file, emit, good, read_json

REQ_TYPES = (
    "system_requirement", "software_requirement", "architecture",
    "detailed_design", "software_unit", "unit_test",
    "integration_test", "software_test", "verification_result",
)
REQUIRED_LINKS = (
    ("system_requirement", "software_requirement", "derives"),
    ("software_requirement", "architecture", "allocated_to"),
    ("architecture", "detailed_design", "refined_by"),
    ("detailed_design", "software_unit", "implemented_by"),
    ("software_unit", "unit_test", "verified_by"),
    ("architecture", "integration_test", "verified_by"),
    ("software_requirement", "software_test", "verified_by"),
    ("unit_test", "verification_result", "has_result"),
    ("integration_test", "verification_result", "has_result"),
    ("software_test", "verification_result", "has_result"),
)


def validate(doc: dict[str, Any], root: Path) -> list[str]:
    errors: list[str] = []
    if not good(doc.get("baseline_id")):
        errors.append("trace baseline missing")
    raw_items, raw_links = doc.get("items"), doc.get("links")
    if not isinstance(raw_items, list) or not raw_items:
        return errors + ["trace items missing"]
    if not isinstance(raw_links, list) or not raw_links:
        return errors + ["trace links missing"]
    if any(not isinstance(i, dict) for i in raw_items) or any(not isinstance(e, dict) for e in raw_links):
        return errors + ["trace items and links must be objects"]
    items = {i.get("id"): i for i in raw_items if good(i.get("id"))}
    if len(items) != len(raw_items):
        errors.append("trace item IDs missing or duplicated")
    counts = Counter(i.get("type") for i in raw_items)
    for t in REQ_TYPES:
        if counts[t] == 0:
            errors.append(f"missing required trace item type: {t}")
    for i in raw_items:
        if i.get("type") not in REQ_TYPES:
            errors.append(f"unknown trace type: {i.get('type')}")
        if i.get("type") == "software_unit":
            source = i.get("source_file")
            if not good(source):
                errors.append(f"{i.get('id')} has no source file")
            else:
                code_path = (root / source).resolve()
                try:
                    code_path.relative_to(root.resolve())
                except ValueError:
                    errors.append(f"source path escapes root: {source}")
                else:
                    if not code_path.is_file():
                        errors.append(f"missing C software unit: {source}")
        if i.get("type") == "verification_result":
            if i.get("result") != "PASS":
                errors.append(f"{i.get('id')} verification result not PASS")
            err = checked_file(i.get("evidence_file", ""), i.get("evidence_sha256", ""), root)
            if err:
                errors.append(f"{i.get('id')}: {err}")
    edges: set[tuple[str, str, str]] = set()
    for l in raw_links:
        src, dst, rel = l.get("source"), l.get("target"), l.get("relation")
        if src not in items or dst not in items:
            errors.append(f"dangling trace link {src}->{dst}")
            continue
        if l.get("reviewed") is not True:
            errors.append(f"trace link not independently reviewed: {src}->{dst}")
        edges.add((src, dst, rel))
    for from_type, to_type, relation in REQUIRED_LINKS:
        # Each item of source type requires at least one link of the required kind
        for i in raw_items:
            if i.get("type") == from_type and good(i.get("id")):
                present = any(
                    src == i["id"] and rel == relation and items[dst].get("type") == to_type
                    for src, dst, rel in edges
                    if dst in items
                )
                if not present:
                    errors.append(f"{i.get('id')} missing {relation} -> {to_type}")
    # Every requirement/design/unit/test must be connected to its preceding level.
    for node_type, prev_type, rel in (
        ("software_requirement", "system_requirement", "derives"),
        ("architecture", "software_requirement", "allocated_to"),
        ("detailed_design", "architecture", "refined_by"),
        ("software_unit", "detailed_design", "implemented_by"),
        ("unit_test", "software_unit", "verified_by"),
        ("integration_test", "architecture", "verified_by"),
        ("software_test", "software_requirement", "verified_by"),
        ("verification_result", None, "has_result"),
    ):
        for i in raw_items:
            if i.get("type") != node_type or not good(i.get("id")):
                continue
            present = any(dst == i["id"] and r == rel and (prev_type is None or items[src].get("type") == prev_type)
                          for src, dst, r in edges if src in items)
            if not present:
                errors.append(f"orphan item {i.get('id')}: no incoming {rel} from {prev_type}")
    return errors



def validate_safety_allocations(doc: dict[str, Any], profile: dict[str, Any]) -> list[str]:
    """Check approved allocation links from externally controlled SSR IDs to SW requirements."""
    if profile.get("asil") == "QM":
        return []
    errors: list[str] = []
    expected = profile.get("safety_allocation", {}).get("software_safety_requirement_ids", [])
    links = doc.get("safety_allocations")
    if not isinstance(links, list):
        return ["missing safety_allocations for ASIL element"]
    software_ids = {i.get("id") for i in doc.get("items", []) if isinstance(i, dict) and i.get("type") == "software_requirement"}
    for ssr in expected:
        matched = [l for l in links if isinstance(l, dict) and l.get("software_safety_requirement_id") == ssr]
        if not matched:
            errors.append(f"missing allocation link for software safety requirement {ssr}")
            continue
        if any(l.get("reviewed") is not True for l in matched):
            errors.append(f"unreviewed safety allocation for {ssr}")
        covered = set()
        for l in matched:
            covered.update(l.get("software_requirement_ids", []))
        if not covered or not covered.issubset(software_ids):
            errors.append(f"safety requirement {ssr} has missing/unrecognized SR coverage")
    return errors

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--trace", required=True)
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = p.parse_args()
    try:
        return emit(validate(read_json(args.trace), Path(args.root)), "TRACE_GATE_PASS")
    except ValueError as e:
        return emit([str(e)], "TRACE_GATE_PASS")


if __name__ == "__main__":
    raise SystemExit(main())
