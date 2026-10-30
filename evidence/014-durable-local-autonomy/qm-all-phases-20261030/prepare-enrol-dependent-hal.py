"""Source-bound RCC QM demonstration handoff; explicit commands, never a scheduler.

Run on Omniverse2 with the production Python. Default is read-only. --prepare
creates hash-bound HAL intake files only after the LL archive/header is sealed
and native execution is quiescent. --enrol delegates launch to the existing
Conductor using the already signed LL/HAL scope. No signing, deadline extension,
counter reset, service change or direct model call is performed.
"""
from pathlib import Path
import argparse
from contextlib import nullcontext
import hashlib
import json
import os
import subprocess
import sys
import time

P = Path("/mnt/data/forge-c/production-local-014")
R = P / "repo"
O = P / "deployment/qm-rcc-launch-ready-20261030-v1"
SCOPE = "bdf0f9637adf9e1f4efc46978b9bc5d68346090b108235bad4e08352418c049f"
REV = "899865d5f256e3c2fbdd836ba8696ef9cdb6fa8f"
EXPECTED_EPOCH = 72

for line in (P / "state/afo/conductor.env").read_text().splitlines():
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ[k] = v
sys.path.insert(0, str(R / "factory/python"))
from forge_factory import development_demonstration as demo
from forge_factory.afo import contracts, operations, policy
from forge_factory.afo.dispatch import package_verdict
from forge_factory.afo.durable import digest, immutable_bytes, immutable_json
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.overnight import provision_order
from forge_factory.afo.queue import ReadSnapshot, Store
from forge_factory.common import sha256_file, utc_now
from forge_factory.inspection.engine import PHASES, Store as Inspections
from forge_factory.lrtx import stack
from forge_factory.release.finalize import verify_archive

parser = argparse.ArgumentParser(description=__doc__)
mode = parser.add_mutually_exclusive_group()
mode.add_argument("--prepare", action="store_true")
mode.add_argument("--enrol", action="store_true")
args = parser.parse_args()
s = json.loads((O / "scope.json").read_text())
assert digest(s) == SCOPE and s["source_revision"] == REV
assert s["demonstration_only"] and not s["historical_counters_reset"]
assert not s["deadline_changed"] and not s["non_time_limits_changed"]
assert time.time() < s["deadline_epoch"], "EXISTING_WINDOW_EXPIRED"
assert subprocess.check_output(["git", "-C", str(R), "rev-parse", "HEAD"], text=True).strip() == REV
assert not subprocess.check_output(["git", "-C", str(R), "status", "--porcelain"])
I = operations.Intent()


def waiting(reason, **fields):
    print(json.dumps({"status": "WAIT_FOR_PROVISIONAL_LL", "reason": reason,
                      "HAL_submitted": False, "model_requests": 0, **fields}))
    raise SystemExit(3)


def dependency(store):
    source = store.order(s["ll"]["order_id"])
    if not source or source["state"] not in {"BLOCKED", "FAILED", "READY_FOR_OFFLINE_REVIEW"}:
        waiting("LL_TASK_NOT_FINISHED", ll_state=(source or {}).get("state"))
    attempts = store.attempts(s["ll"]["order_id"])
    assert attempts
    latest = max(attempts, key=lambda a: a["seq"])
    with store.tx() as c:
        jobs = [json.loads(row[0]) for row in c.execute("SELECT record FROM afo_product_jobs")]
        selected = [j for j in jobs if j["order_id"] == s["ll"]["order_id"]
                    and j["attempt_id"] == latest["attempt_id"]]
    assert len(selected) == 1
    job = selected[0]
    execution = Executions(store).get(job["job_id"])
    if not execution or execution["execution_liveness"] != "QUIESCENT" or execution["resource_lease"] != "RELEASED":
        waiting("LL_NATIVE_NOT_QUIESCENT_AND_RELEASED")
    assert not Executions(store).pending()
    with store.tx() as c:
        assert not c.execute("SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL").fetchone()
        assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
        assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
    ws = Path(job["workspace"])
    assert ws.resolve().is_relative_to(P / "state/workorders") and not ws.is_symlink()
    assert job["factory_revision"]["commit"] == REV and job["model"] == s["model"]
    assert job["profile"] == s["profile"] and job["mission_id"] == s["mission_id"]
    native = (ws / ".forge-run/fabro_run_id").read_text().strip()
    assert native in execution["native_run_ids"]
    man = json.loads((ws / ".forge-run/manifest.json").read_text())
    assert man["purpose"] == "QM" and demo.selected(ws)
    package = ws / ".forge-run/package.json"
    if not package.is_file():
        waiting("LL_PACKAGE_NOT_FINALIZED")
    verdict = package_verdict(package)
    pkg = json.loads(package.read_text())
    assert verify_archive(Path(pkg["archive"]))["integrity"] == "PASS"
    assert sha256_file(Path(pkg["archive"])) == verdict["archive_sha256"]
    try:
        header, provided = demo.provided_ll(ws.parent.name, "rcc")
    except (ValueError, FileNotFoundError) as exc:
        waiting("LL_HAS_NO_USABLE_SEALED_HEADER", detail=str(exc))
    assert provided["qualification"] == "PROVISIONAL_QM_DEMONSTRATION_ONLY"
    assert provided["quality_accepted"] is False
    gates = {phase: Inspections(ws).gate(phase) for phase in PHASES}
    snapshot = MissionLedger(store).snapshot(s["mission_id"])
    assert snapshot["limits"]["deadline"] == s["deadline_epoch"]
    assert snapshot["lineage"] == s["mission_before"]["lineage"]
    return {
        "source_work_order": ws.parent.name, "source_order_id": s["ll"]["order_id"],
        "source_job_id": job["job_id"], "source_native_run_id": native,
        "source_revision": REV, "archive_sha256": verdict["archive_sha256"],
        "source_header_sha256": hashlib.sha256(header).hexdigest(), "provided_ll": provided,
        "phase_gates": {k: {"decision": v["decision"], "reason": v["reason"]} for k, v in gates.items()},
        "qualification": "PROVISIONAL_QM_DEMONSTRATION_ONLY", "quality_accepted": False,
        "basis": "Verified archive, six attempted phases, exact sealed read-only SWE.3 header; actual findings retained",
    }, snapshot


