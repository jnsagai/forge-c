"""Check required tool and review evidence records; requires raw log content hashes.

No automatic authentication of human reviewers is attempted: production releases
must use SCM/ALM authorization rather than trusting agent-authored JSON.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from gate_common import checked_file, emit, read_json

MANDATORY = (
    "target_compile", "host_unit", "static_analysis", "misra_assessment",
    "component_verification", "integration_verification", "software_verification",
    "coverage_assessment", "fault_injection", "target_hil",
    "tool_confidence", "independent_review",
)


def validate(data: dict[str, Any], root: Path, *, phase: str = "release") -> list[str]:
    errors: list[str] = []
    checks = MANDATORY if phase == "release" else tuple(k for k in MANDATORY if k not in {"target_hil", "tool_confidence", "independent_review"})
    for check in checks:
        record = data.get(check)
        if not isinstance(record, dict):
            errors.append(f"missing check: {check}")
            continue
        if record.get("status") != "PASS":
            errors.append(f"{check} status not PASS")
        err = checked_file(record.get("log", ""), record.get("sha256", ""), root)
        if err:
            errors.append(f"{check}: {err}")
    return errors


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--checks", required=True)
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = p.parse_args()
    try:
        return emit(validate(read_json(args.checks), Path(args.root)), "CHECKS_GATE_PASS")
    except ValueError as e:
        return emit([str(e)], "CHECKS_GATE_PASS")


if __name__ == "__main__":
    raise SystemExit(main())
