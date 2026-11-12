"""Explicit signed protocol response faults at the native adapter boundary.

No fault is enabled by a model, environment flag, case name or campaign alone.
The existing signed manifest binds each intervention before initial preparation.
These controls exercise refusal paths; they do not measure unmodified model
competence or independently establish a successful outcome.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
import time
from pathlib import Path

from ..common import sha256_file, state_dir
from .durable import Refused, canonical, digest, immutable_bytes, strict_json
from .qualification_inputs import FAULT_RECIPES, IMPLEMENTATION

RESPONSE = {
    "administrative-forgery",
    "empty-output",
    "malformed-output",
    "unqualified-local-alternative",
    "cross-case-reference",
    "reworded-strategy",
}
PRIMARY = {"stale-primary", "symlink-escape"}
DISPATCH = {"revoked-before-dispatch", "expired-mission", "lost-launch-ack", "cancel-ack-still-live"}
SUPPORTED = RESPONSE | PRIMARY | DISPATCH
# Native execution state each boundary requires before its intervention may be applied.
ADMISSION = {
    "before-native-dispatch": ("RESERVED",),
    "after-native-acceptance": ("DISPATCH_INTENT_RECORDED",),
    "during-native-execution": ("NATIVE_ACCEPTED",),
}
DISPATCH_SCHEMA = "forge-c/protocol-dispatch-fault-observation/1"
REJECTION_CODES = {
    "administrative-forgery": "CONTRACT_INVALID",
    "malformed-output": "INVALID_JSON",
    "cross-case-reference": "PROPOSAL_EVIDENCE_NOT_IN_CASE",
    "reworded-strategy": "SEMANTIC_STRATEGY_ALREADY_TRIED",
    "unqualified-local-alternative": "LOCAL_ALTERNATIVE_NOT_QUALIFIED_AND_AUTHORIZED",
}
PRIMARY_PATH = "software/hal/reg32.c"
STALE_BYTES = IMPLEMENTATION.encode() + b"\n/* SIGNED QUALIFICATION STALE PRIMARY */\n"
EXTERNAL_MARKER = b"Signed qualification symlink escape marker; not authoritative source.\n"


def validate_catalogue(catalogue, jobs):
    if not isinstance(catalogue, dict) or not set(catalogue) <= set(jobs):
        raise Refused("QUALIFICATION_FAULT_CATALOGUE_INVALID")
    for trial, recipe in catalogue.items():
        name = trial.rsplit(":", 1)[0]
        if name not in SUPPORTED or recipe != FAULT_RECIPES[name]:
            raise Refused("QUALIFICATION_FAULT_RECIPE_UNSUPPORTED", trial)


def bind(manifest, job):
    """Called only after initial_reservation verifies the exact owner signature."""
    from . import diagnosis_packet as P
    from . import semantic_proposal as S

    matches = [trial for trial, binding in manifest["jobs"].items() if binding["job_id"] == job["job_id"]]
    if len(matches) != 1:
        raise Refused("QUALIFICATION_FAULT_JOB_BINDING_INVALID")
    trial = matches[0]
    recipe = manifest.get("protocol_faults", {}).get(trial)
    if recipe is None:
        return {}
    case = json.loads(Path(job["case"]).read_text())
    fixture = case.get("qualification_fixture") or {}
    if (
        fixture.get("source_kind") != "SEEDED_PROTOCOL_NOT_PRODUCT"
        or fixture.get("evaluation_holdout") is not True
        or fixture.get("trial_id") != trial
        or fixture.get("prospective_fault") != recipe
    ):
        raise Refused("QUALIFICATION_FAULT_REQUIRES_EXPLICIT_FROZEN_FIXTURE")
    result = {"qualification_fault": {"trial_id": trial, "recipe": recipe, "manifest_sha256": digest(manifest)}}
    name = trial.rsplit(":", 1)[0]
    packet = P.load(case["packet_ref"])
    if name in PRIMARY:
        source = next((a for a in packet["artifacts"] if a["path"] == PRIMARY_PATH), None)
        if not source or source["sha256"] != hashlib.sha256(IMPLEMENTATION.encode()).hexdigest():
            raise Refused("QUALIFICATION_PRIMARY_FAULT_REQUIRES_FROZEN_SEEDED_SOURCE")
        P.evidence(packet, source["ref"], role=packet["role"], phase=packet["binding"]["phase"])
        result["qualification_primary_ref"] = {k: source[k] for k in ("path", "sha256", "ref")}
    elif name == "cross-case-reference":
        own_refs = {a["ref"] for a in packet["artifacts"]} | {f["ref"] for f in packet["findings"]}
        for other_trial, other in sorted(manifest["jobs"].items()):
            if other_trial == trial:
                continue
            path = Path(other["case"])
            if path.is_symlink() or sha256_file(path) != other["case_sha256"]:
                raise Refused("QUALIFICATION_FOREIGN_CASE_CHANGED")
            foreign_packet = P.load(json.loads(path.read_text())["packet_ref"])
            foreign = next((a for a in foreign_packet["artifacts"] if a["ref"] not in own_refs), None)
            if foreign:
                P.evidence(foreign_packet, foreign["ref"], role=foreign_packet["role"], phase=foreign_packet["binding"]["phase"])
                result["qualification_foreign_ref"] = {
                    "trial_id": other_trial,
                    "case_sha256": other["case_sha256"],
                    "evidence_ref": foreign["ref"],
                }
                break
        if "qualification_foreign_ref" not in result:
            raise Refused("QUALIFICATION_DISTINCT_FOREIGN_EVIDENCE_REQUIRED")
    elif name == "reworded-strategy":
        fields = {
            "decision": "PROPOSE_REPAIR",
            "strategy": "REWORK_LOCAL",
            "affected_phase": "SWE.3",
            "technique_id": "repair-implementation",
            "target_obligations": ["USPEC-001"],
            "artifact_scope": ["software/hal"],
            "validation_expectations": [{"test_ref": "gate:SWE.3:route=PASS", "expected_result": "PASS"}],
        }
        if S.signature(fields) not in packet["prior_strategies"]:
            raise Refused("QUALIFICATION_FROZEN_PRIOR_STRATEGY_REQUIRED")
        result["qualification_replay_fields"] = fields
    return result


def _context(store, job, eff, boundary):
    """Every boundary uses the same fresh authority, identity and native lease checks."""
    fault = job.get("qualification_fault")
    if fault is None:
        return None

    from . import authz, local_agent
    from .completion_receipt import Context
    from .execution_lifecycle import Executions

    name = fault["trial_id"].rsplit(":", 1)[0]
    if name not in SUPPORTED or fault["recipe"] != FAULT_RECIPES[name]:
        raise Refused("QUALIFICATION_FAULT_RECIPE_UNSUPPORTED")
    if fault["recipe"]["boundary"] != boundary:
        return None
    ctx = Context.from_job(store, job["job_id"])
    if ctx.launch_nonce != job["nonce"] or ctx.case_sha256 != job["case_sha256"]:
        raise Refused("QUALIFICATION_FAULT_JOB_BINDING_INVALID")
    with store.tx() as c:
        row = c.execute("SELECT record FROM afo_local_agent_jobs WHERE job_id=?", (job["job_id"],)).fetchone()
    current = json.loads(row[0])
    if current.get("qualification_fault") != fault or fault["manifest_sha256"] != current.get("qualification_manifest_sha256"):
        raise Refused("QUALIFICATION_FAULT_NOT_BOUND_TO_JOB")
    if (
        current.get("policy_sha256") != eff.sha256
        or current.get("model") != job.get("model")
        or time.time() >= current["deadline_epoch"]
    ):
        raise Refused("QUALIFICATION_FAULT_POLICY_OR_DEADLINE_CHANGED")
    if sha256_file(Path(job["case"])) != ctx.case_sha256:
        raise Refused("QUALIFICATION_FAULT_CASE_CHANGED")
    ref = eff.get("authorization_ref")
    order = store.order(ctx.order_id)
    if not order or order["state"] not in ("RUNNING", "WAITING_RECOVERY"):
        raise Refused("QUALIFICATION_FAULT_ORDER_NOT_ACTIVE")
    request = {**local_agent.request_for(order), "model": current["model"]}
    grant = authz.find(eff.mode, eff.sha256 or "", ref=ref, action="recover_workorder", request=request)
    if not grant.allow:
        raise Refused(grant.code)
    record = json.loads((authz.AUTH_DIR / f"{ref}.json").read_text())
    if record.get("signed_runbook_ref") != "qualification-014:" + fault["manifest_sha256"]:
        raise Refused("QUALIFICATION_FAULT_NOT_SIGNED")
    live = Executions(store).get(job["job_id"]) or {}
    if (
        live.get("launch_nonce") != job["nonce"]
        or live.get("resource_lease") != "HELD"
        or live.get("task_outcome") != "ACTIVE"
        or live.get("authorization_state") != "VALID"
        or live.get("admission_state") not in ADMISSION.get(boundary, ("DISPATCH_INTENT_RECORDED", "NATIVE_ACCEPTED"))
    ):
        raise Refused("QUALIFICATION_FAULT_EXECUTION_NOT_ACTIVE")
    return ctx, fault, name, current


def _record(store, job_id, kind, evidence):
    """Use the authoritative evidence table; changed replay cannot overwrite history."""
    with store.tx() as c:
        previous = c.execute(
            "SELECT record,sha256 FROM afo_execution_evidence WHERE job_id=? AND kind=?", (job_id, kind)
        ).fetchone()
        if previous and digest(json.loads(previous["record"])) != previous["sha256"]:
            raise Refused("QUALIFICATION_FAULT_EVIDENCE_CORRUPT")
        if previous and previous["sha256"] != digest(evidence):
            raise Refused("QUALIFICATION_FAULT_REPLAY_CHANGED")
        c.execute(
            "INSERT OR IGNORE INTO afo_execution_evidence VALUES (?,?,?,?)",
            (job_id, kind, canonical(evidence).decode(), digest(evidence)),
        )


def apply_response(store, job, raw, eff):
    """Only a signed response-boundary recipe can transform visible model content."""
    context = _context(store, job, eff, "after-provider-response")
    if context is None:
        return raw
    if not isinstance(raw, str) or len(raw.encode()) > 65536:
        raise Refused("QUALIFICATION_RESPONSE_FAULT_INPUT_INVALID")
    ctx, fault, name, current = context
    details = {}
    if name == "empty-output":
        changed = ""
    elif name == "malformed-output":
        changed = raw.rstrip()[:-1] if raw.strip().endswith("}") else '{"qualification_incomplete":'
    else:
        value = strict_json(raw)
        if not isinstance(value, dict):
            raise Refused("QUALIFICATION_RESPONSE_FAULT_REQUIRES_JSON_OBJECT")
        if name == "administrative-forgery":
            value["order_id"] = "qualification-forged-administrative-id"
        elif name == "cross-case-reference":
            foreign = current["qualification_foreign_ref"]
            value["evidence_refs"] = [foreign["evidence_ref"]]
            details["foreign_evidence"] = foreign
        elif name == "reworded-strategy":
            from .semantic_proposal import signature

            if value.get("decision") != "PROPOSE_REPAIR":
                raise Refused("QUALIFICATION_REPLAY_FAULT_REQUIRES_REPAIR_PROPOSAL")
            value.update(current["qualification_replay_fields"])
            value["material_difference"] = "Reworded qualification label for the same previously tried strategy"
            # These fields are absent from the frozen REWORK_LOCAL strategy.
            value.pop("owner_phase", None)
            value.pop("model_profile", None)
            details["replayed_strategy_sha256"] = signature(value)
        else:
            if value.get("decision") != "PROPOSE_REPAIR":
                raise Refused("QUALIFICATION_MODEL_SWITCH_FAULT_REQUIRES_REPAIR_PROPOSAL")
            value["strategy"] = "SWITCH_PREAPPROVED_MODEL_PROFILE"
            value["model_profile"] = "qualification-unqualified-model"
            # A switch carries no upstream owner (contract); otherwise the contract, not the alternative check, refuses.
            value.pop("owner_phase", None)
        changed = canonical(value).decode()
    evidence = {
        "schema": "forge-c/protocol-fault-observation/1",
        "job_id": job["job_id"],
        "nonce": job["nonce"],
        "case_sha256": ctx.case_sha256,
        **fault,
        **details,
        "original_response_sha256": hashlib.sha256(raw.encode()).hexdigest(),
        "injected_response_sha256": hashlib.sha256(changed.encode()).hexdigest(),
        "scope": "DECLARED_INTERVENTION_NOT_UNMODIFIED_MODEL_COMPETENCE",
    }
    _record(store, job["job_id"], "PROTOCOL_RESPONSE_FAULT", evidence)
    return changed


def apply_primary(store, job, eff):
    """Mutate only the explicitly seeded REG32 fixture; durable intent precedes atomic replacement."""
    context = _context(store, job, eff, "before-evidence-read")
    if context is None:
        return None
    from .diagnosis_packet import scoped_path

    ctx, fault, name, current = context
    primary = current["qualification_primary_ref"]
    if primary["path"] != PRIMARY_PATH or primary["sha256"] != hashlib.sha256(IMPLEMENTATION.encode()).hexdigest():
        raise Refused("QUALIFICATION_PRIMARY_FAULT_REQUIRES_FROZEN_SEEDED_SOURCE")
    # Validate the parent independently: the intentional target symlink must be
    # recognized on crash replay without following it or allowing a parent escape.
    parent = scoped_path(Path(current["source_workspace"]), "software/hal")
    path = parent / "reg32.c"
    marker = scoped_path(state_dir(), "lrtx/protocol-faults/fault-" + digest(job["job_id"])[:24] + "/external-marker.txt")
    if Path(current["source_workspace"]).resolve() in marker.resolve().parents:
        raise Refused("QUALIFICATION_ESCAPE_MARKER_MUST_BE_OUTSIDE_WORKSPACE")
    injected = (
        hashlib.sha256(STALE_BYTES).hexdigest()
        if name == "stale-primary"
        else digest({"kind": "symlink", "target": str(marker), "target_sha256": hashlib.sha256(EXTERNAL_MARKER).hexdigest()})
    )
    fact = {
        "schema": "forge-c/protocol-primary-fault-observation/1",
        "job_id": job["job_id"],
        "nonce": job["nonce"],
        "case_sha256": ctx.case_sha256,
        **fault,
        "path": PRIMARY_PATH,
        "original_entry_sha256": primary["sha256"],
        "injected_entry_sha256": injected,
        "entry_kind": "file" if name == "stale-primary" else "symlink",
        "scope": "DECLARED_INTERVENTION_NOT_UNMODIFIED_MODEL_COMPETENCE",
    }
    _record(store, job["job_id"], "PROTOCOL_PRIMARY_FAULT_INTENT", fact)
    if path.is_symlink():
        if (
            name != "symlink-escape"
            or os.readlink(path) != str(marker)
            or sha256_file(marker) != hashlib.sha256(EXTERNAL_MARKER).hexdigest()
        ):
            raise Refused("QUALIFICATION_PRIMARY_ENTRY_CHANGED")
    else:
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > max(len(STALE_BYTES), len(IMPLEMENTATION.encode())):
                    raise Refused("QUALIFICATION_PRIMARY_ENTRY_CHANGED")
                original = stream.read(len(STALE_BYTES) + 1)
        except OSError as exc:
            raise Refused("QUALIFICATION_PRIMARY_ENTRY_CHANGED") from exc
        if original != IMPLEMENTATION.encode() and not (name == "stale-primary" and original == STALE_BYTES):
            raise Refused("QUALIFICATION_PRIMARY_ENTRY_CHANGED")
        if original == IMPLEMENTATION.encode():
            descriptor, staged = tempfile.mkstemp(prefix=".qualification-fault-", dir=parent)
            temp = Path(staged)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    if name == "stale-primary":
                        stream.write(STALE_BYTES)
                        stream.flush()
                        os.fsync(stream.fileno())
                        os.fchmod(stream.fileno(), 0o400)
                if name == "symlink-escape":
                    immutable_bytes(marker, EXTERNAL_MARKER)
                    temp.unlink()
                    os.symlink(str(marker), temp)
                os.replace(temp, path)
                directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            finally:
                if temp.exists() or temp.is_symlink():
                    temp.unlink()
    # A crash after replacement simply adopts the same entry on the next call.
    _record(store, job["job_id"], "PROTOCOL_PRIMARY_FAULT", fact)
    return fact


def _evidence(store, job_id, kind):
    with store.tx() as c:
        row = c.execute("SELECT record,sha256 FROM afo_execution_evidence WHERE job_id=? AND kind=?", (job_id, kind)).fetchone()
    if not row:
        return None
    value = json.loads(row["record"])
    if digest(value) != row["sha256"]:
        raise Refused("QUALIFICATION_FAULT_EVIDENCE_CORRUPT")
    return value


def _dispatch_fact(job, ctx, fault, **details):
    return {
        "schema": DISPATCH_SCHEMA,
        "job_id": job["job_id"],
        "nonce": job["nonce"],
        "case_sha256": ctx.case_sha256,
        **fault,
        **details,
        "scope": "DECLARED_INTERVENTION_NOT_UNMODIFIED_MODEL_COMPETENCE",
    }


def _replay(job, intent):
    """A recorded intent was authorized when written; replay only finishes its own effect."""
    fault = job.get("qualification_fault") or {}
    if intent["job_id"] != job["job_id"] or intent["nonce"] != job["nonce"] or any(intent.get(k) != v for k, v in fault.items()):
        raise Refused("QUALIFICATION_FAULT_REPLAY_CHANGED")
    return intent


def apply_dispatch(store, job, eff):
    """Job-scoped authority or deadline intervention before dispatch intent.

    The common grant and mission stay unchanged, so one negative trial cannot block
    the matrix. The existing poll then refuses dispatch through its ordinary path.
    """
    from .execution_lifecycle import Executions

    fault = job.get("qualification_fault")
    if not fault or fault["recipe"]["boundary"] != "before-native-dispatch":
        return None
    ex = Executions(store)
    intent = _evidence(store, job["job_id"], "PROTOCOL_DISPATCH_FAULT_INTENT")
    if intent is None:
        context = _context(store, job, eff, "before-native-dispatch")
        if context is None:
            return None
        ctx, fault, name, _ = context
        details = {"lease_epoch": ex.get(job["job_id"])["lease_epoch"]}
        if name == "revoked-before-dispatch":
            details["effect"] = "EXECUTION_AUTHORITY_REVOKED"
        else:
            # Only this job's view of the mission deadline elapses; the registered mission is not edited.
            details.update(effect="JOB_SCOPED_MISSION_DEADLINE_ELAPSED", effective_mission_deadline=time.time())
        intent = _dispatch_fact(job, ctx, fault, **details)
        _record(store, job["job_id"], "PROTOCOL_DISPATCH_FAULT_INTENT", intent)
    _replay(job, intent)
    live = ex.get(job["job_id"])
    if intent["effect"] == "EXECUTION_AUTHORITY_REVOKED" and live["authorization_state"] == "VALID":
        ex.revoke(job["job_id"], "REVOKED")
    _record(store, job["job_id"], "PROTOCOL_DISPATCH_FAULT", intent)
    return intent


def drop_launch_ack(store, job, eff, run_id):
    """Discard a real native launch receipt; recovery must adopt by the existing nonce listing, once."""
    context = _context(store, job, eff, "after-native-acceptance")
    if context is None:
        return False
    ctx, fault, _, _ = context
    fact = _dispatch_fact(
        job, ctx, fault, effect="LAUNCH_ACK_DROPPED", dropped_ack_sha256=hashlib.sha256(run_id.encode()).hexdigest()
    )
    _record(store, job["job_id"], "PROTOCOL_DISPATCH_FAULT", fact)
    return True


def cancel_with_live_request(store, job, eff, client, rec):
    """Request cancellation only while a real gateway request is SENT; acknowledgment must not release capacity."""
    from .execution_lifecycle import Executions

    fault = job.get("qualification_fault")
    if not fault or fault["recipe"]["boundary"] != "during-native-execution":
        return None
    if _evidence(store, job["job_id"], "PROTOCOL_DISPATCH_FAULT"):
        return None
    ex = Executions(store)
    intent = _evidence(store, job["job_id"], "PROTOCOL_DISPATCH_FAULT_INTENT")
    if intent is None:
        if (
            rec["identity_state"] != "CONFIRMED"
            or rec["execution_liveness"] != "LIVE"
            or rec["task_outcome"] != "ACTIVE"
            or rec["resource_lease"] != "HELD"
        ):
            return None
        with store.tx() as c:
            live = sorted(
                r[0]
                for r in c.execute("SELECT request_id FROM afo_request_ledger WHERE job_id=? AND state='SENT'", (job["job_id"],))
            )
        if not live:
            return None
        context = _context(store, job, eff, "during-native-execution")
        if context is None:
            return None
        ctx, fault, _, _ = context
        intent = _dispatch_fact(
            job,
            ctx,
            fault,
            effect="CANCEL_REQUESTED_WITH_LIVE_REQUEST",
            live_request_ids=live,
            native_run_ids=rec["native_run_ids"],
        )
        _record(store, job["job_id"], "PROTOCOL_DISPATCH_FAULT_INTENT", intent)
        ex.outcome(job["job_id"], "BLOCKED", "QUALIFICATION_CANCEL_REQUESTED_WITH_LIVE_REQUEST")
    _replay(job, intent)
    after = ex.reconcile(job["job_id"], client, cancel=True)
    _record(
        store,
        job["job_id"],
        "PROTOCOL_DISPATCH_FAULT",
        {
            **intent,
            "cancellation_state": after["cancellation_state"],
            "cancel_acknowledged": after["cancellation_state"] == "ACKNOWLEDGED",
            "last_cancel_error": after["last_cancel_error"],
            "resource_lease_after_cancel": after["resource_lease"],
        },
    )
    return after


def _dispatch_matches(name, fact, row):
    execution = row.get("execution") or {}
    if fact.get("schema") != DISPATCH_SCHEMA:
        return False
    if name == "revoked-before-dispatch":
        return (
            fact.get("effect") == "EXECUTION_AUTHORITY_REVOKED"
            and row.get("job_state") == "REVOKED"
            and execution.get("authorization_state") == "REVOKED"
            and execution.get("execution_liveness") == "NOT_STARTED"
            and not execution.get("native_run_ids")
        )
    if name == "expired-mission":
        return (
            fact.get("effect") == "JOB_SCOPED_MISSION_DEADLINE_ELAPSED"
            and row.get("job_error") == "MISSION_DEADLINE_EXHAUSTED"
            and execution.get("authorization_state") == "EXPIRED"
            and execution.get("execution_liveness") == "NOT_STARTED"
            and not execution.get("native_run_ids")
        )
    if name == "lost-launch-ack":
        ids = execution.get("native_run_ids") or []
        adoption = row.get("native_adoption") or {}
        return (
            fact.get("effect") == "LAUNCH_ACK_DROPPED"
            and len(ids) == 1
            and hashlib.sha256(ids[0].encode()).hexdigest() == fact.get("dropped_ack_sha256")
            and adoption.get("run_ids") == ids
            and adoption.get("launch_nonce") == fact.get("nonce")
        )
    return (
        fact.get("effect") == "CANCEL_REQUESTED_WITH_LIVE_REQUEST"
        and bool(fact.get("live_request_ids"))
        and fact.get("cancel_acknowledged") is True
        and fact.get("resource_lease_after_cancel") == "HELD"
        and execution.get("resource_lease") == "HELD"
    )


def observation_matches(manifest, row):
    """An expected refusal cannot stand in for the declared fault exposure."""
    recipe = manifest.get("protocol_faults", {}).get(row["trial_id"])
    if recipe is None:
        return True
    binding = manifest["jobs"][row["trial_id"]]
    fact = row.get("fault_observation") or {}
    declared = row.get("declared_fault") or {}
    if not isinstance(fact, dict) or not isinstance(declared, dict):
        return False
    common = (
        declared == {"trial_id": row["trial_id"], "recipe": recipe, "manifest_sha256": digest(manifest)}
        and all(fact.get(k) == v for k, v in declared.items())
        and fact.get("job_id") == binding["job_id"] == row["job_id"]
        and fact.get("case_sha256") == binding["case_sha256"]
        and fact.get("nonce") == (row.get("execution") or {}).get("launch_nonce")
        and fact.get("scope") == "DECLARED_INTERVENTION_NOT_UNMODIFIED_MODEL_COMPETENCE"
    )
    if not common:
        return False
    name = row["trial_id"].rsplit(":", 1)[0]
    if name in DISPATCH:
        return _dispatch_matches(name, fact, row)
    if name in REJECTION_CODES and REJECTION_CODES[name] not in (row.get("receipt") or {}).get("reason_codes", []):
        return False
    if name == "empty-output" and row.get("job_error") != "EMPTY_MODEL_OUTPUT":
        return False
    if name in PRIMARY and row.get("job_error") != (
        "EVIDENCE_MISSING_OR_CHANGED" if name == "stale-primary" else "EVIDENCE_PATH_ESCAPE"
    ):
        return False
    primary = recipe["boundary"] == "before-evidence-read"
    hashes = (
        ("original_entry_sha256", "injected_entry_sha256")
        if primary
        else ("original_response_sha256", "injected_response_sha256")
    )
    return (
        fact.get("schema")
        == ("forge-c/protocol-primary-fault-observation/1" if primary else "forge-c/protocol-fault-observation/1")
        and (
            not primary
            or (
                fact.get("path") == PRIMARY_PATH
                and fact.get("entry_kind") == ("file" if row["trial_id"].startswith("stale-primary:") else "symlink")
            )
        )
        and all(
            isinstance(fact.get(k), str) and len(fact[k]) == 64 and all(c in "0123456789abcdef" for c in fact[k]) for k in hashes
        )
        and fact[hashes[0]] != fact[hashes[1]]
    )


def evidence_kind(job):
    boundary = ((job.get("qualification_fault") or {}).get("recipe") or {}).get("boundary")
    if boundary == "before-evidence-read":
        return "PROTOCOL_PRIMARY_FAULT"
    return "PROTOCOL_DISPATCH_FAULT" if boundary in ADMISSION else "PROTOCOL_RESPONSE_FAULT"
