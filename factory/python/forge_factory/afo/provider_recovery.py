"""Serving-instance evidence in the existing watchdog, execution and request ledgers.

The serving PID namespace contains BOTH gateway and model workers. Retiring it
ends queued sends as well as generation, preventing a delayed gateway request
from reaching a replacement provider after old capacity has been released.
"""

from __future__ import annotations

import json
import os

from .durable import Refused, canonical, digest


def current_instance():
    from ..lrtx import provider_process as provider, stack

    profile = os.environ.get("FORGE_OPERATIONS_PROFILE")
    if not stack.managed_serving() or not profile:
        return None
    instance = stack.serving_instance(stack.settings(profile))
    if instance["init"]["boot_id"] != provider.boot_id() or instance["init"]["pid_namespace"] != os.readlink("/proc/self/ns/pid"):
        raise Refused("REQUEST_OUTSIDE_MANAGED_SERVING_INSTANCE")
    return instance


def reconcile(store, job_id, instance, *, fenced_effect, retire=False):
    """Fence future sends, then require independent kernel proof for each old request.

    Native execution ownership is intentionally not released here. Fabro must
    still reconcile its actual run before Executions can release that lease.
    No usage, task outcome, semantic receipt or mission allowance is reset.
    """
    from ..lrtx import provider_process as provider
    from .execution_lifecycle import Executions
    from .mission_ledger import MissionLedger

    provider.validate(instance)
    identity = digest(instance)
    with store.tx() as c:
        requests = [
            json.loads(r[0])
            for r in c.execute("SELECT record FROM afo_request_ledger WHERE job_id=? AND state!='QUIESCENT'", (job_id,))
        ]
        if not requests:
            return {"ok": False, "code": "NO_UNCERTAIN_PROVIDER_REQUEST"}
        if any(r.get("provider_instance_sha256") != identity or r.get("provider_instance") != instance for r in requests):
            return {"ok": False, "code": "REQUEST_PROVIDER_LIFETIME_UNPROVEN"}
        old = c.execute(
            "SELECT record,sha256 FROM afo_execution_evidence WHERE job_id=? AND kind='GENERATION_FENCE'", (job_id,)
        ).fetchone()
        if old:
            fence = json.loads(old[0])
            if digest(fence) != old[1] or fence.get("provider_instance_sha256") != identity:
                raise Refused("GENERATION_FENCE_REBOUND")
        else:
            fence = {"job_id": job_id, "provider_instance_sha256": identity, "reason": "SERVING_LIFETIME_RECONCILIATION"}
            c.execute(
                "INSERT INTO afo_execution_evidence VALUES (?,?,?,?)",
                (job_id, "GENERATION_FENCE", canonical(fence).decode(), digest(fence)),
            )
    proof = provider.quiet(instance)
    if not proof and retire:
        proof = provider.stop(instance, fenced_effect=fenced_effect)
    if not proof:
        return {"ok": False, "code": "PROVIDER_QUIESCENCE_UNPROVEN"}
    ex = Executions(store)
    ex._save_evidence(job_id, "PROVIDER_QUIESCENCE:" + identity, proof)
    reference = "provider-quiescence:" + digest(proof)
    for request in requests:
        MissionLedger(store).reconcile_request(request["request_id"], quiescent=True, evidence_ref=reference)
    return {
        "ok": True,
        "code": "PROVIDER_QUIESCENT_NATIVE_RECONCILIATION_REQUIRED",
        "requests": len(requests),
        "provider_instance_sha256": identity,
        "proof_ref": reference,
    }
