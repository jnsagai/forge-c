"""Chronological, holdout-isolated learning comparisons; all learning costs count."""

from __future__ import annotations

import math

from ..afo.durable import Refused, digest

COSTS = ("product_tokens", "retrieval_tokens", "curation_tokens", "validation_tokens", "wall_seconds", "energy_joules")
QUALITY = ("false_ready", "critical_defect_missed")
MEASUREMENT_FIELDS = {"condition", "native_run_id", "consumer_id", "started_at", "lesson_exposure_ids", *QUALITY}


def compare(manifest, baseline, memory, *, lesson_store=None):
    """Combine independently verified rows from matched, preregistered cohorts."""
    ids = manifest["evaluation_ids"]
    if not ids or len(set(ids)) != len(ids) or set(ids) & set(manifest["learning_ids"]):
        raise Refused("LEARNING_HOLDOUT_LEAKAGE")
    cutoff, started = manifest["learning_cutoff"], manifest["evaluation_start"]
    if (any(type(t) not in (int, float) or not math.isfinite(t) for t in (cutoff, started)) or cutoff >= started):
        raise Refused("LEARNING_CHRONOLOGY_INVALID")

    manifest_hash = digest(manifest)
    seen_runs, seen_consumers = set(), set()
    incomplete = []

    def normalized(rows, condition):
        if len(rows) != len(ids) or {r["case_id"] for r in rows} != set(ids):
            raise Refused("COMPARISON_DENOMINATOR_CHANGED")
        for r in rows:
            if type(r.get("independent_pass")) is not bool:
                raise Refused("INDEPENDENT_BOOLEAN_OUTCOME_REQUIRED")
            if r["configuration_sha256"] != manifest["configuration_sha256"] or r["manifest_sha256"] != manifest_hash:
                raise Refused("COMPARISON_IDENTITY_CHANGED")
            if any(
                type(r["costs"].get(k)) not in (int, float) or (not math.isfinite(r["costs"][k]) or r["costs"][k] < 0)
                for k in COSTS
            ):
                raise Refused("LEARNING_OVERHEAD_UNKNOWN")
            measurement = r.get("measurement")
            if measurement is None:
                incomplete.append({"condition": condition, "case_id": r["case_id"], "reason": "MISSING_BOUND_MEASUREMENT"})
                continue
            if not isinstance(measurement, dict) or not MEASUREMENT_FIELDS <= set(measurement):
                raise Refused("LEARNING_MEASUREMENT_INVALID")
            run = measurement["native_run_id"]
            consumer = measurement["consumer_id"]
            at = measurement["started_at"]
            exposures = measurement["lesson_exposure_ids"]
            if (measurement["condition"] != condition or not isinstance(run, str) or not run
                    or not isinstance(consumer, str) or not consumer
                    or any(type(measurement[k]) is not bool for k in QUALITY)
                    or not isinstance(exposures, list) or any(not isinstance(e, str) or not e for e in exposures)
                    or len(set(exposures)) != len(exposures)):
                raise Refused("LEARNING_MEASUREMENT_INVALID")
            if type(at) not in (int, float) or not math.isfinite(at) or at < started:
                raise Refused("LEARNING_CHRONOLOGY_INVALID")
            if run in seen_runs:
                raise Refused("LEARNING_NATIVE_RUN_REUSED")
            seen_runs.add(run)
            if consumer in seen_consumers:
                raise Refused("LEARNING_CONSUMER_REUSED")
            seen_consumers.add(consumer)
            if condition == "baseline" and exposures:
                raise Refused("LEARNING_BASELINE_EXPOSED")
            if lesson_store is None:
                incomplete.append({"condition": condition, "case_id": r["case_id"], "reason": "LESSON_LEDGER_NOT_VERIFIED"})
            else:
                recorded = {receipt for receipt, _ in lesson_store.exposure_records(consumer)}
                if condition == "baseline" and recorded:
                    raise Refused("LEARNING_BASELINE_EXPOSED")
                if recorded != set(exposures):
                    raise Refused("LEARNING_EXPOSURE_RECEIPTS_MISMATCH")
        return {r["case_id"]: r for r in rows}

    a, b = normalized(baseline, "baseline"), normalized(memory, "memory")
    regressions = [i for i in ids if a[i]["independent_pass"] and not b[i]["independent_pass"]]
    accuracy_a = sum(r["independent_pass"] for r in a.values()) / len(ids)
    accuracy_b = sum(r["independent_pass"] for r in b.values()) / len(ids)
    costs = {
        k: {"baseline": sum(r["costs"][k] for r in a.values()), "memory": sum(r["costs"][k] for r in b.values())} for k in COSTS
    }
    quality_findings = {
        flag: {"baseline": [i for i in ids if (a[i].get("measurement") or {}).get(flag) is True],
               "memory": [i for i in ids if (b[i].get("measurement") or {}).get(flag) is True]}
        for flag in QUALITY
    }
    quality_regressed = bool(regressions) or any(facts["memory"] for facts in quality_findings.values())
    if not any((r.get("measurement") or {}).get("lesson_exposure_ids") for r in b.values()):
        incomplete.append({"condition": "memory", "reason": "NO_BOUND_LESSON_EXPOSURE"})
    improved = (
        accuracy_b > accuracy_a
        or accuracy_b == accuracy_a and accuracy_b > 0
        and costs["product_tokens"]["memory"]
        + costs["curation_tokens"]["memory"]
        + costs["retrieval_tokens"]["memory"]
        + costs["validation_tokens"]["memory"]
        < sum(costs[k]["baseline"] for k in COSTS[:4])
    )
    if quality_regressed:
        status = "QUALITY_REGRESSION"
    elif incomplete:
        status = "INSUFFICIENT_EVIDENCE"
    else:
        status = "MEASURED_BENEFIT" if improved else "NO_MEASURED_BENEFIT"
    return {
        "denominator": len(ids),
        "baseline_accuracy": accuracy_a,
        "memory_accuracy": accuracy_b,
        "regressions": regressions,
        "all_costs": costs,
        "quality_findings": quality_findings,
        "evidence_gaps": incomplete,
        "status": status,
        "benefit_demonstrated": status == "MEASURED_BENEFIT",
        "individual_run_monotonicity_claim": False,
    }
