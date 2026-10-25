#!/usr/bin/env python3
"""Check the dated evidence handoff only. This never qualifies a model or running factory."""
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "specs/014-durable-local-autonomy"


def main():
    rows = list(csv.DictReader((SPEC / "implementation-status.csv").open()))
    ledger = json.loads((ROOT / "evidence/014-durable-local-autonomy/implementation-status.json").read_text())
    assert len(rows) == 52 and rows == ledger["rows"]
    for column, prefix in [("requirement_id", "DA-FR-"), ("task_id", "DA-T"), ("acceptance_test_id", "DA-AT-")]:
        assert {r[column] for r in rows} == {f"{prefix}{i:03d}" for i in range(1, 53)}
    complete = set(ledger["completed_task_ids"])
    checked = set(re.findall(r"^- \[[xX]\] \*\*(DA-T\d{3})", (SPEC / "tasks.md").read_text(), re.M))
    assert checked <= complete  # before marking, checking evidence must already be possible
    for row in rows:
        assert row["source_revision"] == ledger["source_revision"]
        ref = ROOT / row["evidence"]
        if row["task_id"] == "DA-T030" and not ref.exists():
            continue  # the first documentation-only check produces this record
        record = json.loads(ref.read_text())
        if row["task_id"] in complete:
            assert row["implementation_status"] == "PASS_DETERMINISTIC"
            assert record["status"] == "PASS" and record["exit_code"] == 0
        for path_key, hash_key in [("log", "log_sha256"), ("report", "report_sha256")]:
            if path_key in record:
                assert hashlib.sha256((ROOT / record[path_key]).read_bytes()).hexdigest() == record[hash_key]
        if "junit" in record:
            j = record["junit"]
            assert hashlib.sha256((ROOT / j["path"]).read_bytes()).hexdigest() == j["sha256"]
    for axis in ["local_model_capability", "product_success", "learning_benefit", "operational_availability"]:
        assert ledger[axis] == "NOT_RUN"
    assert ledger["deployment"] == "NOT_ACTIVATED"
    assert ledger["rolling_30_day_slo"] == "NOT_DEMONSTRATED"
    print(json.dumps({"status": "PASS", "scope": "DOCUMENTATION_ONLY_NOT_RUNTIME",
                      "rows": len(rows), "supported_completed_tasks": len(complete),
                      "checked_tasks": len(checked), "source_revision": ledger["source_revision"]}))


if __name__ == "__main__":
    main()
