"""Check whether a device / safety / size-budget profile is approved and complete."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from gate_common import emit, good, positive_int, read_json


def validate(data: dict[str, Any], allow_draft: bool = False) -> list[str]:
    problems: list[str] = []
    for key in ("profile_id", "driver"):
        if not good(data.get(key)):
            problems.append(f"invalid profile {key}")
    if data.get("asil") not in {"QM", "A", "B", "C", "D"}:
        problems.append("ASIL must be QM/A/B/C/D")
    target = data.get("target") or {}
    for key in ("part_number", "core", "silicon_revision", "board"):
        if not good(target.get(key)):
            problems.append(f"target.{key} missing or placeholder")
    tc = data.get("toolchain") or {}
    for key in ("compiler", "version", "reproducible_image_digest"):
        if not good(tc.get(key)):
            problems.append(f"toolchain.{key} missing or placeholder")
    source_docs = data.get("source_documents")
    if not isinstance(source_docs, list) or not source_docs:
        problems.append("source_documents must have at least one verified document")
    else:
        for index, doc in enumerate(source_docs):
            if not isinstance(doc, dict):
                problems.append(f"source_documents[{index}] not an object")
                continue
            for key in ("id", "revision", "sha256"):
                if not good(doc.get(key)):
                    problems.append(f"source_documents[{index}].{key} invalid")
            if not allow_draft and doc.get("approved") is not True:
                problems.append(f"source_documents[{index}] not approved")
    hsi = data.get("hsi") or {}
    if not good(hsi.get("contract_id")) or not good(hsi.get("approved_by")):
        problems.append("approved HSI contract / approver missing")
    if not allow_draft and hsi.get("status") != "approved":
        problems.append("HSI contract not approved")
    safety = data.get("safety_allocation") or {}
    if data.get("asil") != "QM":
        for key in ("technical_safety_requirement_ids", "software_safety_requirement_ids"):
            values = safety.get(key)
            if not isinstance(values, list) or not values or not all(good(v) for v in values):
                problems.append(f"safety_allocation.{key} missing")
        if not good(safety.get("safe_state_contract_id")) or not good(safety.get("approved_by")):
            problems.append("safety allocation safe state or approval missing")
        if not allow_draft and safety.get("status") != "approved":
            problems.append("safety allocation not approved")
    budgets = data.get("budgets") or {}
    for key in ("flash_bytes", "static_ram_bytes", "stack_bytes"):
        if not positive_int(budgets.get(key)):
            problems.append(f"budgets.{key} must be positive integer")
    api = budgets.get("api_cycle_limits")
    if not isinstance(api, dict) or not api:
        problems.append("budgets.api_cycle_limits must be a nonempty dictionary")
    elif any(not good(k) or not positive_int(v) for k, v in api.items()):
        problems.append("invalid per-API cycle limits")
    if not allow_draft and data.get("budgets_status") != "approved":
        problems.append("resource budgets not approved")
    app = data.get("approval") or {}
    for key in ("design_approver", "safety_approver", "baseline_id"):
        if not good(app.get(key)):
            problems.append(f"approval.{key} missing")
    if not allow_draft and data.get("status") != "approved":
        problems.append("profile not approved")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("profile", type=Path)
    parser.add_argument("--allow-draft", action="store_true", help="Schema check only; not a release gate")
    opts = parser.parse_args()
    try:
        data = read_json(opts.profile)
        return emit(validate(data, allow_draft=opts.allow_draft), "PROFILE_VALID" if not opts.allow_draft else "PROFILE_DRAFT_SCHEMA_VALID")
    except ValueError as exc:
        return emit([str(exc)], "PROFILE_VALID")


if __name__ == "__main__":
    raise SystemExit(main())
