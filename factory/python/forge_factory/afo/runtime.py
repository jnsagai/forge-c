"""AFO M3 production wiring: the real Fabro listing, launcher and workspace mapping used by the Conductor cycle.

The launcher calls `workorder.run(..., detach=True, labels=...)` - the same path an operator uses - with the
pinned launch manifest (example, provided LL, model, provider, Codex authors, optional resume source). The view lists
recent runs of the Fabro server the factory launches on (FORGE_FABRO_URL); unreachable -> None (never "no runs").
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from ..common import REPO_ROOT, state_dir


def fabro_view(limit: int = 200):
    from ..fabro.client import FabroClient, FabroUnavailable, load_token

    try:
        c = FabroClient(token=load_token(os.environ.get("FORGE_FABRO_STORAGE")), timeout=10)
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
# the DeepSeek gateway; owner 2026-10-25 "a codex - claude based AFO, without deepseek").
PROFILES = {"codex-claude": {"model": "deepseek-flash", "provider": "deepseek", "acp_authors": "codex",
                             "acp_inspectors": "claude", "model_gateway": None}}
CLOUD_GATEWAY = "http://127.0.0.1:11437"


def model_gateway(profile: str) -> str | None:
    """The gateway an order's model profile needs (the cloud gateway for a profile this module does not define)."""
    return PROFILES[profile].get("model_gateway", CLOUD_GATEWAY) if profile in PROFILES else CLOUD_GATEWAY


def _brownfield(example: Path) -> bool:
    import json

    return bool((json.loads((example / "workorder.json").read_text()).get("delivery") or {}).get("code_mode"))


def launcher(manifest: dict, wo: str, labels: dict) -> dict:
    from ..workorder import run

    if manifest.get("model_profile"):  # a SWITCH_PREAPPROVED_MODEL_PROFILE recovery attempt
        if manifest["model_profile"] not in PROFILES:
            raise ValueError(f"MODEL_PROFILE_UNKNOWN:{manifest['model_profile']}")
        manifest = {**manifest, **PROFILES[manifest["model_profile"]]}
    example = REPO_ROOT / manifest["example"]
    resume = manifest.get("resume_from")
    if resume and _brownfield(example):  # main refuses --resume-from for delivered code (BROWNFIELD_RESUME_NOT_SUPPORTED):
        # the recovery attempt is a fresh work order that still carries its material difference (lessons, defects)
        resume, labels = None, {**labels, "afo_brownfield_fresh_attempt": "1"}
    r = run(example, wo, detach=True, model=manifest.get("model", "deepseek-flash"),
            provider=manifest.get("provider", "deepseek"), provided_from=manifest.get("provided_from"),
            acp_authors=manifest.get("acp_authors"), acp_inspectors=manifest.get("acp_inspectors"), resume=resume,
            resume_upto=manifest.get("resume_upto") if resume else None, labels=labels)
    if not r.get("fabro_run_id"):
        raise RuntimeError(f"no Fabro run (preflight {r.get('preflight')})")
    rev = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    return {"fabro_run_id": r["fabro_run_id"], "factory_revision": rev or "unknown"}


def workspace_of(attempt: dict) -> Path:
    ref = attempt["record"].get("workspace_ref", "")
    return state_dir() / "workorders" / ref.removeprefix("workorder:") / "workspace"
