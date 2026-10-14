"""Compare already-normalized, target-derived metrics with approved profile budgets.

NOT a linker-map parser and NOT proof of WCET; provenance is externally verified.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from gate_common import checked_file, emit, nonnegative_int, read_json


def validate(profile: dict[str, Any], metrics: dict[str, Any], root: Path, *, require_hardware_cycles: bool = True) -> list[str]:
    errors: list[str] = []
    target = profile.get("target", {})
    tc = profile.get("toolchain", {})
    if metrics.get("target_part_number") != target.get("part_number"):
        errors.append("metrics target does not match approved MCU part number")
    if metrics.get("toolchain_version") != tc.get("version"):
        errors.append("metrics compiler version does not match approved compiler")
    if metrics.get("status") != "measured":
        errors.append("metrics have not been measured/approved")
    checks = (
        ("loadable_flash_bytes", "flash_bytes"),
        ("static_ram_bytes", "static_ram_bytes"),
        ("max_stack_bytes", "stack_bytes"),
    )
    for measured, budget in checks:
        value, limit = metrics.get(measured), profile.get("budgets", {}).get(budget)
        if not nonnegative_int(value):
            errors.append(f"metrics.{measured} missing or invalid")
        elif nonnegative_int(limit) and value > limit:
            errors.append(f"{measured}={value} exceeds {budget}={limit}")
    if metrics.get("stack_proven") is not True:
        errors.append("peak stack upper bound not proven including IRQ/preemption")
    if metrics.get("heap_calls") != 0:
        errors.append("target heap_calls must equal zero")
    limits = profile.get("budgets", {}).get("api_cycle_limits", {})
    times = metrics.get("api_worst_case_cycles") or {}
    if require_hardware_cycles:
        if metrics.get("cycle_source") != "real_hardware":
            errors.append("API timing must come from real hardware, not Renode/host")
        for api, budget in limits.items():
            value = times.get(api)
            if not nonnegative_int(value):
                errors.append(f"missing hardware cycle result for API {api}")
            elif value > budget:
                errors.append(f"API {api} worst-case {value} exceeds {budget} cycles")
    for prefix, path_field, hash_field in (
        ("build", "build_log", "build_log_sha256"),
        ("measurement", "measurement_record", "measurement_sha256"),
    ):
        if not require_hardware_cycles and prefix == "measurement":
            continue
        err = checked_file(metrics.get(path_field, ""), metrics.get(hash_field, ""), root)
        if err:
            errors.append(f"{prefix} log: {err}")
    return errors


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--profile", required=True)
    p.add_argument("--metrics", required=True)
    p.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = p.parse_args()
    try:
        return emit(validate(read_json(args.profile), read_json(args.metrics), Path(args.root)), "FOOTPRINT_GATE_PASS")
    except ValueError as e:
        return emit([str(e)], "FOOTPRINT_GATE_PASS")


if __name__ == "__main__":
    raise SystemExit(main())
