"""AFO M3 production wiring: the real Fabro listing, launcher and workspace mapping used by the Conductor cycle.

The launcher calls `workorder.run(..., detach=True, labels=...)` - the same path an operator uses - with the
pinned launch manifest (example, provided LL, model, provider, Codex authors, optional resume source). The view lists
recent runs of the Fabro server the factory launches on (FORGE_FABRO_URL); unreachable -> None (never "no runs").
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from ..common import REPO_ROOT, state_dir


def fabro_view(limit: int = 200):
    from ..fabro.client import FabroClient, FabroUnavailable, load_token

    try:
        with FabroClient(token=load_token(os.environ.get("FORGE_FABRO_STORAGE")), timeout=10) as c:
            return c.list_runs(limit=limit)
    except (FabroUnavailable, OSError):
        return None
    except Exception:  # noqa: BLE001 - any unexpected listing failure is "unreachable", never an empty listing
        return None


# pre-approved model profiles (policy engineering.allowed_model_profiles) -> launch parameters. Owner 2026-10-25: "I
# want it running with codex and claude as inspector, forget about deepseek now": the production line only - Codex
# authors and Claude inspectors through the forge ACP proxy (OD-2026-10-19-06/08). DeepSeek stays suspended
# (model-suspensions.yaml): "deepseek-flash" is only Fabro's nominal run model, every agent node runs on ACP and the
# cloud gateway refuses the suspended provider before any network call (CAPA-051/052). `model_gateway`: the model
# gateway the profile's agent nodes need (None: none - every agent node runs on ACP, so admission does not depend on
# the DeepSeek gateway; owner 2026-10-25 "a codex - claude based AFO, without deepseek"). Local profiles (Feature 014)
# launch through the work order's own `profile` instead of this map.
PROFILES = {"codex-claude": {"model": "deepseek-flash", "provider": "deepseek", "acp_authors": "codex",
                             "acp_inspectors": "claude", "model_gateway": None}}
CLOUD_GATEWAY = "http://127.0.0.1:11437"


def model_gateway(profile: str) -> str | None:
    """The gateway an order's model profile needs (the cloud gateway for a profile this module does not define)."""
    return PROFILES[profile].get("model_gateway", CLOUD_GATEWAY) if profile in PROFILES else CLOUD_GATEWAY


def launcher(manifest: dict, wo: str, labels: dict) -> dict:
    binding = manifest.get("durable_binding")
    if not binding:
        return _launcher(manifest, wo, labels)
    invoked = False

    def before_native():
        nonlocal invoked
        # From this point any launch/journal/transport error is uncertain.
        invoked = True

    try:
        return _launcher(manifest, wo, labels, before_native_launch=before_native)
    except Exception as exc:
        if not invoked:
            from .local_agent import LaunchNotStarted

            raise LaunchNotStarted(binding, exc) from exc
        raise


def _launcher(manifest: dict, wo: str, labels: dict, *, before_native_launch=None) -> dict:
    from ..workorder import factory_revision, run

    if manifest.get("model_profile"):  # a SWITCH_PREAPPROVED_MODEL_PROFILE recovery attempt
        if manifest.get("profile"):
            from ..lrtx.profile import load

            prof = load(manifest["profile"])
            selected = manifest["model_profile"]
            if selected not in prof["models"]["allowed"]:
                raise ValueError(f"LOCAL_MODEL_PROFILE_UNKNOWN:{selected}")
            manifest = {**manifest, "model": selected, "provider": prof["provider"], "acp_authors": None, "acp_inspectors": None}
            alternative = next(
                (a for a in manifest.get("qualified_local_alternatives") or [] if a.get("model_profile") == selected), None
            )
            if alternative:
                manifest = {**manifest, "role_capabilities": alternative["role_capabilities"]}
        elif manifest["model_profile"] not in PROFILES:
            raise ValueError(f"MODEL_PROFILE_UNKNOWN:{manifest['model_profile']}")
        else:
            manifest = {**manifest, **PROFILES[manifest["model_profile"]]}
    resume = manifest.get("resume_from")
    if "revalidate_author_tasks" in manifest and type(manifest["revalidate_author_tasks"]) is not bool:
        raise ValueError("AUTHOR_TASK_REVALIDATION_FLAG_INVALID")
    fresh = None
    approved = manifest.get("approved_factory_revision")
    if resume and approved and approved == factory_revision()["commit"]:
        from ..brownfield.resume import source_workspace
        from . import authz, dispatch
        from .local_agent import request_for
        from .policy import load
        from .queue import Store

        source = json.loads((source_workspace(resume) / ".forge-run/manifest.json").read_text())
        if (source.get("factory_revision") or {}).get("commit") != approved:
            # Only the immutable, owner-approved launch manifest may request a fresh cross-revision attempt.
            # A model cannot add these fields to its recovery plan. No old phase evidence is carried.
            store = Store()
            attempt = dispatch._attempt(store, labels["afo_attempt"])
            order = store.order(attempt["order_id"])
            eff = load()
            grant = authz.find(
                eff.mode,
                eff.sha256 or "",
                ref=eff.get("authorization_ref"),
                action="launch_workorder",
                request=request_for(order),
            )
            record = json.loads((authz.AUTH_DIR / f"{eff.get('authorization_ref')}.json").read_text())
            if not grant.allow or record.get("signed_runbook_ref") != f"factory-revision:{approved}":
                raise RuntimeError("FRESH_FACTORY_CHANGE_NOT_OWNER_AUTHORIZED")
            fresh, resume = resume, None
    r = run(
        REPO_ROOT / manifest["example"],
        wo,
        detach=True,
        model=manifest.get("model", "deepseek-flash"),
        provider=manifest.get("provider", "deepseek"),
        provided_from=manifest.get("provided_from"),
        acp_authors=manifest.get("acp_authors"),
        resume=resume,
        fresh_recovery_from=fresh,
        acp_inspectors=manifest.get("acp_inspectors"),
        profile=manifest.get("profile"),
        resume_upto=manifest.get("resume_upto") if resume else None,
        labels=labels,
        resume_max_attempts=manifest.get("resume_max_attempts"),
        resume_max_wall_seconds=manifest.get("resume_max_wall_seconds"),
        recovery_plan=manifest.get("recovery_plan"),
        durable_binding=manifest.get("durable_binding"),
        recovery_exhausted=manifest.get("recovery_exhausted"),
        **({"evaluation_holdout": True} if manifest.get("evaluation_holdout") else {}),
        **({"purpose": manifest["purpose"]} if "purpose" in manifest else {}),
        **({"revalidate_author_tasks": True} if manifest.get("revalidate_author_tasks") is True else {}),
        **({"before_native_launch": before_native_launch} if before_native_launch is not None else {}),
    )
    if not r.get("fabro_run_id"):
        raise RuntimeError(f"no Fabro run (preflight {r.get('preflight')})")
    rev = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    return {"fabro_run_id": r["fabro_run_id"], "factory_revision": rev or "unknown"}


def workspace_of(attempt: dict) -> Path:
    ref = attempt["record"].get("workspace_ref", "")
    return state_dir() / "workorders" / ref.removeprefix("workorder:") / "workspace"
