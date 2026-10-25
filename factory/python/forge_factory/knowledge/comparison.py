"""Chronological, holdout-isolated learning comparisons; all learning costs count."""

from __future__ import annotations

from ..afo.durable import Refused, digest

COSTS = ("product_tokens", "retrieval_tokens", "curation_tokens", "validation_tokens", "wall_seconds", "energy_joules")


def compare(manifest, baseline, memory):
    ids = manifest["evaluation_ids"]
    if not ids or len(set(ids)) != len(ids) or set(ids) & set(manifest["learning_ids"]):
        raise Refused("LEARNING_HOLDOUT_LEAKAGE")
    if manifest["learning_cutoff"] >= manifest["evaluation_start"]:
        raise Refused("LEARNING_CHRONOLOGY_INVALID")

    def normalized(rows):
        if len(rows) != len(ids) or {r["case_id"] for r in rows} != set(ids):
            raise Refused("COMPARISON_DENOMINATOR_CHANGED")
        for r in rows:
            if r["configuration_sha256"] != manifest["configuration_sha256"] or r["manifest_sha256"] != digest(manifest):
                raise Refused("COMPARISON_IDENTITY_CHANGED")
            if any(type(r["costs"].get(k)) not in (int, float) or r["costs"][k] < 0 for k in COSTS):
                raise Refused("LEARNING_OVERHEAD_UNKNOWN")
        return {r["case_id"]: r for r in rows}

    a, b = normalized(baseline), normalized(memory)
    regressions = [i for i in ids if a[i]["independent_pass"] and not b[i]["independent_pass"]]
    accuracy_a = sum(r["independent_pass"] for r in a.values()) / len(ids)
    accuracy_b = sum(r["independent_pass"] for r in b.values()) / len(ids)
    costs = {
        k: {"baseline": sum(r["costs"][k] for r in a.values()), "memory": sum(r["costs"][k] for r in b.values())} for k in COSTS
    }
    improved = (
        accuracy_b > accuracy_a
        or accuracy_b == accuracy_a
        and costs["product_tokens"]["memory"]
        + costs["curation_tokens"]["memory"]
        + costs["retrieval_tokens"]["memory"]
        + costs["validation_tokens"]["memory"]
        < sum(costs[k]["baseline"] for k in COSTS[:4])
    )
    return {
        "denominator": len(ids),
        "baseline_accuracy": accuracy_a,
        "memory_accuracy": accuracy_b,
        "regressions": regressions,
        "all_costs": costs,
        "benefit_demonstrated": improved and not regressions,
        "individual_run_monotonicity_claim": False,
    }
