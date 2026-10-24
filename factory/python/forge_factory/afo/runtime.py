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


# pre-approved model profiles (policy engineering.allowed_model_profiles) -> launch parameters
PROFILES = {"deepseek-flash": {"model": "deepseek-flash", "provider": "deepseek", "acp_authors": None},
            "codex-gpt-6.1-sol": {"model": "deepseek-flash", "provider": "deepseek", "acp_authors": "codex"}}


def launcher(manifest: dict, wo: str, labels: dict) -> dict:
    from ..workorder import run

    if manifest.get("model_profile"):  # a SWITCH_PREAPPROVED_MODEL_PROFILE recovery attempt
        if manifest.get("profile"):
            from ..lrtx.profile import load

            prof = load(manifest["profile"])
            selected = manifest["model_profile"]
            if selected not in prof["models"]["allowed"]:
                raise ValueError(f"LOCAL_MODEL_PROFILE_UNKNOWN:{selected}")
            manifest = {**manifest, "model": selected, "provider": prof["provider"],
                        "acp_authors": None, "acp_inspectors": None}
        elif manifest["model_profile"] not in PROFILES:
            raise ValueError(f"MODEL_PROFILE_UNKNOWN:{manifest['model_profile']}")
        else:
            manifest = {**manifest, **PROFILES[manifest["model_profile"]]}
    r = run(REPO_ROOT / manifest["example"], wo, detach=True, model=manifest.get("model", "deepseek-flash"),
            provider=manifest.get("provider", "deepseek"), provided_from=manifest.get("provided_from"),
            acp_authors=manifest.get("acp_authors"), resume=manifest.get("resume_from"),
            acp_inspectors=manifest.get("acp_inspectors"), profile=manifest.get("profile"),
            resume_upto=manifest.get("resume_upto"), labels=labels,
            resume_max_attempts=manifest.get("resume_max_attempts"),
            resume_max_wall_seconds=manifest.get("resume_max_wall_seconds"), recovery_plan=manifest.get("recovery_plan"))
    if not r.get("fabro_run_id"):
        raise RuntimeError(f"no Fabro run (preflight {r.get('preflight')})")
    rev = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    return {"fabro_run_id": r["fabro_run_id"], "factory_revision": rev or "unknown"}


def workspace_of(attempt: dict) -> Path:
    ref = attempt["record"].get("workspace_ref", "")
    return state_dir() / "workorders" / ref.removeprefix("workorder:") / "workspace"
