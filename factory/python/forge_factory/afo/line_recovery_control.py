"""Explicit controller-owned M6 authority. This creates no grant or capability receipt.

Only a separately signed exact configuration can introduce finite mission limits or
role inputs. A driver's source workspace is never evidence of planner competence.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path

from .durable import Refused, digest

SCHEMA = "forge-c/line-recovery-control/1"


def revision():
    from ..workorder import factory_revision

    return factory_revision()


def profile_identity(profile):
    from ..lrtx.profile import load

    selected = load(profile)
    if selected.get("local_only") is not True or selected.get("provider") != "ollama":
        raise Refused("LINE_RECOVERY_LOCAL_PROFILE_REQUIRED")
    return selected["_sha256"]


def read(ref):
    from .fault_observer import bound_json

    if (not isinstance(ref, dict) or set(ref) != {"path", "sha256"}
            or not isinstance(ref["path"], str) or not Path(ref["path"]).is_absolute()
            or not re.fullmatch(r"[0-9a-f]{64}", str(ref["sha256"]))):
        raise Refused("LINE_RECOVERY_CONTROL_REFERENCE_INVALID")
    value = bound_json(ref)
    required = {"schema", "source_revision", "policy_sha256", "authorization_ref", "profile", "profile_sha256",
                "operations_intent", "mission", "role_capabilities", "product_role_trial"}
    optional = {"product_role_trials", "qualified_local_alternatives", "native_transport_ref"}
    if (not isinstance(value, dict) or not required <= set(value) or set(value) - required - optional
            or value.get("schema") != SCHEMA):
        raise Refused("LINE_RECOVERY_CONTROL_INVALID")
    if not isinstance(value["operations_intent"], str) or not Path(value["operations_intent"]).is_absolute():
        raise Refused("LINE_RECOVERY_OPERATIONS_INTENT_REQUIRED")
    mission = value["mission"]
    from .mission_ledger import validate_limits

    if not isinstance(mission, dict) or set(mission) != {"mission_id", "lineage", "limits"}:
        raise Refused("LINE_RECOVERY_FINITE_MISSION_REQUIRED")
    if not all(isinstance(mission[k], str) and re.fullmatch(r"[A-Za-z0-9_.:/-]{1,160}", mission[k])
               for k in ("mission_id", "lineage")):
        raise Refused("LINE_RECOVERY_FINITE_MISSION_REQUIRED")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}", mission["mission_id"]):
        raise Refused("LINE_RECOVERY_MISSION_EXECUTION_ID_INVALID")
    validate_limits(mission["limits"])
    if not isinstance(value["role_capabilities"], dict):
        raise Refused("LINE_RECOVERY_ROLE_INPUTS_INVALID")
    if (not isinstance(value.get("product_role_trials", {}), dict)
            or not isinstance(value.get("qualified_local_alternatives", []), list)):
        raise Refused("LINE_RECOVERY_ROLE_INPUTS_INVALID")
    return value


def configuration(ref, eff, *, request=None):
    return _configuration(ref, eff, request=request, actual=revision())


def controller_configuration(ref, eff, *, target_revision, request):
    """Only queue coordination may run from a separate conductor checkout.

    The target is the already resolved immutable campaign run revision. This
    grants no model execution: the external worker/native request path always
    calls configuration(), which checks its own actual clean source checkout.
    """
    return _configuration(ref, eff, request=request, actual={"commit": target_revision, "dirty": False})


def _configuration(ref, eff, *, request, actual):
    from . import authz

    value = read(ref)
    if (actual.get("dirty") is not False or actual.get("commit") != value["source_revision"]
            or not re.fullmatch(r"[0-9a-f]{40}", str(value["source_revision"]))):
        raise Refused("LINE_RECOVERY_EXECUTING_REVISION_MISMATCH")
    if (value["policy_sha256"] != eff.sha256 or value["authorization_ref"] != eff.get("authorization_ref")
            or profile_identity(value["profile"]) != value["profile_sha256"]):
        raise Refused("LINE_RECOVERY_CONTROL_BINDING_CHANGED")
    from . import owner_supervised_development as development

    if eff.mode == development.MODE:
        development.control_authorized(ref, value, eff, request)
        return value
    decision = authz.find(eff.mode, eff.sha256 or "", ref=value["authorization_ref"],
                          action="recover_workorder", request=request or {})
    if not decision.allow:
        raise Refused(decision.code)
    grant = json.loads((authz.AUTH_DIR / (value["authorization_ref"] + ".json")).read_text())
    if grant.get("signed_runbook_ref") != "line-recovery-014:" + digest(value):
        raise Refused("LINE_RECOVERY_CONTROL_NOT_OWNER_SIGNED")
    try:
        expiry = datetime.fromisoformat(grant["expires_utc"].replace("Z", "+00:00")).timestamp()
    except (ValueError, KeyError, TypeError):
        raise Refused("LINE_RECOVERY_CONTROL_EXPIRY_INVALID") from None
    if not time.time() < value["mission"]["limits"]["deadline"] <= expiry:
        raise Refused("LINE_RECOVERY_MISSION_OUTSIDE_AUTHORITY")
    return value


def role_inputs(ref, eff):
    value = configuration(ref, eff)
    return {key: value[key] for key in ("role_capabilities", "product_role_trial")}


def require_job_binding(job, control, *, store=None):
    """Intersect a signed control with the actual intent and linked effective mission; never refill it."""
    from ..common import state_dir
    from . import mission_capacity, mission_deadline
    from .queue import ReadSnapshot

    if store is None:
        with ReadSnapshot(state_dir() / "supervisor/line-queue.sqlite3", max_rows=100, timeout_s=3) as reader:
            return require_job_binding(job, control, store=reader)
    native = job.get("native_context") or {}
    from . import owner_supervised_development as development

    if development.selected():
        development.require_job_context(job)
    if (native.get("FORGE_OPERATIONS_INTENT") != control["operations_intent"]
            or native.get("FORGE_AFO_QUEUE_SCOPE") != "line-local"):
        raise Refused("LINE_ROLE_OPERATIONS_CONTEXT_MISMATCH")
    if (job.get("mission_id") != control["mission"]["mission_id"] or job.get("profile") != control["profile"]
            or job.get("profile_sha256") != control["profile_sha256"]
            or job.get("factory_revision", {}).get("commit") != control["source_revision"]
            or job.get("factory_revision", {}).get("dirty") is not False
            or job.get("policy_sha256") != control["policy_sha256"]):
        raise Refused("LINE_ROLE_MISSION_OR_SOURCE_MISMATCH")
    with store.tx() as c:
        link = c.execute("SELECT mission_id FROM afo_mission_orders WHERE order_id=?", (job["order_id"],)).fetchone()
        row = c.execute("SELECT record FROM afo_missions WHERE mission_id=?", (job["mission_id"],)).fetchone()
        if not link or link[0] != job["mission_id"] or not row:
            raise Refused("LINE_ROLE_LINKED_MISSION_REQUIRED")
        base = json.loads(row[0])
        current = mission_capacity.effective(c, base, mission_deadline.effective(c, base))
    if current["lineage"] != control["mission"]["lineage"] or current["limits"] != control["mission"]["limits"]:
        raise Refused("LINE_ROLE_SIGNED_MISSION_LIMITS_MISMATCH")
    return True


def native_envelope_minimum(job):
    """Actual sanitizer lower bound, not a guessed native SDK default or capability proof."""
    from ..llm_gateway import sanitize_request
    from ..lrtx.profile import load

    profile = load(job["profile"])
    body = sanitize_request({"model": job["model"], "max_tokens": 1, "messages": []},
                            policy=(profile.get("gateway") or {}).get("reasoning") or {}, role=job.get("role"))
    output = body["max_tokens"]
    # A real serialized input is nonempty. Even this lower bound must fit;
    # request admission later measures and checks the complete actual body.
    report = {"status": "LOWER_BOUND_FITS_NOT_QUALIFICATION", "profile_sha256": profile["_sha256"],
              "minimum_positive_output_cap": output, "minimum_input_tokens": 1,
              "minimum_total_tokens": output + 1, "reserved_tokens": job["reserved_tokens"],
              "native_sdk_default": "NOT_MEASURED", "model_calls": 0}
    if type(job["reserved_tokens"]) is not int or job["reserved_tokens"] < output + 1:
        raise Refused("RECOVERY_NATIVE_ENVELOPE_EXCEEDS_RESERVATION", f"minimum={output+1},reserved={job['reserved_tokens']}")
    return report


def require_native_transport(job, *, cfg=None, control=None):
    """Products/native maintenance need measured correlation; planner explicit-body transport is separate."""
    import os

    from .line_launcher import LineConfig
    from .policy import load

    if control is None:
        if not job.get("line_role_authority_ref"):
            raise Refused("LINE_NATIVE_TRANSPORT_MEASUREMENT_REQUIRED")
        control = configuration(job["line_role_authority_ref"], load())
    ref = control.get("native_transport_ref")
    if not ref:
        raise Refused("LINE_NATIVE_TRANSPORT_MEASUREMENT_REQUIRED")
    if os.environ.get("FORGE_DURABLE_NATIVE_HEADER") != "1":
        raise Refused("LINE_NATIVE_TRANSPORT_OPT_IN_REQUIRED")
    try:
        from .line_native_transport import require
    except ModuleNotFoundError:
        raise Refused("LINE_NATIVE_TRANSPORT_VALIDATOR_UNAVAILABLE") from None
    measured = require(ref, job=job, cfg=cfg or LineConfig.from_env())
    if not isinstance(measured, dict):
        raise Refused("LINE_NATIVE_TRANSPORT_PROOF_INVALID")
    return measured
