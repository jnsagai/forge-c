"""Read-only snapshot replay into a NEW offline SQLite copy; never a live migration command."""

from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from .durable import Refused, digest, immutable_json
from .mission_ledger import MissionLedger
from .queue import Store


def replay(dump_path, expected_sha256, copy_path, report_path):
    source, target = Path(dump_path), Path(copy_path)
    if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != expected_sha256:
        raise Refused("HISTORY_SNAPSHOT_CHANGED")
    if target.exists() or target.is_symlink() or source.resolve() == target.resolve():
        raise Refused("OFFLINE_COPY_MUST_BE_NEW")
    con = sqlite3.connect(target)
    try:
        con.executescript(source.read_text())
        names = [
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'afo_schema_version'"
            )
        ]
        before = {n: list(con.execute('SELECT * FROM "' + n.replace('"', '""') + '"')) for n in names}
        # Conductor migrations use their own version table, not SQLite's unrelated user_version.
        old_version = con.execute("SELECT MAX(version) FROM afo_schema_version").fetchone()[0] or 0
    finally:
        con.close()
    store = Store(target)
    with store.tx() as c:
        unchanged = {n: before[n] == [tuple(r) for r in c.execute('SELECT * FROM "' + n.replace('"', '""') + '"')] for n in names}
        version = c.execute("SELECT MAX(version) FROM afo_schema_version").fetchone()[0]
        attempts = [json.loads(r[0]) for r in c.execute("SELECT record FROM afo_attempts")]
        diagnoses = [json.loads(r[0]) for r in c.execute("SELECT record FROM afo_local_agent_jobs")]
        orders = [r[0] for r in c.execute("SELECT order_id FROM afo_work_orders")]
    if not all(unchanged.values()):
        raise Refused("LEGACY_SNAPSHOT_ROWS_MUTATED")
    ledger = MissionLedger(store)
    mission = "offline-historical-" + expected_sha256[:16]
    limits = {
        "max_attempts": 5,
        "max_jobs": 4,
        "max_requests": 32,
        "max_tokens": 64000,
        "max_tools": 32,
        "max_corrections": 1,
        "deadline": 1792918800,
    }
    ledger.register(
        mission, "offline-copy:" + expected_sha256, limits, "OFFLINE_RECONSTRUCTION_NOT_A_LIVE_GRANT", authorize=lambda *_: True
    )
    for order in orders:
        ledger.link(mission, order)
    native = sorted({a["fabro_run_id"] for a in attempts if a.get("fabro_run_id")})
    for run in native:
        for _ in range(2):
            ledger.execution(
                mission,
                "omniverse2:" + run,
                "PRODUCT",
                reserved_tokens=0,
                imported=True,
                evidence_refs=["snapshot:sha256:" + expected_sha256],
            )
    observed_diagnoses = []
    for job in diagnoses:
        run = job.get("run_id")
        if not run:
            continue
        reserved, reported = job["reserved_tokens"], job.get("reported_tokens")
        for _ in range(2):
            ledger.execution(
                mission,
                "omniverse2:" + run,
                "DIAGNOSIS",
                reserved_tokens=reserved,
                reported_tokens=reported,
                imported=True,
                evidence_refs=["snapshot:sha256:" + expected_sha256],
            )
        observed_diagnoses.append(
            {"native_run_id": run, "state": job["state"], "reserved_tokens": reserved, "reported_tokens": reported}
        )
    snapshot = ledger.snapshot(mission)
    try:
        ledger.execution(mission, "forbidden-continuation", "DIAGNOSIS", reserved_tokens=1)
    except Refused as exc:
        denial = exc.code
    else:
        raise Refused("HISTORY_CREATED_NEW_CAPACITY")
    report = {
        "schema": "forge-c/history-copy-qualification/1",
        "status": "PASS",
        "source_dump_sha256": expected_sha256,
        "original_source_mutated": False,
        "schema_before": old_version,
        "schema_after": version,
        "legacy_tables": {
            n: {"rows": len(before[n]), "rows_sha256": digest(before[n]), "unchanged": unchanged[n]} for n in names
        },
        "historical_attempt_rows": len(attempts),
        "unique_product_executions": len(native),
        "diagnoses": observed_diagnoses,
        "replayed_imports_per_identity": 2,
        "ledger": snapshot,
        "new_admission_denial": denial,
        "historical_v4_native_stop_cause": "UNKNOWN",
        "new_live_inference": False,
        "scope": "OFFLINE_COPY_ONLY_NOT_DEPLOYMENT_OR_AUTHORIZATION",
    }
    immutable_json(Path(report_path), report)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dump", type=Path, required=True)
    ap.add_argument("--sha256", required=True)
    ap.add_argument("--copy", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    a = ap.parse_args(argv)
    print(json.dumps(replay(a.dump, a.sha256, a.copy, a.report), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
