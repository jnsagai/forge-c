"""Collect one preregistered Delivery-First trial on its execution host.

Observation only: no candidate execution, inference, dispatch, service control or
milestone/release decision. Output is outside the product workspace. A terminal
native result is separate from request/execution quiescence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance-root", type=Path, required=True)
    parser.add_argument("--cohort-root", type=Path, required=True)
    parser.add_argument("--order-id", required=True)
    parser.add_argument("--api-url", default="http://127.0.0.1:32404")
    args = parser.parse_args()
    root = args.instance_root.resolve()
    cohort_path = args.cohort_root / "cohort.json"
    cohort_raw = cohort_path.read_bytes()
    cohort = json.loads(cohort_raw)
    binding = json.loads((root / "control/repeatability-20261031-v4b/admission-binding.json").read_text())
    if hashlib.sha256(cohort_raw).hexdigest() != binding["cohort_sha256"]:
        raise ValueError("OBSERVER_COHORT_BINDING_CHANGED")
    frozen = json.loads((args.cohort_root / "frozen-contract.json").read_text())
    if hashlib.sha256((args.cohort_root / "frozen-contract.json").read_bytes()).hexdigest() != cohort["frozen_contract_sha256"]:
        raise ValueError("OBSERVER_FROZEN_CONTRACT_CHANGED")
    allowed = {r["order_id"] for r in cohort["items"]}
    if args.order_id not in allowed:
        raise ValueError("ORDER_NOT_IN_FROZEN_COHORT")
    url = urlparse(args.api_url)
    if url.scheme != "http" or url.hostname != "127.0.0.1" or url.username or url.password:
        raise ValueError("OBSERVER_API_MUST_BE_LOCAL")
    os.environ.update(json.loads((root / "control/runtime-env-v6.json").read_text()))
    sys.path.insert(0, str(root / "source/factory/python"))
    from forge_factory import delivery_first
    from forge_factory.afo.durable import digest, immutable_json
    from forge_factory.common import sha256_file, utc_now
    from forge_factory.fabro.client import FabroClient, load_token, run_status
    from forge_factory.release.finalize import verify_archive

    source = subprocess.check_output(["git", "-C", str(root / "source"), "rev-parse", "HEAD"], text=True).strip()
    if source != cohort["source_revision"]:
        raise ValueError("OBSERVER_PRODUCER_SOURCE_CHANGED")
    with sqlite3.connect("file:" + str(root / "state/conductor/conductor.sqlite3") + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        order = db.execute(
            "SELECT order_id,state,terminal_reason FROM afo_work_orders WHERE order_id=?", (args.order_id,)
        ).fetchone()
        if order is None:
            raise ValueError("COHORT_ORDER_NOT_SUBMITTED")
        attempts = list(db.execute("SELECT attempt_id,record FROM afo_attempts WHERE order_id=? ORDER BY seq", (args.order_id,)))
        out = {
            "schema": "forge-c/delivery-first-cohort-observation/1", "at": utc_now(),
            "cohort_sha256": hashlib.sha256(cohort_raw).hexdigest(), "order": dict(order),
            "producer_source_revision": source, "read_only_product_workspace": True,
            "model_calls_by_observer": 0, "candidate_execution_by_observer": False,
            "milestone": "REQUIRES_EXTERNAL_AUDIT_NOT_INFERRED", "attempts": [],
        }
        with FabroClient(base_url=args.api_url, token=load_token(str(root / "fabro/storage")), timeout=15) as client:
            for row in attempts:
                attempt = json.loads(row["record"])
                ws = root / "state/workorders" / attempt["workspace_ref"].removeprefix("workorder:") / "workspace"
                if not ws.resolve().is_relative_to(root / "state/workorders") or ws.is_symlink():
                    raise ValueError("OBSERVER_WORKSPACE_ESCAPE")
                rid = attempt.get("fabro_run_id")
                jobs = [json.loads(r[0]) for r in db.execute("SELECT record FROM afo_product_jobs")]
                jobs = [j for j in jobs if j["order_id"] == args.order_id and j["attempt_id"] == row["attempt_id"]]
                if len(jobs) != 1:
                    raise ValueError("OBSERVER_PRODUCT_JOB_BINDING_UNKNOWN")
                job = jobs[0]
                manifest = json.loads((ws / ".forge-run/manifest.json").read_text())
                if manifest["factory_revision"]["commit"] != source:
                    raise ValueError("OBSERVER_WORKSPACE_SOURCE_CHANGED")
                cfg = delivery_first.contract(manifest)
                if cfg != frozen["delivery_first"] or manifest["inputs"] != frozen["inputs"]:
                    raise ValueError("OBSERVER_WORKSPACE_CONTRACT_CHANGED")
                paths = delivery_first.checked_paths(ws, cfg)
                current = {p: sha256_file(path) if path.is_file() else None for p, path in paths.items()}
                item = {
                    "attempt_id": row["attempt_id"], "native_id": rid, "workspace": str(ws), "job_id": job["job_id"],
                    "candidate_hashes": current,
                    "phase_files": {f"SWE.{i}": [
                        {"path": str(p.relative_to(ws)), "sha256": sha256_file(p), "bytes": p.stat().st_size}
                        for p in sorted((ws / f"workproducts/SWE.{i}").rglob("*")) if p.is_file() and not p.is_symlink()
                    ] for i in range(1, 7)},
                    "verifiers": [{"path": str(p.relative_to(ws)), "sha256": sha256_file(p), "result": json.loads(p.read_text())}
                                  for p in sorted((ws / ".forge-run/delivery-first").glob("attempt-*/result.json"))],
                    "request_states": [dict(r) for r in db.execute(
                        "SELECT state,COUNT(*) AS n FROM afo_request_ledger WHERE job_id=? GROUP BY state", (job["job_id"],))],
                    "execution": [json.loads(r[0]) for r in db.execute(
                        "SELECT record FROM afo_execution_liveness WHERE job_id=?", (job["job_id"],))],
                }
                # Do not export administrative nonces from the liveness record.
                item["execution"] = [{k: v.get(k) for k in (
                    "job_id", "execution_liveness", "resource_lease", "task_outcome", "native_run_ids", "quiescence_evidence_ref"
                )} for v in item["execution"]]
                initial = ws / ".forge-run/delivery-first/initial.json"
                item["initial_preflight"] = json.loads(initial.read_text()) if initial.is_file() else None
                if rid:
                    if (ws / ".forge-run/fabro_run_id").read_text().strip() != rid:
                        raise ValueError("OBSERVER_NATIVE_IDENTITY_CHANGED")
                    native = client.get_run(rid)
                    events = list(client.iter_events(rid))
                    item["native_status"] = run_status(native)
                    item["usage"] = client.usage(rid)
                    item["stage_outcomes"] = [{
                        "event": e["event"], "node": e.get("node_id"), "at": e.get("ts"),
                        "failure": (e.get("properties") or {}).get("failure")
                    } for e in events if e["event"] in {"stage.started", "stage.completed", "stage.failed"}]
                    item["external_steering_events"] = sum("steer" in e["event"] for e in events)
                    package_path = ws / ".forge-run/package.json"
                    terminal = item["native_status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "CANCELED", "DEAD"}
                    if package_path.is_file() and terminal:
                        package = json.loads(package_path.read_text())
                        archive = Path(package["archive"])
                        if not archive.resolve().is_relative_to(root / "archives") or archive.is_symlink():
                            raise ValueError("OBSERVER_ARCHIVE_ESCAPE")
                        if sha256_file(archive) != package["archive_sha256"]:
                            raise ValueError("OBSERVER_ARCHIVE_CHANGED")
                        item["package"] = {k: package.get(k) for k in (
                            "archive", "archive_sha256", "package_status", "gap_count", "gaps")}
                        item["archive_integrity"] = verify_archive(archive)
                        with zipfile.ZipFile(archive) as z:
                            report_raw = z.read("evidence/verification/delivery-first/report.json")
                            report = json.loads(report_raw)
                            item["packaged_report_sha256"] = hashlib.sha256(report_raw).hexdigest()
                            item["packaged_report"] = {k: report.get(k) for k in (
                                "factory_revision", "local_profile", "model_profile", "execution", "artifact_delivery",
                                "functional_verification", "process_qualification", "release_eligibility", "integrity_issues",
                                "authorship", "milestone", "metrics", "phases", "native_evidence", "unrun")}
                            item["archived_candidate_hashes"] = {
                                p: hashlib.sha256(z.read("evidence/" + p)).hexdigest() for p in current}
                            final_name = "evidence/verification/delivery-first/attempts/attempt-final/result.json"
                            item["archived_final_receipt_present"] = final_name in z.namelist()
                            if item["archived_final_receipt_present"]:
                                final_raw = z.read(final_name)
                                final = json.loads(final_raw)
                                item["archived_final_receipt"] = final
                                final_path = ws / ".forge-run/delivery-first/attempt-final/result.json"
                                item["archived_final_equals_live_bytes"] = final_raw == final_path.read_bytes()
                                item["archived_report_has_same_final_receipt"] = any(
                                    r == final for r in report.get("attempts", []))
                            item["archived_phase_hashes_match"] = all(
                                hashlib.sha256(z.read("evidence/" + p["path"])).hexdigest() == p["sha256"]
                                for rows in item["phase_files"].values() for p in rows)
                out["attempts"].append(item)
    target = root / "control/qualification-observations/cohort" / args.order_id / (digest(out) + ".json")
    immutable_json(target, out)
    print(json.dumps({
        "path": str(target), "sha256": sha256_file(target), "order": out["order"],
        "attempts": [{k: a.get(k) for k in ("native_id", "native_status", "candidate_hashes", "archive_integrity",
                                          "archived_final_receipt_present")} for a in out["attempts"]],
        "model_calls_by_observer": 0, "candidate_execution_by_observer": False, "milestone": out["milestone"],
    }))


if __name__ == "__main__":
    main()
