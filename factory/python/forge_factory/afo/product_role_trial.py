"""Separately signed, finite product-role experiments; never capability receipts.

The normal production grant and mission limits still admit every job/request.
An additional owner-signed qualification grant permits measuring unqualified
roles on exactly the frozen orders/configurations, without claiming competence.
"""

from __future__ import annotations

import json
import time

from ..common import state_dir
from .durable import Refused, digest, strict_json


def resolve(ref):
    from .diagnosis_packet import scoped_path

    sha = ref.get("sha256") if isinstance(ref, dict) else None
    if ref != {"path": f"afo/product-role-trials/{sha}.json", "sha256": sha}:
        raise Refused("PRODUCT_ROLE_TRIAL_REFERENCE_INVALID")
    document = strict_json(scoped_path(state_dir(), ref["path"]).read_bytes(), 4 * 1024 * 1024)
    if digest(document) != sha or document.get("schema") != "forge-c/product-role-trial/1":
        raise Refused("PRODUCT_ROLE_TRIAL_CHANGED")
    return document


def authorized(ref, job, eff):
    from ..lrtx.role_capability import key
    from . import authz
    from .local_agent import request_for
    from .queue import Store

    trial = resolve(ref)
    order = Store().order(job["order_id"])
    if (
        not order
        or trial.get("qualification_only") is not True
        or job["order_id"] not in trial.get("order_ids", [])
        or trial.get("source_revision") != (job.get("factory_revision") or {}).get("commit")
        or trial.get("profile") != job.get("profile")
        or trial.get("model") != job.get("model")
        or type(trial.get("deadline_epoch")) not in (int, float)
        or not time.time() < trial["deadline_epoch"]
    ):
        raise Refused("PRODUCT_ROLE_TRIAL_BINDING_CHANGED")
    roles = trial.get("roles")
    allowed = {f"swe{i}-{r}" for i in range(1, 7) for r in ("author", "inspector")}
    allowed |= {"afo-recovery-planner", "afo-factory-maintainer"}
    if not isinstance(roles, dict) or not roles or not set(roles) <= allowed:
        raise Refused("PRODUCT_ROLE_TRIAL_ROLES_INVALID")
    for role, identities in roles.items():
        if not isinstance(identities, list) or not 1 <= len(identities) <= 32:
            raise Refused("PRODUCT_ROLE_TRIAL_CONFIGURATIONS_UNBOUNDED")
        for identity in identities:
            key(identity)
            if (
                identity["role"] != role
                or identity["adapter_revision"] != trial["source_revision"]
                or identity["model_digest"] != job.get("model_digest")
                or identity["precision"] != job.get("precision")
                or identity["context_tokens"] > 65536
            ):
                raise Refused("PRODUCT_ROLE_TRIAL_CONFIGURATION_CHANGED")
    authref = trial.get("authorization_ref")
    grant = authz.find(eff.mode, eff.sha256 or "", ref=authref, action="recover_workorder", request=request_for(order))
    if not grant.allow:
        raise Refused(grant.code)
    record = json.loads((authz.AUTH_DIR / f"{authref}.json").read_text())
    if record.get("signed_runbook_ref") != "qualification-product-014:" + ref["sha256"]:
        raise Refused("PRODUCT_ROLE_TRIAL_NOT_OWNER_SIGNED")
    return trial


def bind(ref, job, eff):
    if ref:
        authorized(ref, job, eff)
        job["product_role_trial"] = ref
    return job


def identity(job, role, body, eff):
    trial = authorized(job["product_role_trial"], job, eff)
    if not isinstance(body, dict):
        raise Refused("PRODUCT_ROLE_TRIAL_REQUEST_REQUIRED")
    mode = (body.get("response_format") or {}).get("type") or ("tool" if body.get("tools") else "unconstrained")
    candidates = [
        i
        for i in trial["roles"].get(role, [])
        if i["schema_mode"] == mode
        and i["reasoning"] == body.get("reasoning_effort", "none")
        and all(body.get(k) == v for k, v in i["sampling"].items())
    ]
    if len(candidates) != 1:
        raise Refused("PRODUCT_ROLE_TRIAL_CONFIGURATION_UNDECLARED")
    return candidates[0]
