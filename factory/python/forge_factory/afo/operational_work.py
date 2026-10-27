"""Read-only operational work verification using existing native/audit evidence.

No model, scheduler, database or authority is created here. Product qualification
owns the independent oracle; the external observer owns captured liveness facts.
"""

from __future__ import annotations

from pathlib import Path

from ..common import sha256_file
from . import fault_observer as observer
from . import qualification_capture, queue
from .durable import Refused, digest, immutable_json
from .qualification_capture import replay_product_row

SCHEMA = "forge-c/independent-operational-work/1"
PHASES = {f"SWE.{i}" for i in range(1, 7)}
TERMINAL = {"READY_FOR_OFFLINE_REVIEW", "BLOCKED", "CANCELLED", "FAILED"}


def work_plan(manifest, plan_ref):
    frozen = observer.plan(manifest, plan_ref)
    if any(
        frozen.get(key) != sha256_file(path)
        for key, path in (
            ("work_verifier_sha256", Path(__file__)),
            ("product_observer_sha256", Path(qualification_capture.__file__)),
            ("queue_reader_sha256", Path(queue.__file__)),
        )
    ):
        raise Refused("OPERATIONAL_WORK_VERIFIER_NOT_FROZEN")
    return frozen


def capture_product(manifest, plan_ref, trial, destination):
    """Export existing product observations without opening the runtime writer."""
    import zipfile

    from .diagnosis_packet import scoped_path
    from .qualification_capture import product_row
    from .queue import ReadSnapshot
    from .runtime import workspace_of

    frozen = work_plan(manifest, plan_ref)
    binding = manifest.get("jobs", {}).get(trial)
    if not isinstance(binding, dict) or not all(binding.get(k) for k in ("job_id", "mission_id", "order_id", "attempt_id")):
        raise Refused("CAMPAIGN_JOB_BINDING_MISSING")
    root = Path(frozen["data_root"]).resolve()
    with ReadSnapshot(frozen["database"], max_rows=frozen["max_rows"]) as store:
        from .execution_lifecycle import Executions

        execution = Executions(store).get(binding["job_id"])
        if not execution or execution["resource_lease"] != "RELEASED" or execution["execution_liveness"] != "QUIESCENT":
            raise Refused("OPERATIONAL_PRODUCT_EXECUTION_NOT_QUIESCENT")
        attempt = next((a for a in store.attempts(binding["order_id"]) if a["attempt_id"] == binding["attempt_id"]), None)
        if attempt is None:
            raise Refused("QUALIFICATION_ATTEMPT_UNPROVISIONED")
        ws = workspace_of(attempt)
        try:
            relative = ws.absolute().relative_to(root)
        except ValueError:
            raise Refused("OPERATIONAL_WORKSPACE_OUTSIDE_DATA_ROOT") from None
        ws = scoped_path(root, str(relative))
        # Bound the existing gate/package reader's inputs before invoking it.
        # No extraction, compiler, model, worker, gate rewrite or archive mutation.
        count, total = 0, 0
        for p in ws.rglob("*"):
            count += 1
            if p.is_symlink() or not (p.is_file() or p.is_dir()) or count > frozen["max_rows"]:
                raise Refused("OPERATIONAL_WORKSPACE_BOUND_EXCEEDED")
            if p.is_file():
                total += p.stat().st_size
            if total > observer.MAX_TRACE_BYTES:
                raise Refused("OPERATIONAL_WORKSPACE_BOUND_EXCEEDED")
        package = ws / ".forge-run/package.json"
        if package.is_file():
            rec = observer.read_json(package)
            archive = Path(rec.get("archive", ""))
            try:
                relative = archive.absolute().relative_to(root)
            except ValueError:
                raise Refused("OPERATIONAL_ARCHIVE_OUTSIDE_DATA_ROOT") from None
            archive = scoped_path(root, str(relative))
            if archive.is_file():
                if archive.stat().st_size > observer.MAX_TRACE_BYTES:
                    raise Refused("OPERATIONAL_ARCHIVE_BOUND_EXCEEDED")
                with zipfile.ZipFile(archive) as z:
                    if len(z.infolist()) > frozen["max_rows"] or z.getinfo("manifest.json").file_size > observer.MAX_BYTES:
                        raise Refused("OPERATIONAL_ARCHIVE_BOUND_EXCEEDED")
        row = product_row(store, manifest, trial, binding)
    immutable_json(observer.artifact(frozen, destination), row)
    return row


