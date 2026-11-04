"""M6 provenance adapter for existing Line Conductor orders and the existing local recovery agent.

This first boundary binds context only. It neither admits a job nor lifts development-policy
deferral. A future dispatch must separately prove role qualification, signed model authority,
budget admission and the existing locked SKILL/MCP protocol; a valid driver run proves none of those.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

from ..common import state_dir
from . import line_campaign as campaign
from . import line_orders as orders


class BindingRefused(ValueError):
    pass


def _read(path: Path, code: str) -> dict:
    try:
        value = json.loads(path.read_text())
    except (ValueError, OSError):
        raise BindingRefused(code) from None
    if not isinstance(value, dict):
        raise BindingRefused(code)
    return value


def _require(condition, code: str) -> None:
    if not condition:
        raise BindingRefused(code)


def _revision(root: Path, revision: str) -> str:
    if not isinstance(revision, str) or not campaign.RX["factory_revision"].fullmatch(revision):
        raise BindingRefused("SOURCE_REVISION_INVALID")
    result = subprocess.run(["git", "rev-parse", "--verify", revision + "^{commit}"], cwd=root,
                            capture_output=True, text=True, timeout=30)
    _require(result.returncode == 0, "SOURCE_REVISION_UNRESOLVED")
    return result.stdout.strip()


def bind_order(store, order_id: str, attempt_id: str, *, campaign_path: Path,
               policy_path: Path | None = None, auth_base: Path | None = None, allowed_signers: Path | None = None,
               now: float | None = None) -> dict:
    """Read-only M3 identity/grant binding, also usable before a fresh product workspace exists."""
    row = store.order(order_id)
    _require(row is not None, "LINE_QUEUE_ORDER_ABSENT")
    attempts = [a for a in store.attempts(order_id) if a["attempt_id"] == attempt_id]
    _require(len(attempts) == 1, "LINE_QUEUE_ATTEMPT_MISMATCH")
    try:
        envelope = json.loads(row["envelope"])
    except (TypeError, ValueError):
        raise BindingRefused("LINE_QUEUE_ENVELOPE_INVALID") from None
    _require(isinstance(envelope, dict), "LINE_QUEUE_ENVELOPE_INVALID")
    wo = row["request_id"]
    _require(isinstance(wo, str) and campaign.RX["wo"].fullmatch(wo), "LINE_ORDER_NAME_INVALID")
    _require(envelope.get("request_id") == wo and row["tenant_scope"] == envelope.get("tenant_scope"),
             "LINE_QUEUE_IDENTITY_MISMATCH")
    root = state_dir().resolve()
    spec_path = root / "supervisor/line-orders" / f"{wo}.json"
    _require(spec_path.resolve().is_relative_to(root / "supervisor/line-orders"), "LINE_SPEC_PATH_ESCAPE")
    spec = _read(spec_path, "LINE_SPEC_ABSENT_OR_INVALID")
    digest = orders._digest(spec)
    _require(spec.get("schema") == orders.ORDER_SCHEMA and spec.get("wo") == wo
             and spec.get("digest") == digest == envelope.get("payload_digest"), "LINE_SPEC_DIGEST_MISMATCH")
    try:
        camp = campaign.parse(Path(campaign_path), require_approval=True)
    except (campaign.CampaignError, OSError, ValueError):
        raise BindingRefused("LINE_CAMPAIGN_UNAPPROVED_OR_INVALID") from None
    _require(camp.line == "local" and envelope.get("tenant_scope") == "line-local", "LINE_SCOPE_MISMATCH")
    _require(camp.sha256 == spec.get("campaign_sha256") == envelope.get("manifest_sha256")
             == row["manifest_sha256"] and camp.rel == spec.get("campaign_file")
             == envelope.get("input_manifest_ref") == row["input_manifest_ref"]
             and camp.commit == spec.get("campaign_commit")
             and envelope.get("approved_by") == f"campaign-commit:{camp.commit}", "LINE_CAMPAIGN_BINDING_MISMATCH")
    candidates = [lin for lin in camp.lineages if lin.key == spec.get("lineage")]
    _require(len(candidates) == 1, "LINEAGE_ABSENT")
    lin = candidates[0]
    _require(lin.status == "ACTIVE" and lin.sha256 == spec.get("lineage_sha")
             and lin.campaign_id == spec.get("campaign_id") and spec.get("phase") in lin.phases,
             "LINEAGE_BINDING_MISMATCH")
    for spec_key, lineage_key, envelope_key in (
        ("revision", "factory_revision", "git_revision"), ("profile", "profile", "model_profile"),
        ("example", "example", "target"), ("driver_class", "driver_class", "driver_class"),
        ("purpose", "purpose", "safety_scope"),
    ):
        _require(spec.get(spec_key) == getattr(lin, lineage_key) == envelope.get(envelope_key),
                 f"LINE_{spec_key.upper()}_MISMATCH")
    _require(spec.get("run_model") == lin.run_model, "LINE_MODEL_MISMATCH")
    policy = orders.load_policy(policy_path)
    _require(policy.get("line") == "local", "LINE_POLICY_SCOPE_MISMATCH")
    grant = orders.verify_grant(policy, now=time.time() if now is None else now, base=auth_base,
                                allowed_signers=allowed_signers)
    _require(grant.allow, f"LINE_AUTH_REFUSED:{grant.code}")
    _require(grant.authorization_id == spec.get("authorization_id") == envelope.get("authorization_ref"),
             "LINE_AUTH_BINDING_MISMATCH")
    permission = grant.permit("recover_workorder", {"order_id": wo, "driver_class": lin.driver_class, "model": lin.profile})
    _require(permission.allow, f"LINE_AUTH_RECOVERY_REFUSED:{permission.code}")
    return {"row": row, "spec": spec, "campaign": camp, "lineage": lin, "grant": grant,
            "order_digest": digest}


def bind(store, order_id: str, attempt_id: str, *, workspace: Path, campaign_path: Path,
         policy_path: Path | None = None, auth_base: Path | None = None, allowed_signers: Path | None = None,
         now: float | None = None) -> dict:
    """Read-only source provenance, never an admission or qualification receipt."""
    data = bind_order(store, order_id, attempt_id, campaign_path=campaign_path, policy_path=policy_path,
                      auth_base=auth_base, allowed_signers=allowed_signers, now=now)
    row, spec, camp, lin, grant = (data[k] for k in ("row", "spec", "campaign", "lineage", "grant"))
    digest = data["order_digest"]
    wo = row["request_id"]
    root = state_dir().resolve()
    expected = root / "workorders" / wo / "workspace"
    ws = Path(workspace).resolve()
    _require(ws == expected.resolve() and ws.is_relative_to(root / "workorders") and ws.is_dir(),
             "SOURCE_WORKSPACE_MISMATCH")
    for relative in (".forge-run/manifest.json", ".forge-run/model-profile.json"):
        _require((ws / relative).resolve().is_relative_to(ws), "SOURCE_PROVENANCE_PATH_ESCAPE")
    man = _read(ws / ".forge-run/manifest.json", "SOURCE_MANIFEST_INVALID")
    revision = _revision(camp.root, lin.factory_revision)
    provenance = man.get("factory_revision") or {}
    _require(man.get("work_order") == wo and isinstance(provenance, dict)
             and provenance.get("commit") == revision and provenance.get("dirty") is False,
             "SOURCE_FACTORY_PROVENANCE_MISMATCH")
    scope = man.get("phase_scope") or {}
    _require(isinstance(scope, dict) and scope.get("stop_after") == spec.get("stop_after")
             == spec.get("phase"), "SOURCE_PHASE_SCOPE_MISMATCH")
    from ..lrtx.profile import ProfileRefused, load

    try:
        profile = load(lin.profile)
    except (ProfileRefused, OSError, ValueError):
        raise BindingRefused("SOURCE_LOCAL_PROFILE_INVALID") from None
    local = man.get("local_profile") or {}
    _require(isinstance(local, dict) and local.get("id") == lin.profile
             and type(local.get("version")) is int and local["version"] == profile["version"]
             and local.get("config") == profile["_path"] and local.get("config_sha256") == profile["_sha256"],
             "SOURCE_LOCAL_PROFILE_BINDING_CHANGED")
    model_profile = _read(ws / ".forge-run/model-profile.json", "SOURCE_MODEL_PROFILE_INVALID")
    _require(model_profile.get("default") == lin.run_model, "SOURCE_MODEL_PROFILE_MISMATCH")
    return {"schema": "forge-c/line-recovery-context/1", "status": "BOUND_CONTEXT_ONLY_NO_DISPATCH",
            "dispatch_authorized": False, "role_qualification": "NOT_EVALUATED", "order_id": order_id,
            "attempt_id": attempt_id, "work_order": wo, "source_workspace": str(ws), "source_revision": revision,
            "order_digest": digest, "campaign_sha256": camp.sha256, "campaign_commit": camp.commit,
            "lineage_sha256": lin.sha256, "profile_sha256": profile["_sha256"], "profile": lin.profile,
            "model": lin.run_model, "authorization": grant.view()}


ORIGIN_KEYS = {"campaign_path", "policy_path", "auth_base", "allowed_signers"}


def context(store, order_id, attempt_id, workspace, origin):
    """Controller configuration only; never read origin overrides from model output or a case."""
    _require(isinstance(origin, dict) and "campaign_path" in origin and set(origin) <= ORIGIN_KEYS,
             "LINE_ORIGIN_CONFIGURATION_INVALID")
    _require(store.path.resolve() == (state_dir() / "supervisor/line-queue.sqlite3").resolve(),
             "LINE_QUEUE_STORE_MISMATCH")
    paths = {}
    for key, value in origin.items():
        _require(isinstance(value, str) and Path(value).is_absolute(), "LINE_ORIGIN_PATH_INVALID")
        paths[key] = Path(value)
    return bind(store, order_id, attempt_id, workspace=workspace, **paths)


def valid_job(job, store=None):
    """Reverify a line-origin job before every dispatch/poll, including after process restart."""
    if "line_origin" not in job:
        return True
    from ..common import canonical_json, sha256_bytes
    from .queue import Store

    try:
        current = context(store or Store(state_dir() / "supervisor/line-queue.sqlite3"), job["order_id"],
                          job["attempt_id"], Path(job["source_workspace"]), job["line_origin"])
        return sha256_bytes(canonical_json(current)) == job.get("line_context_sha256")
    except (BindingRefused, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return False


def make_planner(store, eff, *, origin, line_role_authority_ref=None):
    """Use the existing bounded Fabro planner lifecycle; no queue, scheduler or inferred grant is added."""
    from . import local_agent

    return local_agent.make_planner(store, eff, line_origin=origin, line_role_authority_ref=line_role_authority_ref)
