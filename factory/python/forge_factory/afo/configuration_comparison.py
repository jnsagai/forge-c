"""DA-T028: replay recorded controlled comparisons; never dispatch or select a model.

Use the existing qualification identities, frozen cases, independent audit producer
and comparison-factor rules. Missing native measurements remain NOT_RUN/INCOMPLETE.
RCC success is deliberately not a prerequisite. This report grants no authority.
"""

from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path

from ..lrtx.role_capability import key
from . import fault_observer as O
from . import qualification as Q
from . import qualification_capture as C
from .durable import Refused, digest, immutable_json

CONTROLS = {"prompts", "oracles", "workload", "admission", "measurement", "quality_gates"}
COSTS = ("input_tokens", "output_tokens", "learning_tokens", "wall_seconds", "learning_wall_seconds")
BOOL_FACTS = ("useful_plan", "false_acceptance", "false_rejection", "critical_defect_missed")


def validate_plan(plan):
    if (
        not isinstance(plan, dict)
        or plan.get("schema") != "forge-c/configuration-comparison-plan/1"
        or plan.get("comparison_factor") not in Q.COMPARISON_FACTORS
        or not isinstance(plan.get("controls"), dict)
        or set(plan["controls"]) != CONTROLS
        or not isinstance(plan.get("case_ids"), list)
        or not plan["case_ids"]
        or len(plan["case_ids"]) > 10000
        or any(not isinstance(v, str) or not v or len(v) > 256 for v in plan["case_ids"])
        or len(set(plan["case_ids"])) != len(plan["case_ids"])
        or type(plan.get("registered_at")) not in (int, float)
        or not math.isfinite(plan["registered_at"])
    ):
        raise Refused("COMPARISON_PREREGISTRATION_INVALID")
    for identity in ("baseline_identity", "candidate_identity"):
        key(plan[identity])
    # Read and verify every frozen common control, not supplied equality flags.
    total = 0
    for ref in plan["controls"].values():
        raw = O.read_bytes(ref["path"], min(O.MAX_BYTES, O.MAX_TRACE_BYTES - total))
        total += len(raw)
        if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
            raise Refused("COMPARISON_CONTROL_CHANGED")
    Q.comparison_identity(plan["comparison_factor"], plan["baseline_identity"], plan["candidate_identity"])
    return digest(plan)


