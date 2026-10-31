"""Recompute descriptive paired timing from saved numeric meters; no model calls."""
from pathlib import Path
import hashlib
import json


def analyze(root):
    cohorts = {}
    for effort in ("xhigh", "medium"):
        rows = {}
        for path in sorted(root.glob(effort + "-*.json")):
            row = json.loads(path.read_text())
            if row.get("schema") != "forge-c/reasoning-speed-trial/1":
                continue
            key = row["trial_id"]
            assert key not in rows, "Duplicate trial meter"
            assert row["effort"] == effort
            rows[key] = (row, {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        cohorts[effort] = rows
    assert len(cohorts["xhigh"]) == len(cohorts["medium"]) == 8
    assert cohorts["xhigh"].keys() == cohorts["medium"].keys()
    paired, excluded = [], []
    for key, (baseline, baseline_ref) in sorted(cohorts["xhigh"].items()):
        candidate, candidate_ref = cohorts["medium"][key]
        assert baseline["source_revision"] == candidate["source_revision"]
        assert baseline["expected"] == candidate["expected"]
        fields = ("gateway_total_seconds", "trial_wall_seconds", "completion_output_tokens")
        if not all(isinstance(row.get(f), (int, float)) and row[f] > 0
                   for row in (baseline, candidate) for f in fields):
            excluded.append({"trial_id": key, "reason": "MISSING_PAIRED_GENERATION_MEASUREMENT",
                             "baseline_ref": baseline_ref, "candidate_ref": candidate_ref})
            continue
        paired.append({"trial_id": key, "baseline_ref": baseline_ref, "candidate_ref": candidate_ref,
                       "xhigh": {f: baseline[f] for f in fields},
                       "medium": {f: candidate[f] for f in fields},
                       "gateway_speedup": baseline["gateway_total_seconds"] / candidate["gateway_total_seconds"],
                       "trial_wall_speedup": baseline["trial_wall_seconds"] / candidate["trial_wall_seconds"],
                       "baseline_observed": baseline["observed"], "candidate_observed": candidate["observed"],
                       "expected": baseline["expected"]})
    totals = {e: {f: sum(p[e][f] for p in paired) for f in fields} for e in cohorts}
    return {"schema": "forge-c/descriptive-paired-reasoning-timing/1",
            "frozen_trials_per_effort": 8, "paired_generated_trials": len(paired),
            "excluded_from_timing_only": excluded, "pairs": paired, "totals": totals,
            "gateway_speedup": totals["xhigh"]["gateway_total_seconds"] / totals["medium"]["gateway_total_seconds"],
            "trial_wall_speedup": totals["xhigh"]["trial_wall_seconds"] / totals["medium"]["trial_wall_seconds"],
            "limitations": ["Descriptive serial diagnosis pilot, not randomized or full-pipeline qualification",
                            "Original failures remain in eight-trial quality denominator",
                            "Completion output includes reasoning tokens; hidden content was not collected",
                            "Trial wall includes orchestration and verification, not initial model activation",
                            "Neither setting passed the protocol campaign; no production selection"]}


if __name__ == "__main__":
    print(json.dumps(analyze(Path(__file__).resolve().parent), indent=2))
