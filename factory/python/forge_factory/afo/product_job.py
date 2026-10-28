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
    from .operations import Intent, configured

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
        "deadline_epoch": min(order["created_epoch"] + float(eff.get("budgets.max_order_wall_seconds")),
                              MissionLedger(store).snapshot(mission)["limits"]["deadline"]),
        "reserved_tokens": int(eff.get("budgets.max_model_tokens_per_order")),
    }
    allocations = manifest.get("product_attempt_token_reservations")
    if allocations is not None:
        if (not isinstance(allocations, list) or not allocations
                or any(type(n) is not int or not 0 < n <= job["reserved_tokens"] for n in allocations)
                or not 1 <= attempt["seq"] <= len(allocations)):
            raise Refused("PRODUCT_ATTEMPT_RESERVATION_INVALID")
        job["reserved_tokens"] = allocations[attempt["seq"] - 1]
    from ..workorder import factory_revision

    job["factory_revision"] = factory_revision()
    selected = next(
        (a for a in manifest.get("qualified_local_alternatives") or [] if a.get("model_profile") == job["model"]), None
    )
    job["role_capabilities"] = (selected or manifest).get("role_capabilities") or {}
    job["work_class"] = "PRODUCT"  # per-phase semantic size is not measured yet: admission refuses, never guesses
    job["profile"] = manifest.get("profile")
    if job["profile"]:
        from ..lrtx.profile import load as load_profile

        model_identity = load_profile(job["profile"])["models"]["allowed"][job["model"]]
        job["model_digest"] = model_identity["digest"]
        job["precision"] = model_identity["quantization"]
    from .product_role_trial import bind as bind_trial

    bind_trial(manifest.get("product_role_trial"), job, eff)
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
        if not rec:
            continue
        order = store.order(job["order_id"])
        rec = _failed_outcome(ex, job, rec, order)
        if rec["resource_lease"] == "RELEASED":
            continue
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
        reconciled = ex.reconcile(job["job_id"], client, cancel=not valid)
        out.append(_failed_outcome(ex, job, reconciled, order))
    return out


def _failed_outcome(ex, job, rec, order):
    """Project factual product failure even after native capacity was settled.

    A successful transport never proves product success. Independent recovery
    verification remains the only path to RECOVERED. This projection changes no
    physical-liveness proof, request accounting or resource ownership.
    """
    if rec["task_outcome"] != "ACTIVE":
        return rec
    if order and order["state"] in ("BLOCKED", "FAILED", "CANCELLED"):
        return ex.outcome(job["job_id"], "BLOCKED", "PRODUCT_ORDER_TERMINAL:" + order["state"])
    if not ex._evidence(job["job_id"], "NATIVE_TERMINAL"):
        return rec
    from .dispatch import package_verdict

    path = Path(job["workspace"]) / ".forge-run/package.json"
    try:
        raw = path.read_bytes()
        verdict = package_verdict(path)
        if verdict["verdict"] != "BLOCKED" or path.read_bytes() != raw:
            return rec
    except OSError:
        return rec  # unavailable package evidence does not establish a result
    import hashlib

    evidence = {
        "job_id": job["job_id"], "attempt_id": job["attempt_id"],
        "package_record_sha256": hashlib.sha256(raw).hexdigest(), "verdict": verdict,
    }
    ex._save_evidence(job["job_id"], "PRODUCT_FAILURE", evidence)
    return ex.outcome(job["job_id"], "BLOCKED", ("PRODUCT_PACKAGE_BLOCKED:" + verdict["reason"])[:200],
                      "product-failure:" + digest(evidence))