def _campaign(plan, bundle, identity, *, preregistered=False):
    manifest = O.bound_json(bundle["manifest_ref"])
    sha = Q.validate(manifest)
    if manifest["identity"] != identity or manifest.get("execution_host") not in ("omniverse", "omniverse2"):
        raise Refused("COMPARISON_EFFECTIVE_IDENTITY_CHANGED")
    if preregistered and (bundle.get("plan_ref") not in manifest["inputs"] or O.bound_json(bundle["plan_ref"]) != plan):
        raise Refused("COMPARISON_CANDIDATE_PLAN_NOT_FROZEN")
    for ref in plan["controls"].values():
        if ref not in manifest["inputs"]:
            raise Refused("COMPARISON_CONTROL_NOT_FROZEN")
    if Q.protocol_like(manifest["stage"]):
        expected = Q.frozen_trials(manifest["cases"])
    elif manifest["stage"] == "benchmark":
        expected = [c["trial_id"] for c in manifest["product_cases"]]
    else:
        raise Refused("COMPARISON_STAGE_NOT_SUPPORTED")
    if expected != plan["case_ids"]:
        raise Refused("COMPARISON_DENOMINATOR_CHANGED")
    refs = bundle.get("result_refs")
    if not isinstance(refs, list) or len(refs) > len(expected):
        raise Refused("COMPARISON_RESULT_COUNT_INVALID")
    rows, budget = [], O.MAX_TRACE_BYTES
    for ref in refs:
        raw = O.read_bytes(ref["path"], min(O.MAX_BYTES, max(0, budget)))
        budget -= len(raw)
        if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
            raise Refused("COMPARISON_RESULT_CHANGED")
        rows.append(O.strict_json(raw, O.MAX_BYTES))
    ids = [r["trial_id"] for r in rows]
    if len(set(ids)) != len(ids) or not set(ids) <= set(expected):
        raise Refused("COMPARISON_DENOMINATOR_CHANGED")
    missing = [i for i in expected if i not in ids]
    costs = dict.fromkeys(COSTS, 0)
    metrics = {k: 0 for k in BOOL_FACTS}
    metrics.update(independently_closed_defects=0, accepted_work_orders=0, failed_or_blocked=0)
    native, unknown, closed = [], [], set()
    for row in rows:
        if row.get("manifest_sha256") != sha:
            raise Refused("COMPARISON_RESULT_UNBOUND")
        audit = C.independent_audit(None, manifest, row["trial_id"], row)
        if audit is None:
            unknown.append({"trial_id": row["trial_id"], "reason": "INDEPENDENT_AUDIT_MISSING"})
            continue
        facts = audit["observations"]
        measurement = facts.get("comparison_measurement")
        if not isinstance(measurement, dict):
            unknown.append({"trial_id": row["trial_id"], "reason": "INDEPENDENT_MEASUREMENT_MISSING"})
            continue
        settings_ref = measurement.get("effective_settings_ref")
        if settings_ref is None:
            unknown.append({"trial_id": row["trial_id"], "reason": "OBSERVED_EFFECTIVE_SETTINGS_MISSING"})
            continue
        if settings_ref not in audit["oracle_refs"]:
            raise Refused("COMPARISON_EFFECTIVE_SETTINGS_NOT_AUDITED")
        settings = O.bound_json(settings_ref)
        if settings.get("identity") != identity or settings.get("native_run_id") != row.get("native_run_id"):
            raise Refused("COMPARISON_OBSERVED_SETTINGS_CHANGED")
        not_started = (row.get("execution") or {}).get("execution_liveness") == "NOT_STARTED" and row.get("request_count") == 0
        if (
            any(type(measurement.get(k)) is not int or not 0 <= measurement[k] <= 2**63 - 1 for k in COSTS[:3])
            or any(
                type(measurement.get(k)) not in (int, float)
                or not math.isfinite(measurement[k])
                or not 0 <= measurement[k] <= 10**12
                for k in COSTS[3:]
            )
            or any(type(measurement.get(k)) is not bool for k in BOOL_FACTS)
            or type(measurement.get("accepted_work_order")) is not bool
            or not isinstance(measurement.get("closed_defect_ids"), list)
            or any(not isinstance(d, str) or not d for d in measurement["closed_defect_ids"])
            or type(measurement.get("started_at")) not in (float, int)
            or not math.isfinite(measurement["started_at"])
            or (not not_started and (not isinstance(row.get("native_run_id"), str) or not row["native_run_id"]))
        ):
            raise Refused("COMPARISON_MEASUREMENT_INVALID")
        if measurement.get("includes_all_attempts_and_learning") is not True:
            unknown.append({"trial_id": row["trial_id"], "reason": "COMPLETE_COST_ACCOUNTING_MISSING"})
            continue
        if row.get("reported_tokens") != sum(measurement[k] for k in COSTS[:3]):
            unknown.append({"trial_id": row["trial_id"], "reason": "NATIVE_TOKEN_ACCOUNTING_MISMATCH_OR_UNKNOWN"})
            continue
        if identity == plan["candidate_identity"] and measurement["started_at"] < plan["registered_at"]:
            raise Refused("COMPARISON_CANDIDATE_NOT_PREREGISTERED")
        # Every recorded outcome, including a failed/blocked attempt, contributes cost.
        for name in COSTS:
            costs[name] += measurement[name]
        for name in BOOL_FACTS:
            metrics[name] += int(measurement[name])
        accepted = measurement["accepted_work_order"]
        metrics["accepted_work_orders"] += accepted
        metrics["failed_or_blocked"] += not accepted
        closed.update(measurement["closed_defect_ids"])
        if row.get("native_run_id"):
            native.append(row["native_run_id"])
    metrics["independently_closed_defects"] = len(closed)
    accepted = metrics["accepted_work_orders"]
    total_tokens = sum(costs[k] for k in ("input_tokens", "output_tokens", "learning_tokens"))
    total_wall = costs["wall_seconds"] + costs["learning_wall_seconds"]
    return {
        "manifest_ref": bundle["manifest_ref"],
        "identity": identity,
        "source_revision": manifest["source_revision"],
        "stage": manifest["stage"],
        "quality_criteria_sha256": digest(manifest["criteria"]),
        "frozen_cases_sha256": digest(
            manifest["cases"]
            if Q.protocol_like(manifest["stage"])
            else [{k: v for k, v in case.items() if k not in ("model", "profile")} for case in manifest["product_cases"]]
        ),
        "expected": len(expected),
        "recorded": len(rows),
        "missing": missing,
        "unknown": unknown,
        "native_run_ids": native,
        "metrics": metrics,
        "costs": costs,
        "known_subset_tokens": total_tokens,
        "known_subset_wall_seconds": total_wall,
        "total_tokens": total_tokens if not missing and not unknown else None,
        "total_wall_seconds": total_wall if not missing and not unknown else None,
        "tokens_per_accepted_work_order": total_tokens / accepted if accepted and not unknown and not missing else None,
        "seconds_per_accepted_work_order": total_wall / accepted if accepted and not unknown and not missing else None,
        # Completion speed includes prompt processing, retries and learning. It
        # must never be labelled backend decode throughput.
        "end_to_end_output_tokens_per_second": costs["output_tokens"] / total_wall
        if total_wall > 0 and not missing and not unknown else None,
        "backend_decode_tokens_per_second": None,
        "backend_decode_timing_status": "NOT_CAPTURED_BY_THIS_REPORT; use separately correlated native timings",
        "complete": not missing and not unknown and bool(native),
    }


