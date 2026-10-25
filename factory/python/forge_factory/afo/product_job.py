"""Product executions share the mission ledger and native-liveness reconciler."""

from __future__ import annotations
import json
import time
from pathlib import Path
from .durable import Refused, canonical, digest, immutable_json
from .execution_lifecycle import Executions
from .mission_ledger import MissionLedger


def prepare(store, order, attempt, nonce, manifest, eff):
    from .runtime import workspace_of

    mission = MissionLedger(store).for_order(order["order_id"])
    job_id = "afo-product-" + digest(attempt["attempt_id"])[:24]
    ws = workspace_of(attempt)
    binding = {
        "job_id": job_id,
        "nonce": nonce,
        "mission_id": mission,
        "order_id": order["order_id"],
        "attempt_id": attempt["attempt_id"],
    }
    from .operations import configured, Intent

    if configured():
        intent = Intent().read()
        if intent["mode"] != "RUNNING":
            raise Refused("OPERATIONS_ADMISSION_REFUSED")
        if manifest.get("operations_epoch") != intent["epoch"]:
            raise Refused("OPERATIONS_ADMISSION_FENCED")
        binding["operations_epoch"] = intent["epoch"]
    job = {
        **binding,
        "workspace": str(ws),
        "binding": str(ws / ".forge-run/durable-binding.json"),
        "model": manifest.get("model_profile") or manifest.get("model"),
        "policy_sha256": eff.sha256,
        "deadline_epoch": order["created_epoch"] + float(eff.get("budgets.max_order_wall_seconds")),
        "reserved_tokens": int(eff.get("budgets.max_model_tokens_per_order")),
    }
    from ..workorder import factory_revision

    job["factory_revision"] = factory_revision()
    selected = next(
        (a for a in manifest.get("qualified_local_alternatives") or [] if a.get("model_profile") == job["model"]), None
    )
    job["role_capabilities"] = (selected or manifest).get("role_capabilities") or {}
    job["profile"] = manifest.get("profile")
    if job["profile"]:
        from ..lrtx.profile import load as load_profile

        model_identity = load_profile(job["profile"])["models"]["allowed"][job["model"]]
        job["model_digest"] = model_identity["digest"]
        job["precision"] = model_identity["quantization"]
    MissionLedger(store).execution(mission, job_id, "PRODUCT", reserved_tokens=job["reserved_tokens"])
    with store.tx() as c:
        old = c.execute("SELECT record FROM afo_product_jobs WHERE job_id=?", (job_id,)).fetchone()
        if old:
            prior = json.loads(old[0])
            if any(prior[k] != job[k] for k in ("nonce", "mission_id", "attempt_id")):
                raise Refused("PRODUCT_JOB_REBOUND")
            return prior
        c.execute("INSERT INTO afo_product_jobs VALUES (?,?)", (job_id, canonical(job).decode()))
    Executions(store).reserve(job_id, mission, nonce)
    return job


def install(ws, binding):
    immutable_json(Path(ws) / ".forge-run/durable-binding.json", binding)


def resolve(store, job_id):
    with store.tx() as c:
        row = c.execute("SELECT record FROM afo_product_jobs WHERE job_id=?", (job_id,)).fetchone()
    if not row:
        raise Refused("PRODUCT_JOB_UNBOUND")
    job = json.loads(row[0])
    p = Path(job["binding"])
    if p.is_symlink() or not p.is_file():
        raise Refused("PRODUCT_BINDING_UNAVAILABLE")
    binding = json.loads(p.read_text())
    if binding != {
        k: job[k] for k in ("job_id", "nonce", "mission_id", "order_id", "attempt_id", "operations_epoch") if k in job
    }:
        raise Refused("PRODUCT_BINDING_CHANGED")
    return job


def from_native(store, native_id, *, client=None):
    with store.tx() as c:
        rows = c.execute("SELECT record FROM afo_execution_liveness").fetchall()
    matches = [json.loads(r[0]) for r in rows if native_id in json.loads(r[0])["native_run_ids"]]
    if not matches:
        import re
        from ..fabro.client import FabroClient, FabroUnavailable, load_token

        if not isinstance(native_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", native_id):
            raise Refused("NATIVE_REQUEST_IDENTITY_INVALID")
        owned = client is None
        client = client or FabroClient(token=load_token(), timeout=3)
        try:
            native = client.get_run(native_id)
        except (OSError, ValueError, FabroUnavailable) as exc:
            raise Refused("NATIVE_REQUEST_IDENTITY_UNCONFIRMED") from exc
        finally:
            if owned:
                client.close()
        labels = native.get("labels") or {}
        job_id = labels.get("afo_agent")
        execution = Executions(store).get(job_id) if job_id else None
        if (
            not execution
            or execution["admission_state"] != "DISPATCH_INTENT_RECORDED"
            or execution["launch_nonce"] != labels.get("afo_nonce")
            or execution["authorization_state"] != "VALID"
            or execution["task_outcome"] != "ACTIVE"
            or execution["resource_lease"] != "HELD"
        ):
            raise Refused("NATIVE_REQUEST_IDENTITY_UNCONFIRMED")
        # Fabro can reach the gateway before detach's acknowledgement reaches the
        # controller. Adopt the authoritative native nonce, never launch a second run.
        matches = [Executions(store).adopt(job_id, [native_id])]
    if len(matches) != 1 or matches[0]["identity_state"] != "CONFIRMED":
        raise Refused("NATIVE_REQUEST_IDENTITY_UNCONFIRMED")
    rec = matches[0]
    return {"job_id": rec["job_id"], "nonce": rec["launch_nonce"]}


def reconcile(store, eff, client):
    from .local_agent import authorized

    ex = Executions(store)
    out = []
    with store.tx() as c:
        jobs = [json.loads(r[0]) for r in c.execute("SELECT record FROM afo_product_jobs")]
    for job in jobs:
        rec = ex.get(job["job_id"])
        if not rec or rec["resource_lease"] == "RELEASED":
            continue
        order = store.order(job["order_id"])
        valid = (
            order is not None
            and order["state"] in ("ADMITTED", "RUNNING", "WAITING_RECOVERY", "VALIDATING")
            and eff.sha256 == job["policy_sha256"]
            and authorized(order, eff, job["model"])
            and time.time() < job["deadline_epoch"]
        )
        if not valid and rec["authorization_state"] == "VALID":
            ex.revoke(job["job_id"])
            ex.outcome(job["job_id"], "BLOCKED", "PRODUCT_AUTHORITY_OR_OUTCOME_TERMINAL")
        out.append(ex.reconcile(job["job_id"], client, cancel=not valid))
    return out
