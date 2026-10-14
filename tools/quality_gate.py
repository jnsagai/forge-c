"""Aggregate objective evidence gates. No AI summary can override a failed gate."""
from __future__ import annotations

import argparse
from pathlib import Path

from checks_gate import validate as check_checks
from footprint_gate import validate as check_footprint
from gate_common import emit, read_json
from trace_gate import validate as check_trace, validate_safety_allocations
from validate_profile import validate as check_profile


def validate(profile_path: str, trace_path: str, metrics_path: str, checks_path: str, root: Path, phase: str = "release") -> list[str]:
    problems: list[str] = []
    required_paths = {"profile": profile_path, "trace": trace_path, "metrics": metrics_path, "checks": checks_path}
    records = {}
    for label, path in required_paths.items():
        try:
            records[label] = read_json(path)
        except ValueError as err:
            problems.append(f"[{label}] {err}")
    if problems:
        return problems
    problems.extend(f"[profile] {x}" for x in check_profile(records["profile"]))
    problems.extend(f"[trace] {x}" for x in check_trace(records["trace"], root))
    problems.extend(f"[safety_trace] {x}" for x in validate_safety_allocations(records["trace"], records["profile"]))
    problems.extend(f"[footprint] {x}" for x in check_footprint(records["profile"], records["metrics"], root, require_hardware_cycles=(phase == "release")))
    problems.extend(f"[checks] {x}" for x in check_checks(records["checks"], root, phase=phase))
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("candidate", "release"), default="release")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--metrics", required=True)
    parser.add_argument("--checks", required=True)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    opts = parser.parse_args()
    try:
        errs = validate(opts.profile, opts.trace, opts.metrics, opts.checks, Path(opts.root), phase=opts.phase)
    except ValueError as e:
        errs = [str(e)]
    status = "CANDIDATE_TECHNICAL_GATES_PASS__NOT_ASIL_B_RELEASE" if opts.phase == "candidate" else "TECHNICAL_EVIDENCE_PASS__HUMAN_RELEASE_APPROVAL_STILL_REQUIRED"
    return emit(errs, status)


if __name__ == "__main__":
    raise SystemExit(main())