def report(plan, baseline=None, candidate=None):
    sha = validate_plan(plan)
    result = {
        "schema": "forge-c/configuration-comparison-report/1",
        "plan_sha256": sha,
        "comparison_factor": plan["comparison_factor"],
        "status": "NOT_RUN",
        "blockers": [],
        "baseline": None,
        "candidate": None,
        "rcc_success_prerequisite": False,
        "automatic_selection": False,
        "automatic_deployment": False,
        "product_success": "SEPARATE_BENCHMARK",
        "learning_benefit": "SEPARATE_COMPARISON",
        "operational_availability": "SEPARATE_CAMPAIGN",
        "recommendation": "INSUFFICIENT_COMPARABLE_EVIDENCE",
    }
    for lane, bundle, identity in (
        ("baseline", baseline, plan["baseline_identity"]),
        ("candidate", candidate, plan["candidate_identity"]),
    ):
        if bundle is None:
            result["blockers"].append(lane.upper() + "_MEASUREMENT_NOT_RUN")
        else:
            result[lane] = _campaign(plan, bundle, identity, preregistered=lane == "candidate")
            if not result[lane]["complete"]:
                result["blockers"].append(lane.upper() + "_MEASUREMENTS_INCOMPLETE")
    if baseline is not None and candidate is not None:
        for field in ("source_revision", "stage", "frozen_cases_sha256", "quality_criteria_sha256"):
            if result["baseline"][field] != result["candidate"][field]:
                raise Refused("COMPARISON_FROZEN_CASES_OR_RUNTIME_CHANGED")
        result["status"] = "INCOMPLETE" if result["blockers"] else "MEASURED"
        if not result["blockers"]:
            a, b = result["baseline"], result["candidate"]
            regressions = [
                name
                for name in ("false_acceptance", "false_rejection", "critical_defect_missed")
                if b["metrics"][name] > a["metrics"][name]
            ]
            regressions += [
                name
                for name in ("useful_plan", "independently_closed_defects", "accepted_work_orders")
                if b["metrics"][name] < a["metrics"][name]
            ]
            result["quality_regressions"] = regressions
            result["recommendation"] = "REJECT_QUALITY_REGRESSION" if regressions else "REVIEW_MEASURED_RESULTS"
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--plan", required=True, type=Path)
    ap.add_argument("--baseline", type=Path, help="JSON bundle of frozen manifest_ref/result_refs")
    ap.add_argument("--candidate", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    result = report(
        O.read_json(args.plan),
        O.read_json(args.baseline) if args.baseline else None,
        O.read_json(args.candidate) if args.candidate else None,
    )
    immutable_json(args.out, result)
    return 0 if result["status"] == "MEASURED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
