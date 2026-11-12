"""Offline reporting must retain failed/missing trials and reject evidence swaps."""

import copy
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

TOOL = Path(__file__).resolve().parents[2] / "qualification/014/summarize_delivery_cohort.py"
SPEC = importlib.util.spec_from_file_location("delivery_cohort_summary", TOOL)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def write(path, value):
    raw = json.dumps(value).encode()
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()


@pytest.fixture
def cohort(tmp_path):
    data = {"trials": 3, "items": [{"order_id": f"order-{i}", "request_id": f"trial-{i}"} for i in range(3)],
            "source_revision": "a" * 40, "auditor_revision": "b" * 40, "deadline_utc": "2026-10-31T07:57:59Z"}
    path, sha = write(tmp_path / "cohort.json", data)
    audit = {"schema": "forge-c/delivery-first-fresh-trial-audit/1", "order_id": "order-0",
             "trial_request_id": "trial-0", "native_id": "native-0", "cohort_sha256": sha,
             "source_revision": data["source_revision"], "auditor_revision": data["auditor_revision"],
             "deadline_utc": data["deadline_utc"], "result": "FUNCTIONAL_MILESTONE_PASS",
             "scope": "ONLY_PREREGISTERED_CRC_IDR_TWO_FUNCTIONS", "model_calls_by_auditor": 0,
             "candidate_execution_by_auditor": False, "release_eligibility": "BLOCKED", "gap_count": 16,
             "conditions": {str(i): {"status": "PASS", "evidence_refs": [{"sha256": "c" * 64}]}
                            for i in range(1, 10)}}
    return path, sha, audit


def test_missing_and_failed_trials_never_disappear_from_denominator(cohort, tmp_path):
    path, sha, audit = cohort
    empty = MODULE.summarize(path, sha, [])
    assert empty["qualified"] == 0 and empty["denominator"] == 3
    first = write(tmp_path / "first.json", audit)
    failed = {**audit, "order_id": "order-1", "trial_request_id": "trial-1", "native_id": "native-1",
              "result": "NOT_PROVEN", "conditions": {}}
    result = MODULE.summarize(path, sha, [first, write(tmp_path / "failed.json", failed)])
    assert result["qualified"] == 1 and result["denominator"] == 3 and not result["all_frozen_trials_qualified"]
    assert [r["audit_status"] for r in result["trials"]] == ["FUNCTIONAL_MILESTONE_PASS", "NOT_PROVEN", "MISSING"]
    assert result["trials"][0]["release_eligibility"] == "BLOCKED"
    assert result["trials"][0]["automatic_factory_handoff"] == "UNKNOWN"
    assert result["runtime_effects"] is result["candidate_execution"] is False and result["model_calls"] == 0


@pytest.mark.parametrize("field,value,code", [
    ("schema", "model-self-assessment", "NOT_EXTERNAL"),
    ("order_id", "unregistered", "OUTSIDE_FROZEN"),
    ("trial_request_id", "trial-other", "OUTSIDE_FROZEN"),
    ("cohort_sha256", "0" * 64, "COMPARABILITY"),
    ("source_revision", "0" * 40, "COMPARABILITY"),
    ("auditor_revision", "0" * 40, "COMPARABILITY"),
    ("deadline_utc", "2099-01-01T00:00:00Z", "COMPARABILITY"),
    ("conditions", {}, "INCOMPLETE"),
    ("scope", "ALL_DRIVERS", "WRONG_SCOPE"),
    ("model_calls_by_auditor", 1, "INCOMPLETE"),
    ("candidate_execution_by_auditor", True, "INCOMPLETE"),
])
def test_hash_valid_but_wrong_trial_or_pass_claim_is_rejected(cohort, tmp_path, field, value, code):
    path, sha, audit = cohort
    audit[field] = value
    with pytest.raises(ValueError, match=code):
        MODULE.summarize(path, sha, [write(tmp_path / "bad.json", audit)])


@pytest.mark.parametrize("kind", ["audit-bytes", "cohort-bytes", "duplicate-order", "reused-native", "missing-evidence"])
def test_tamper_duplication_and_missing_support_are_rejected(cohort, tmp_path, kind):
    path, sha, audit = cohort
    first = write(tmp_path / "first.json", audit)
    if kind.endswith("bytes"):
        changed = first[0] if kind == "audit-bytes" else path
        changed.write_bytes(changed.read_bytes() + b" ")
        with pytest.raises(ValueError, match="HASH_MISMATCH"):
            MODULE.summarize(path, sha, [first])
        return
    if kind == "missing-evidence":
        audit["conditions"]["9"]["evidence_refs"] = []
        with pytest.raises(ValueError, match="INCOMPLETE"):
            MODULE.summarize(path, sha, [write(tmp_path / "bad.json", audit)])
        return
    second = copy.deepcopy(audit)
    if kind == "reused-native":
        second.update(order_id="order-1", trial_request_id="trial-1")
    with pytest.raises(ValueError, match="DUPLICATE_TRIAL_OR_NATIVE"):
        MODULE.summarize(path, sha, [first, write(tmp_path / "second.json", second)])


def test_all_three_requires_distinct_frozen_trials_and_cli_never_overwrites(cohort, tmp_path):
    path, sha, audit = cohort
    refs = []
    for i in range(3):
        row = {**audit, "order_id": f"order-{i}", "trial_request_id": f"trial-{i}", "native_id": f"native-{i}"}
        refs.append(write(tmp_path / f"audit-{i}.json", row))
    result = MODULE.summarize(path, sha, refs)
    assert result["qualified"] == result["denominator"] == 3 and result["all_frozen_trials_qualified"]
    assert all(row["release_eligibility"] == "BLOCKED" for row in result["trials"])
    out = tmp_path / "new-summary.json"
    cmd = [sys.executable, str(TOOL), "--cohort", str(path), "--cohort-sha256", sha, "--out", str(out)]
    for p, digest in refs:
        cmd.extend(["--audit", str(p), digest])
    first = subprocess.run(cmd, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr
    saved = out.read_bytes()
    second = subprocess.run(cmd, capture_output=True, text=True)
    assert second.returncode != 0 and "FileExistsError" in second.stderr and out.read_bytes() == saved
