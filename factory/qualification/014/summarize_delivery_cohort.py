"""Summarize hash-pinned external trial audits; never qualify a job or grant release.

Missing trials stay in the frozen denominator. This reader trusts the explicitly
pinned external audit assertions, not model self-assessments or native status.
It performs no candidate execution, inference, dispatch or runtime mutation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def pinned_json(path: Path, expected: str) -> dict:
    raw = path.read_bytes()
    if len(expected) != 64 or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("INPUT_HASH_MISMATCH:" + str(path))
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("INPUT_NOT_OBJECT:" + str(path))
    return value


def summarize(cohort_path: Path, cohort_sha256: str, audits: list[tuple[Path, str]]) -> dict:
    cohort = pinned_json(cohort_path, cohort_sha256)
    items = cohort["items"]
    if not items or cohort["trials"] != len(items):
        raise ValueError("COHORT_DENOMINATOR_INVALID")
    by_order = {row["order_id"]: row for row in items}
    if len(by_order) != len(items) or len({row["request_id"] for row in items}) != len(items):
        raise ValueError("COHORT_DUPLICATE_TRIAL")
    rows = {key: {"order_id": key, "request_id": row["request_id"], "functional_status": "NOT_QUALIFIED",
                  "audit_status": "MISSING", "release_eligibility": "UNKNOWN"} for key, row in by_order.items()}
    seen_orders, seen_natives = set(), set()
    for path, sha in audits:
        audit = pinned_json(path, sha)
        if audit.get("schema") != "forge-c/delivery-first-fresh-trial-audit/1":
            raise ValueError("NOT_EXTERNAL_FRESH_TRIAL_AUDIT")
        oid = audit["order_id"]
        if oid not in rows or audit["trial_request_id"] != by_order[oid]["request_id"]:
            raise ValueError("AUDIT_OUTSIDE_FROZEN_TRIAL")
        if oid in seen_orders or audit["native_id"] in seen_natives:
            raise ValueError("DUPLICATE_TRIAL_OR_NATIVE")
        seen_orders.add(oid)
        seen_natives.add(audit["native_id"])
        if (audit["cohort_sha256"] != cohort_sha256 or audit["source_revision"] != cohort["source_revision"]
                or audit["auditor_revision"] != cohort["auditor_revision"]
                or audit["deadline_utc"] != cohort["deadline_utc"]):
            raise ValueError("AUDIT_COMPARABILITY_BINDING_MISMATCH")
        passed = audit["result"] == "FUNCTIONAL_MILESTONE_PASS"
        if passed and (set(audit["conditions"]) != {str(i) for i in range(1, 10)}
                       or any(row.get("status") != "PASS" or not row.get("evidence_refs")
                              for row in audit["conditions"].values())
                       or audit.get("scope") != "ONLY_PREREGISTERED_CRC_IDR_TWO_FUNCTIONS"
                       or audit.get("model_calls_by_auditor") != 0
                       or audit.get("candidate_execution_by_auditor") is not False):
            raise ValueError("PASS_AUDIT_INCOMPLETE_OR_WRONG_SCOPE")
        rows[oid].update({"functional_status": "QUALIFIED_BY_PINNED_EXTERNAL_AUDIT" if passed else "NOT_QUALIFIED",
                          "audit_status": audit["result"], "audit": {"path": str(path), "sha256": sha},
                          "native_id": audit["native_id"], "archive": audit.get("archive"),
                          "candidate_hashes": audit.get("candidate_hashes"),
                          "release_eligibility": audit["release_eligibility"],
                          "gap_count": audit.get("gap_count"), "gates": audit.get("gates"),
                          "metrics": audit.get("metrics"),
                          "automatic_factory_handoff": audit.get("automatic_factory_handoff", "UNKNOWN")})
    ordered = [rows[item["order_id"]] for item in items]
    qualified = sum(row["functional_status"] == "QUALIFIED_BY_PINNED_EXTERNAL_AUDIT" for row in ordered)
    return {"schema": "forge-c/delivery-first-cohort-summary/1", "cohort_sha256": cohort_sha256,
            "source_revision": cohort["source_revision"], "auditor_revision": cohort["auditor_revision"],
            "deadline_utc": cohort["deadline_utc"], "denominator": len(items), "qualified": qualified,
            "all_frozen_trials_qualified": qualified == len(items), "trials": ordered,
            "basis": "HASH_PINNED_EXTERNAL_AUDIT_ASSERTIONS; NOT_REEXECUTION_OR_NEW_QUALIFICATION",
            "runtime_effects": False, "model_calls": 0, "candidate_execution": False,
            "limits": ["Does not independently reproduce external audits or measure missing interventions",
                       "Missing/failed/cancelled/unfinished trials remain in denominator",
                       "Functional yield does not grant release, LL/HAL, autonomy or learning benefit",
                       "No causal speed inference from stochastic/shared-resource trials"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--cohort-sha256", required=True)
    parser.add_argument("--audit", nargs=2, metavar=("JSON", "SHA256"), action="append", default=[])
    parser.add_argument("--out", type=Path, required=True, help="New output file; never overwrite a prior summary")
    args = parser.parse_args()
    result = summarize(args.cohort, args.cohort_sha256, [(Path(p), sha) for p, sha in args.audit])
    raw = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    with args.out.open("xb") as stream:
        stream.write(raw)
    print(json.dumps({"path": str(args.out), "sha256": hashlib.sha256(raw).hexdigest(),
                      "qualified": result["qualified"], "denominator": result["denominator"],
                      "all_frozen_trials_qualified": result["all_frozen_trials_qualified"], "runtime_effects": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