with I.lock():
    intent = I.read()
    assert intent["mode"] == "RUNNING" and intent["epoch"] == EXPECTED_EPOCH, "OPERATOR_INTENT_CHANGED"
    assert time.time() < s["deadline_epoch"]
    manager = nullcontext(Store()) if args.enrol else ReadSnapshot(P / "state/conductor/conductor.sqlite3")
    with manager as store:
        dep, snapshot = dependency(store)
        eff = policy.load(log=False)
        assert eff.mode == "PILOT" and eff.sha256 == s["policy_sha256"]
        assert stack.serving_instance(stack.settings(s["profile"])) == json.loads((O / "activation.json").read_text())["provider_instance"]
        trial = json.loads((O / "trial.json").read_text())
        ref = json.loads((O / "trial-ref.json").read_text())
        assert digest(trial) == ref["sha256"] and s["hal"]["order_id"] in trial["order_ids"]
        assert trial["source_revision"] == REV and trial["deadline_epoch"] == s["deadline_epoch"]
        launch = json.loads((O / "launch.json").read_text())
        launch.update(example=s["hal"]["example"], provided_from=dep["source_work_order"],
                      provisional_ll_dependency=dep, purpose="QM", profile=s["profile"],
                      advisory_continue=True, functional_gates_blocking=False)
        raw = json.dumps(launch, sort_keys=True, separators=(",", ":")).encode()
        if args.enrol:
            saved_dep = json.loads((O / "hal-dependency.json").read_text())
            assert dep == saved_dep, "LL_DEPENDENCY_CHANGED"
            assert (O / "hal-launch.json").read_bytes() == raw
            entry = json.loads((O / "hal-entry.json").read_text())
            env = entry["envelope"]
            assert entry["order_id"] == s["hal"]["order_id"] and entry["continuation_of"] == s["ll"]["order_id"]
            assert env["authorization_ref"] == s["primary_authorization"] and env["git_revision"] == REV
            assert env["request_id"] == s["hal"]["request_id"] and env["driver_class"] == "HAL"
            assert hashlib.sha256(raw).hexdigest() == env["manifest_sha256"]
            assert entry["mission"]["limits"] == snapshot["limits"]
            assert entry["mission"]["lineage"] == snapshot["lineage"]
            assert entry["mission"]["admission_authorization_ref"] == s["primary_authorization"]
            immutable_bytes(R / env["input_manifest_ref"], raw)
            assert sha256_file(R / env["input_manifest_ref"]) == env["manifest_sha256"]
            provision_order(store, entry, eff, s["deadline_epoch"])
            assert MissionLedger(store).for_order(entry["order_id"]) == s["mission_id"]
            assert MissionLedger(store).snapshot(s["mission_id"]) == snapshot
            result = {"status": "ENROLLED_CONDUCTOR_OWNS_EXECUTION", "order_id": entry["order_id"],
                      "mission_id": s["mission_id"], "source_revision": REV, "operator_epoch": EXPECTED_EPOCH,
                      "deadline_utc": s["deadline_utc"], "dependency_sha256": digest(dep),
                      "quality_accepted": False, "product_result": "NOT_RUN", "model_requests_by_enrolment": 0,
                      "spent_counters_preserved_before_dispatch": True, "at": utc_now()}
            immutable_json(O / "hal-intake.json", result)
        elif args.prepare:
            old = json.loads((O / "envelope.json").read_text())
            env = {**old, "request_id": s["hal"]["request_id"], "driver_class": "HAL",
                   "target": "QM demonstration: RCC HAL SWE.1-SWE.6 with sealed provisional generated LL",
                   "manifest_sha256": hashlib.sha256(raw).hexdigest(),
                   "input_manifest_ref": ".evidence-tmp/qm-rcc-launch-ready-20261030-v1/hal-launch.json",
                   "submitted_utc": utc_now()}
            contracts.require("work-order", env)
            entry = {"order_id": s["hal"]["order_id"], "continuation_of": s["ll"]["order_id"],
                     "envelope": env, "mission": {"mission_id": s["mission_id"], "lineage": snapshot["lineage"],
                      "limits": snapshot["limits"], "authorization_ref": snapshot["authorization_ref"],
                      "admission_authorization_ref": s["primary_authorization"],
                      "request": {"order_id": s["hal"]["request_id"], "driver_class": "HAL", "model": s["model"]}}}
            for name, doc in {"hal-dependency.json": dep, "hal-envelope.json": env, "hal-entry.json": entry}.items():
                immutable_json(O / name, doc)
            immutable_bytes(O / "hal-launch.json", raw)
            result = {"status": "HAL_PREPARED_NOT_ENROLLED", "order_id": s["hal"]["order_id"],
                      "dependency_sha256": digest(dep), "existing_signed_trial_reused": True,
                      "quality_accepted": False, "model_requests": 0}
        else:
            result = {"status": "HAL_PREREQUISITES_READY_NOT_SUBMITTED", "order_id": s["hal"]["order_id"],
                      "dependency_sha256": digest(dep), "quality_accepted": False, "model_requests": 0}
print(json.dumps(result))

