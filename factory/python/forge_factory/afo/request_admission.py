"""Gateway bridge to the Conductor ledger; validates trusted live job bindings."""

from __future__ import annotations

import json
import time

from .completion_receipt import Context
from .diagnosis_packet import measure_request
from .durable import Refused
from .mission_ledger import MissionLedger


def reserve(store, binding, body, *, eff=None):
    from . import local_agent
    from .policy import load

    eff = eff or load()
    if (
        not isinstance(binding, dict)
        or not {"job_id", "nonce", "request_id"} <= set(binding)
        or not set(binding) <= {"job_id", "nonce", "request_id", "role"}
    ):
        raise Refused("GENERATION_BINDING_REQUIRED")
    product = binding["job_id"].startswith("afo-product-")
    if product:
        from .product_job import resolve
        from types import SimpleNamespace

        job = resolve(store, binding["job_id"])
        ctx = SimpleNamespace(
            job_id=job["job_id"], mission_id=job["mission_id"], order_id=job["order_id"], launch_nonce=job["nonce"]
        )
    else:
        ctx = Context.from_job(store, binding["job_id"])
        with store.tx() as c:
            row = c.execute("SELECT record FROM afo_local_agent_jobs WHERE job_id=?", (ctx.job_id,)).fetchone()
        job = json.loads(row[0])
    if ctx.launch_nonce != binding["nonce"]:
        raise Refused("GENERATION_NONCE_MISMATCH")
    with store.tx() as c:
        live = c.execute("SELECT record FROM afo_execution_liveness WHERE job_id=?", (ctx.job_id,)).fetchone()
    execution = json.loads(live[0]) if live else {}
    if (
        execution.get("task_outcome") != "ACTIVE"
        or execution.get("authorization_state") != "VALID"
        or execution.get("resource_lease") != "HELD"
        or job.get("model") != body.get("model")
    ):
        raise Refused("GENERATION_EXECUTION_NOT_ACTIVE")
    order = store.order(ctx.order_id)

    def authorized():
        return (
            time.time() < job["deadline_epoch"]
            and eff.sha256 == job["policy_sha256"]
            and (product or local_agent.enabled(job["role"], eff))
            and local_agent.authorized(order, eff, job["model"])
        )

    measured = measure_request(body)
    caps = [body[k] for k in ("max_tokens", "max_completion_tokens") if body.get(k) is not None]
    if len(caps) != 1:
        raise Refused("PROVIDER_OUTPUT_CAP_MISSING_OR_AMBIGUOUS")
    cap = caps[0]
    if type(cap) is not int or cap < 1:
        raise Refused("PROVIDER_OUTPUT_CAP_REQUIRED")
    if product or job.get("durable_protocol") or job.get("durable_native"):
        from ..lrtx.role_capability import admit_job
        from ..llm_gateway import detect_role

        role = binding.get("role") or job.get("role") or detect_role(body.get("messages") or [])
        if not role:
            raise Refused("CAPABILITY_LIMIT", "native role identity is unqualified")
        admit_job(job, role, input_tokens=measured["input_tokens"], output_tokens=cap, body=body)
    rec = MissionLedger(store).reserve_request(
        ctx.mission_id,
        ctx.job_id,
        binding["request_id"],
        body_sha256=measured["sha256"],
        input_tokens=measured["input_tokens"],
        output_cap=cap,
        authorize=authorized,
    )
    if rec["replay"]:
        raise Refused("GENERATION_ALREADY_RESERVED_OR_SENT")
    from .execution_lifecycle import Executions

    Executions(store)._save_evidence(
        ctx.job_id,
        "REQUEST_METADATA:" + rec["request_id"],
        {
            "request_id": rec["request_id"],
            "body_sha256": measured["sha256"],
            "measurement": measured,
            "model": job["model"],
            "role": binding.get("role") or job.get("role"),
            "schema_mode": (body.get("response_format") or {}).get("type"),
            "policy_sha256": eff.sha256,
            "output_cap": cap,
        },
    )
    return rec


def unbound_allowed(store) -> bool:
    import os

    if os.environ.get("FORGE_DURABLE_AUTONOMY") == "1":
        return False
    with store.tx() as c:
        row = c.execute("SELECT holder FROM afo_resource_ownership WHERE resource='inference'").fetchone()
    return not row or row[0] is None


def reconcile(store, request_id, usage, *, completed=False):
    usage = usage or {}
    return MissionLedger(store).reconcile_request(
        request_id,
        input_tokens=usage.get("prompt_tokens"),
        cached_tokens=usage.get("prompt_cache_hit_tokens"),
        output_tokens=usage.get("completion_tokens"),
        quiescent=completed,
        evidence_ref="gateway-complete:" + request_id if completed else None,
    )


def start(store, rec, body):
    """Recheck authority after admission waiting, immediately before the ordered provider effect."""
    from . import local_agent
    from .policy import load
    from .durable import digest

    eff = load()
    with store.tx() as c:
        if rec["job_id"].startswith("afo-product-"):
            row = c.execute("SELECT record FROM afo_product_jobs WHERE job_id=?", (rec["job_id"],)).fetchone()
        else:
            row = c.execute("SELECT record FROM afo_local_agent_jobs WHERE job_id=?", (rec["job_id"],)).fetchone()
    job = json.loads(row[0]) if row else {}
    order = store.order(job["order_id"]) if job else None

    def authorized():
        from .operations import configured, Intent

        if configured() and Intent().read()["mode"] not in ("RUNNING", "PAUSED", "DRAINING"):
            return False
        return (
            order is not None
            and order["state"] in ("ADMITTED", "RUNNING", "WAITING_RECOVERY", "WAITING_EXTERNAL_CHANGE")
            and time.time() < job["deadline_epoch"]
            and eff.sha256 == job["policy_sha256"]
            and digest(body) == rec["body_sha256"]
            and local_agent.authorized(order, eff, job["model"])
        )

    return MissionLedger(store).start_request(rec["request_id"], authorize=authorized)