def evaluate(manifest, plan_ref, product_row_ref, sample_refs, destination=None):
    """Recompute a work verdict; schema labels or success flags are not oracles."""
    frozen = work_plan(manifest, plan_ref)
    row = observer.bound_json(product_row_ref, path=observer.artifact(frozen, product_row_ref["path"]))
    row, binding = replay_product_row(manifest, row)
    samples = observer.load_samples(manifest, plan_ref, sample_refs)
    if any(s.get("complete") is not True for s in samples):
        raise Refused("OPERATIONAL_WORK_OBSERVATION_INCOMPLETE")
    native = row.get("native_run_id")
    if not isinstance(native, str) or not native or row.get("order_state") not in TERMINAL:
        raise Refused("OPERATIONAL_WORK_NOT_NATIVE_TERMINAL")
    order_id = binding["order_id"]
    matches = []
    for sample in samples:
        ledger = sample["ledger"]
        orders = [r for r in ledger["orders"] if r["order_id"] == order_id]
        attempts = [r for r in ledger["attempts"] if r["order_id"] == order_id]
        executions = [r for r in ledger["afo_execution_liveness"] if r["job_id"] == binding["job_id"]]
        if not orders or not attempts or not executions:
            continue
        if len(orders) != 1 or len(executions) != 1 or any(type(r.get("attempt_seq")) is not int for r in attempts):
            raise Refused("OPERATIONAL_WORK_IDENTITY_AMBIGUOUS")
        latest = max(attempts, key=lambda r: r["attempt_seq"])
        execution = executions[0]
        requests = [r for r in ledger["afo_request_ledger"] if r["job_id"] == binding["job_id"]]
        if (
            orders[0]["state"] == row["order_state"]
            and orders[0].get("authorization_id")
            and latest["attempt_id"] == binding["attempt_id"]
            and latest["fabro_run_id"] == native
            and latest["state"] in {"SUCCEEDED", "FAILED", "CANCELLED"}
            and execution["mission_id"] == binding["mission_id"]
            and execution["native_run_ids"] == [native]
            and execution["launch_nonce"] == row["execution"].get("launch_nonce")
            and execution["execution_liveness"] == "QUIESCENT"
            and execution["resource_lease"] == "RELEASED"
            and requests
            and all(r["state"] == "QUIESCENT" and r["mission_id"] == binding["mission_id"] for r in requests)
        ):
            matches.append(sample)
    captured = bool(matches)
    ready = row["order_state"] == "READY_FOR_OFFLINE_REVIEW"
    gates = row.get("gates") or {}
    ready_consistent = (
        row.get("sealed_ready") is True
        and row.get("native_all_six_gates") is True
        and set(gates) == PHASES
        and all(v == "PASS" for v in gates.values())
        and (row.get("package_verdict") or {}).get("verdict") == "READY_FOR_OFFLINE_REVIEW"
        and bool(row.get("package_sha256"))
    )
    audited = row.get("qualification_status") == "AUDITED"
    false_ready = row.get("false_ready") if audited else None
    if ready and not ready_consistent:
        false_ready = True  # a native READY contradicting its gate/package evidence
    verified = (
        captured
        and audited
        and false_ready is False
        and (row.get("required_evidence_complete") is True or (not ready and row.get("native_outcome_verified") is True))
        and (not ready or ready_consistent)
    )
    result = {
        "schema": SCHEMA,
        "manifest_sha256": digest(manifest),
        "plan_ref": plan_ref,
        "product_row_ref": product_row_ref,
        "sample_refs": sample_refs,
        "order_id": order_id,
        "attempt_id": binding["attempt_id"],
        "job_id": binding["job_id"],
        "mission_id": binding["mission_id"],
        "native_run_id": native,
        "order_state": row["order_state"],
        "observed_from": samples[0]["wall"],
        "observed_until": samples[-1]["wall"],
        "native_terminal_observed_at": matches[0]["wall"] if matches else None,
        "native_quiescence_captured": captured,
        "independent_audit": row.get("independent_audit"),
        "false_ready": false_ready,
        "independently_verified": verified,
        "status": "VERIFIED" if verified else "FAIL" if false_ready is True else "INCOMPLETE",
        "product_success": bool(verified and ready),
    }
    if destination is not None:
        immutable_json(observer.artifact(frozen, destination), result)
    return result


def verify(manifest, record):
    if record.get("schema") != SCHEMA:
        raise Refused("INDEPENDENT_OPERATIONAL_WORK_REQUIRED")
    actual = evaluate(manifest, record["plan_ref"], record["product_row_ref"], record["sample_refs"])
    if actual != record:
        raise Refused("OPERATIONAL_WORK_VERDICT_CHANGED")
    return actual


def ready_verdict(samples, work):
    """READY claims need corresponding independently verified native work."""
    orders = set()
    for sample in samples:
        for row in sample["ledger"]["orders"]:
            if row["state"] != "READY_FOR_OFFLINE_REVIEW":
                continue
            attempts = [r for r in sample["ledger"].get("attempts", []) if r["order_id"] == row["order_id"]]
            if not attempts or any(type(r.get("attempt_seq")) is not int for r in attempts):
                return None
            latest = max(attempts, key=lambda r: r["attempt_seq"])
            orders.add((row["order_id"], latest["attempt_id"], latest["fabro_run_id"]))
    if any(r["false_ready"] is True for r in work):
        return True
    verified = {
        (r["order_id"], r["attempt_id"], r["native_run_id"]) for r in work if r["independently_verified"] and r["product_success"]
    }
    return False if orders <= verified else None
