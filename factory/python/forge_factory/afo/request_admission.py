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
    if not isinstance(binding, dict) or set(binding) != {"job_id", "nonce", "request_id"}:
        raise Refused("GENERATION_BINDING_REQUIRED")
    ctx = Context.from_job(store, binding["job_id"])
    if ctx.launch_nonce != binding["nonce"]:
        raise Refused("GENERATION_NONCE_MISMATCH")
    with store.tx() as c:
        row = c.execute("SELECT record FROM afo_local_agent_jobs WHERE job_id=?", (ctx.job_id,)).fetchone()
        live = c.execute("SELECT record FROM afo_execution_liveness WHERE job_id=?", (ctx.job_id,)).fetchone()
    job = json.loads(row[0])
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
            and local_agent.enabled(job["role"], eff)
            and local_agent.authorized(order, eff, job["model"])
        )

    measured = measure_request(body)
    cap = body.get("max_tokens", body.get("max_completion_tokens"))
    if type(cap) is not int or cap < 1:
        raise Refused("PROVIDER_OUTPUT_CAP_REQUIRED")
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
