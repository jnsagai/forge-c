"""Signed qualification intake through the existing AFO authorities (DA-T024).

Enrollment registers only the explicitly frozen, owner-signed qualification
mission, links each predeclared order to it BEFORE the order can become QUEUED,
submits the hash-bound envelope through the ordinary intake validator and records
the signed intake context in the existing evidence table. It creates no grant,
scheduler, job reservation, native run or inference. The existing scheduler
admits the wrapper under its lease, pause/drain, concurrency and operator epoch;
a RUNNING wrapper denotes qualification work only, never a product run.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from .durable import Refused, digest, strict_json
from .queue import QueueError, order_id_for

KIND = "QUALIFICATION_INTAKE"
SCHEMA = "forge-c/qualification-intake-014/1"
INPUT_SCHEMA = "forge-c/protocol-inputs-014/1"
ACTIONS = ("submit_workorder", "launch_workorder", "recover_workorder")
FILES = ("envelope", "launch_manifest", "run_manifest", "model_profile")
MAX_INPUTS_BYTES = 4 * 1024 * 1024


def _key(order_id):
    return "order:" + order_id


def authenticated_inputs(manifest):
    """The single protocol-input document the signed manifest names, read once and hash-checked."""
    found = []
    for ref in manifest["inputs"]:
        path = Path(ref["path"])
        if path.suffix != ".json" or path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_INPUTS_BYTES:
            continue
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
            raise Refused("CAMPAIGN_FROZEN_INPUT_CHANGED", str(path))
        try:
            doc = strict_json(raw, MAX_INPUTS_BYTES)
        except (Refused, ValueError, UnicodeError):
            continue
        if isinstance(doc, dict) and doc.get("schema") == INPUT_SCHEMA:
            found.append((path, ref["sha256"], doc))
    if len(found) != 1:
        raise Refused("QUALIFICATION_INTAKE_INPUTS_REQUIRED")
    return found[0]


def _file(root, ref, name, trial):
    from .diagnosis_packet import scoped_path

    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"}:
        raise Refused("QUALIFICATION_INTAKE_UNBOUND_LEGACY_INPUT", trial)
    try:
        path = scoped_path(root, ref["path"])
    except Refused as exc:
        raise Refused("QUALIFICATION_INTAKE_PATH_ESCAPE", f"{trial}:{name}") from exc
    if not path.is_file():
        raise Refused("QUALIFICATION_INTAKE_FILE_MISSING", f"{trial}:{name}")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
        raise Refused("QUALIFICATION_INTAKE_FILE_CHANGED", f"{trial}:{name}")
    return strict_json(raw, 1024 * 1024)


def verify_files(root, intake, trial):
    """Re-read every bound intake file; legacy inputs without bindings are refused, never trusted."""
    if not isinstance(intake, dict) or set(intake) != set(FILES):
        raise Refused("QUALIFICATION_INTAKE_UNBOUND_LEGACY_INPUT", trial)
    return {name: _file(root, intake[name], name, trial) for name in FILES}


def _context(manifest, inputs_path, inputs_sha, inputs, trial_id, authorization_ref):
    sha = digest(manifest)
    root = Path(inputs["root"]).resolve()
    trial = next((t for t in inputs["trials"] if t["trial_id"] == trial_id), None)
    binding = manifest["jobs"].get(trial_id)
    if trial is None or binding is None or inputs["jobs"].get(trial_id) != binding:
        raise Refused("QUALIFICATION_INTAKE_TRIAL_BINDING_MISMATCH", trial_id)
    docs = verify_files(root, trial.get("intake"), trial_id)
    env, launch, run, model = (docs[name] for name in FILES)
    intake = trial["intake"]
    if (
        env.get("input_manifest_ref") != intake["launch_manifest"]["path"]
        or env.get("manifest_sha256") != intake["launch_manifest"]["sha256"]
        or env.get("authorization_ref") != authorization_ref
        or env.get("model_profile") != manifest["model_profile"]
        or env.get("tenant_scope") != inputs["mission_id"]
        or order_id_for(env.get("tenant_scope", ""), env.get("request_id", "")) != trial["order_id"]
    ):
        raise Refused("QUALIFICATION_INTAKE_ENVELOPE_MISMATCH", trial_id)
    if (
        launch.get("kind") != "QUALIFICATION_PROTOCOL_FIXTURE"
        or launch.get("case") != binding["case"]
        or launch.get("case_sha256") != binding["case_sha256"]
        or launch.get("model_profile") != manifest["model_profile"]
        or run.get("fixture_kind") != "SEEDED_PROTOCOL_NOT_PRODUCT"
        or run.get("evaluation_holdout") is not True
        or (run.get("local_profile") or {}).get("id") != launch.get("profile")
        or model.get("default") != manifest["model_profile"]
    ):
        raise Refused("QUALIFICATION_INTAKE_LAUNCH_MISMATCH", trial_id)
    return env, {
        "schema": SCHEMA,
        "order_id": trial["order_id"],
        "attempt_id": trial["attempt_id"],
        "trial_id": trial_id,
        "job_id": binding["job_id"],
        "case_sha256": binding["case_sha256"],
        "mission_id": binding["mission_id"],
        "manifest_sha256": sha,
        "qualification_ref": "qualification-014:" + sha,
        "authorization_ref": authorization_ref,
        "inputs": {"path": str(inputs_path.resolve()), "sha256": inputs_sha},
        "root": str(root),
        "intake": intake,
        "envelope_sha256": digest(env),
        "job_token_reservation": manifest["job_token_reservations"][binding["job_id"]],
        "purpose": "ROLE_PROTOCOL_FIXTURE_NO_PRODUCT_LAUNCH",
    }


def context(store, order):
    """The signed intake record of a qualification wrapper, or None for every ordinary order."""
    with store.tx() as c:
        row = c.execute(
            "SELECT record,sha256 FROM afo_execution_evidence WHERE job_id=? AND kind=?", (_key(order["order_id"]), KIND)
        ).fetchone()
    if not row:
        return None
    rec = json.loads(row["record"])
    if (
        digest(rec) != row["sha256"]
        or rec.get("schema") != SCHEMA
        or rec.get("order_id") != order["order_id"]
        or order["manifest_sha256"] != rec["intake"]["launch_manifest"]["sha256"]
        or order["input_manifest_ref"] != rec["intake"]["launch_manifest"]["path"]
        or digest(json.loads(order["envelope"])) != rec["envelope_sha256"]
    ):
        raise Refused("QUALIFICATION_INTAKE_BINDING_CHANGED", order["order_id"])
    return rec


def launch_manifest(rec):
    """Resolve only inside the authenticated frozen intake root, re-verifying the bound bytes."""
    return _file(Path(rec["root"]), rec["intake"]["launch_manifest"], "launch_manifest", rec["trial_id"])


def grant_record(authorization_ref):
    from . import authz

    return json.loads((authz.AUTH_DIR / f"{authorization_ref}.json").read_text())


def _record(store, rec):
    from .protocol_faults import _record as record

    try:
        record(store, _key(rec["order_id"]), KIND, rec)
    except Refused as exc:
        raise Refused("QUALIFICATION_INTAKE_REPLAY_CHANGED", rec["order_id"]) from exc


def enroll(manifest, authorization_ref, *, store=None, trial_ids=None, limit=8):
    """Bounded, crash-recoverable intake of predeclared trials; no admission, job or inference."""
    from . import authority, authz
    from . import qualification as Q
    from .mission_ledger import MissionLedger
    from .policy import load
    from .queue import Store

    readiness = Q.preflight(manifest, live=True, authorization_ref=authorization_ref, trial_ids=trial_ids)
    if readiness["blockers"]:
        return readiness
    if manifest["stage"] != "protocol" or not 1 <= limit <= 32:
        raise Refused("PROTOCOL_INTAKE_BOUND_REQUIRED")
    mission = manifest.get("mission")
    if not mission or not manifest.get("job_token_reservations"):
        raise Refused("QUALIFICATION_EXPLICIT_MISSION_REQUIRED")
    store = store or Store()
    eff = load()
    inputs_path, inputs_sha, inputs = authenticated_inputs(manifest)
    if inputs["mission_id"] != mission["mission_id"]:
        raise Refused("QUALIFICATION_INTAKE_MISSION_MISMATCH")
    blockers = []
    for action in ACTIONS:
        d = authz.find(
            eff.mode, eff.sha256 or "", ref=authorization_ref, action=action, request={"model": manifest["model_profile"]}
        )
        if not d.allow:
            blockers.append(f"{d.code}:{action}")
    if blockers:
        return {**readiness, "status": "BLOCKED", "blockers": blockers}
    expiry = datetime.fromisoformat(grant_record(authorization_ref)["expires_utc"].replace("Z", "+00:00")).timestamp()
    if mission["limits"]["deadline"] > expiry:
        raise Refused("QUALIFICATION_MISSION_OUTLIVES_AUTHORITY")
    # Every selected binding is verified before any durable effect, including mission registration.
    selected = [
        (trial, *_context(manifest, inputs_path, inputs_sha, inputs, trial, authorization_ref))
        for trial in sorted(Q.selected_trials(manifest, trial_ids))
    ]
    ledger = MissionLedger(store)
    # Exact frozen limits only: an existing mission with any other identity is a forbidden reset.
    ledger.register(
        mission["mission_id"],
        mission["lineage"],
        mission["limits"],
        authorization_ref,
        authorize=lambda ref, limits: ref == authorization_ref and limits == mission["limits"],
    )
    max_queued = int(eff.get("queue.max_queued_orders", 0))
    submitted, present = [], []
    for trial, env, rec in selected:
        oid = rec["order_id"]
        existing = store.order(oid)
        if existing is not None:
            if context(store, existing) != rec:
                raise Refused("QUALIFICATION_ORDER_EXISTS_WITHOUT_SIGNED_INTAKE", trial)
            present.append(trial)
            continue
        request = {"order_id": env["request_id"], "driver_class": env["driver_class"], "model": env["model_profile"]}
        for action in ACTIONS:
            d = authority.decide(action, request, afo=eff)
            if not d.allow:
                return {"status": "BLOCKED", "blockers": [f"{d.code}:{action}"], "trial": trial, "inference_requests": 0}
        # Record and link before the order exists: no scheduler can observe an unlinked QUEUED wrapper.
        _record(store, rec)
        ledger.link(mission["mission_id"], oid)
        def approve(_env, request=request):
            d = authority.decide("submit_workorder", request, afo=eff)
            return d.allow, d.code

        try:
            store.submit(env, repo=Path(rec["root"]), max_queued=max_queued, approve=approve)
        except QueueError as exc:
            if exc.code != "INTAKE_BACKLOG_FULL":
                raise
            return {
                "status": "INTAKE_BACKPRESSURE",
                "submitted_this_call": len(submitted),
                "submitted": submitted,
                "inference_requests": 0,
            }
        submitted.append(trial)
        if len(submitted) >= limit:
            return {
                "status": "ENROLLMENT_IN_PROGRESS",
                "submitted_this_call": len(submitted),
                "submitted": submitted,
                "inference_requests": 0,
            }
    return {
        "status": "ENROLLED_WAITING_AFO_ADMISSION",
        "submitted_this_call": len(submitted),
        "submitted": submitted,
        "already_enrolled": present,
        "campaign_denominator": manifest["expected_trials"],
        "inference_requests": 0,
    }


def start(store, order, manifest_sha):
    """ADMITTED -> RUNNING for a signed wrapper only; it never creates a launch intent or native run."""
    rec = context(store, order)
    if rec is None or rec["manifest_sha256"] != manifest_sha:
        raise Refused("QUALIFICATION_WRAPPER_INTAKE_REQUIRED", order["order_id"])
    verify_files(Path(rec["root"]), rec["intake"], rec["trial_id"])
    attempts = store.attempts(order["order_id"])
    att = attempts[-1] if attempts else None
    with store.tx() as c:
        launch = c.execute(
            "SELECT 1 FROM afo_commands_outbox WHERE order_id=? AND kind='FABRO_LAUNCH'", (order["order_id"],)
        ).fetchone()
    if (
        att is None
        or len(attempts) != 1
        or att["attempt_id"] != rec["attempt_id"]
        or att["state"] != "PREPARED"
        or att["record"].get("fabro_run_id")
        or rec["qualification_ref"] not in (att["record"].get("evidence_refs") or [])
        or launch
    ):
        raise Refused("QUALIFICATION_WRAPPER_ADMISSION_MISMATCH", order["order_id"])
    store.transition(order["order_id"], "RUNNING", "qualification wrapper started; no product run claimed")
    return store.order(order["order_id"])
