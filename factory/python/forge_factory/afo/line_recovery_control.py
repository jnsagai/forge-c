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
    optional = {"product_role_trials", "qualified_local_alternatives"}
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
