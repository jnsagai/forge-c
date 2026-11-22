"""Provenance records attached to every workproduct (FR-012)."""
from __future__ import annotations

import datetime as _dt
import secrets
from pathlib import Path

from .io import sha256_file


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_run_id() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("r%Y%m%dT%H%M%SZ-") + secrets.token_hex(3)


def provenance(
    *,
    role: str,
    skill: str,
    skill_version: str,
    harness: str,
    run_id: str,
    inputs: list[Path] | None = None,
    root: Path | None = None,
    model: str | None = None,
    model_family: str | None = None,
) -> dict:
    root = Path(root or Path.cwd())
    hashes = {}
    for p in inputs or []:
        p = Path(p)
        full = p if p.is_absolute() else root / p
        key = str(full.relative_to(root)) if full.is_relative_to(root) else str(full)
        hashes[key] = sha256_file(full)
    return {
        "role": role,
        "skill": skill,
        "skill_version": skill_version,
        "harness": harness,
        "model": model,
        "model_family": model_family,
        "input_hashes": hashes,
        "created_utc": utc_now(),
        "run_id": run_id,
    }
