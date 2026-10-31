"""One-shot cohort intake through existing AFO. Requires a completed external M1 audit.

Run only on Omniverse, inside the existing holder's network/user namespace.
This is intake tooling, not a scheduler, source deployment or grant renewal.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--cohort-root", required=True, type=Path)
p.add_argument("--audit", required=True, type=Path)
p.add_argument("--audit-sha256", required=True)
args = p.parse_args()
E = Path("/mnt/data/forge-c/delivery-first-afo-014-20261030-v1")
Q = E / "source"
O = E / "control/delivery-first-afo-authority-20261031-v4b"
os.environ.update(json.loads((E / "control/runtime-env-v6.json").read_text()))
sys.path.insert(0, str(Q / "factory/python"))
from forge_factory.afo import authority, contracts, policy, product_role_trial
from forge_factory.afo.durable import digest, immutable_json, immutable_bytes
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.operations import Intent
from forge_factory.afo.queue import Store
from forge_factory.common import sha256_file, utc_now
from forge_factory.release.finalize import verify_archive

cohort_raw = (args.cohort_root / "cohort.json").read_bytes()
assert hashlib.sha256(cohort_raw).hexdigest() == "a14bfe74a0365a47360a630e09cdaec0338b10385ecb8be7a1b4d3389d18e759"
cohort = json.loads(cohort_raw)
assert sha256_file(args.audit) == args.audit_sha256
audit = json.loads(args.audit.read_text())
assert audit["schema"] == "forge-c/delivery-first-external-m1-audit/1"
assert audit["milestone"] == "FUNCTIONAL_MILESTONE_PASS"
assert set(audit["conditions"]) == {str(i) for i in range(1, 10)}
assert all(row["status"] == "PASS" and row["evidence_refs"] for row in audit["conditions"].values())
assert audit["native_id"] == cohort["prerequisite"]["native_id"]
assert audit["source_revision"] == cohort["source_revision"]
assert audit["auditor_revision"] == cohort["auditor_revision"]
assert audit["candidate_sha256"] == "9aa11db10b4547cc4f440f91e3d4e513f006906b83a1c1a77e26fbf9ebedf76e"
for ref in audit["remote_artifact_refs"]:
    path = Path(ref["path"])
    assert path.resolve().is_relative_to(E) and not path.is_symlink()
    assert sha256_file(path) == ref["sha256"]
archive = Path(audit["archive"]["path"])
assert archive.resolve().is_relative_to(E / "archives") and not archive.is_symlink()
assert sha256_file(archive) == audit["archive"]["sha256"]
assert verify_archive(archive)["integrity"] == "PASS"

scope = json.loads((O / "scope.json").read_text())
assert time.time() + 90 < scope["deadline_epoch"]
assert scope["deadline_utc"] == cohort["deadline_utc"] == "2026-10-31T07:57:59Z"
assert digest(scope) == cohort["scope_canonical_sha256"]
assert scope["mission_id"] == cohort["mission_id"]
assert subprocess.check_output(["git", "-C", str(Q), "rev-parse", "HEAD"], text=True).strip() == cohort["source_revision"]
assert not subprocess.check_output(["git", "-C", str(Q), "status", "--porcelain", "--untracked-files=no"], text=True).strip()
assert os.readlink("/proc/self/ns/net") == json.loads((E / "run/services.json").read_text())["netns"]
effective = policy.load()
assert effective.mode == "PILOT" and effective.sha256 == scope["policy_sha256"]
ref = json.loads((O / "trial-ref.json").read_text())
assert ref["sha256"] == cohort["role_trial_sha256"]
store = Store()
ledger = MissionLedger(store)
execution = Executions(store).get("afo-product-0fbf506c5889f9f7faa87f04")
assert execution["execution_liveness"] == "QUIESCENT"
assert execution["resource_lease"] == "RELEASED" and execution["quiescence_evidence_ref"]
before = ledger.snapshot(scope["mission_id"])
assert before["limits"] == scope["mission_limits"]
binding = {
    "schema": "forge-c/delivery-first-cohort-admission-binding/1",
    "cohort_sha256": hashlib.sha256(cohort_raw).hexdigest(),
    "m1_audit_ref": {"path": str(args.audit), "sha256": args.audit_sha256},
    "native_id": audit["native_id"],
    "archive": audit["archive"],
    "source_revision": cohort["source_revision"],
    "auditor_revision": cohort["auditor_revision"],
    "mission_id": scope["mission_id"],
    "deadline_utc": scope["deadline_utc"],
    "candidate_reuse": False,
    "release_policy": "UNCHANGED_STRICT",
}
binding_path = E / "control/repeatability-20261031-v4b/admission-binding.json"
immutable_json(binding_path, binding)
intent = Intent()
out = []
predeclared = {(x["request_id"], x["order_id"]) for x in scope["predeclared_orders"]}
for item in cohort["items"]:
    assert (item["request_id"], item["order_id"]) in predeclared
    raw = (args.cohort_root / item["launch_path"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == item["launch_file_sha256"]
    launch = json.loads(raw)
    assert launch["scope_sha256"] == digest(scope)
    assert launch["mission_id"] == scope["mission_id"] and launch["candidate_reuse"] is False
    assert launch["product_role_trial"] == ref
    assert launch["product_attempt_token_reservations"] == [scope["current_job_token_reservation"]]
    relative = ".forge-run/delivery-first-afo/launch-" + item["request_id"] + ".json"
    manifest = Q / relative
    immutable_bytes(manifest, raw)
    envelope = {
        "schema_version": "1.0", "request_id": item["request_id"],
        "tenant_scope": scope["tenant_scope"], "manifest_sha256": sha256_file(manifest),
        "input_manifest_ref": relative, "approved_by": "jefferson",
        "authorization_ref": scope["primary_authorization"], "driver_class": "LL",
        "target": "STM32N6 Cortex-M55 CRC IDR two-function development",
        "safety_scope": "QM DEVELOPMENT; NO SAFETY OR PRODUCTION RELEASE CLAIM",
        "model_profile": scope["model"], "submitted_utc": utc_now(), "priority": "NORMAL",
        "deadline_utc": scope["deadline_utc"], "git_revision": scope["source_revision"],
    }
    contracts.require("work-order", envelope)
    with intent.lock():
        assert time.time() + 90 < scope["deadline_epoch"]
        assert intent.read()["mode"] == "RUNNING" and intent.read()["epoch"] == 6
        job = {"order_id": item["order_id"], "profile": scope["profile"], "model": scope["model"],
               "model_digest": scope["model_digest"], "precision": "Q8_0",
               "factory_revision": {"commit": scope["source_revision"], "dirty": False}}
        ledger.link(scope["mission_id"], item["order_id"])
        oid, created = store.submit(
            envelope, repo=Q, max_queued=100,
            approve=lambda env: (authority.decide("submit_workorder", {
                "order_id": env["request_id"], "driver_class": "LL", "model": scope["model"]
            }, afo=effective).allow, "SIGNED_SCOPED_DEVELOPMENT"),
        )
        assert oid == item["order_id"]
        product_role_trial.authorized(ref, job, effective)
    row = {"request_id": item["request_id"], "order_id": oid, "created": created,
           "binding_sha256": digest(binding), "launch_sha256": item["launch_file_sha256"]}
    immutable_json(E / "control/repeatability-20261031-v4b" / (item["request_id"] + "-intake.json"),
                   {k: v for k, v in row.items() if k != "created"})
    out.append(row)
after = ledger.snapshot(scope["mission_id"])
assert after["limits"] == before["limits"] and after["charged_tokens"] >= before["charged_tokens"]
print(json.dumps({"at": utc_now(), "status": "EXISTING_AFO_INTAKE_COMPLETED",
                  "orders": out, "binding_ref": str(binding_path), "binding_sha256": digest(binding),
                  "mission_before": before, "mission_after": after,
                  "no_grant_change": True, "no_deployment": True,
                  "inference_calls_by_this_script": 0, "deadline_utc": scope["deadline_utc"]}))
