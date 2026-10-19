"""AFO-T003 (AFO-FR-002/004, AT-063/064/065) - the authority intersection deciding every AFO action.

An action is allowed only when every authority that owns it allows it:
  1. the constitutional floor: some actions are never AFO's to take, whatever any policy or authorization says;
  2. the AFO effective mode (policy.load) and, in PILOT/ACTIVE, the signed authorization's action list and scope;
  3. for actions CRE owns (service recovery, retries of guarded side effects), the CRE policy's own mode and
     pre-authorized action list - AFO never edits CRE configuration and never enables CRE ACTIVE implicitly.
Every decision is recorded (AFO-FR-006).
"""
from __future__ import annotations

from dataclasses import dataclass

FORBIDDEN = {  # constitutional floor (CLAUDE.md guardrails, 002/004 policies): never an AFO action
    "source_deploy", "source_auto_merge", "promote_factory_code", "safety_approval", "release_signing",
    "edit_safety_policy", "edit_cre_policy", "edit_afo_policy", "edit_holdout_or_oracle", "edit_release_archive",
    "edit_baselined_evidence", "enable_cre_mode", "hardware_flash",
}
OBSERVE = {"read_status", "simulate_decision", "record_telemetry", "health_poll"}
WORK = {"submit_workorder", "launch_workorder", "reconcile_run", "recover_workorder", "finalize_blocked",
        "dead_letter", "notify"}
CRE_OWNED = {"service_restart", "service_reload", "retry_guarded_side_effect"}


@dataclass(frozen=True)
class Decision:
    allow: bool
    code: str
    action: str
    afo_mode: str
    cre_mode: str | None = None


def cre_mode() -> str:
    from ..reliability.policy import load

    try:
        return load().mode
    except Exception:  # noqa: BLE001 - an unloadable CRE policy grants nothing
        return "UNAVAILABLE"


def decide(action: str, request: dict | None = None, *, afo=None, cre=None, log: bool = True) -> Decision:
    from . import authz
    from .policy import load, record

    afo = afo or load()
    d = _decide(action, request or {}, afo, cre, authz)
    if log:
        record({"kind": "authority", "action": action, "allow": d.allow, "code": d.code, "afo_mode": d.afo_mode,
                "cre_mode": d.cre_mode, "authorization_id": afo.authorization_id})
    return d


def _decide(action: str, request: dict, afo, cre, authz) -> Decision:
    m = afo.mode
    if action in FORBIDDEN:
        return Decision(False, "FORBIDDEN_BY_CONSTITUTION", action, m)
    if action not in OBSERVE | WORK | CRE_OWNED:
        return Decision(False, "UNKNOWN_ACTION", action, m)
    if m == "DISABLED":
        return Decision(False, "AFO_DISABLED", action, m)
    if action in OBSERVE:
        return Decision(True, "OBSERVE_ALLOWED", action, m)
    if m == "OBSERVE_ONLY":
        return Decision(False, "OBSERVE_ONLY_NO_SIDE_EFFECTS", action, m)
    a = authz.find(m, afo.sha256 or "", ref=afo.get("authorization_ref"), action=action, request=request)
    if not a.allow:
        return Decision(False, f"AFO_{a.code}", action, m)
    if action in CRE_OWNED:
        cp = cre if cre is not None else _cre_policy()
        cm = getattr(cp, "mode", "UNAVAILABLE")
        if cp is None or not cp.automatic_action_allowed(action):
            return Decision(False, "CRE_NOT_AUTHORIZED", action, m, cm)
        return Decision(True, "ALLOWED_AFO_AND_CRE", action, m, cm)
    return Decision(True, "ALLOWED", action, m)


def _cre_policy():
    from ..reliability.policy import load

    try:
        return load()
    except Exception:  # noqa: BLE001
        return None
