"""Project configuration, standard profiles and effective rigor."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .io import read_json
from .jsonschema_lite import validate

REFS = Path(__file__).resolve().parents[2] / "references"
DEFAULT_PROFILE = "generic"


class ConfigError(ValueError):
    """Invalid or unsupported project/profile configuration (CLI exit code 2)."""


@lru_cache(maxsize=None)
def schema(name: str) -> dict:
    return json.loads((REFS / "schemas" / f"{name}.schema.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def stages() -> dict:
    doc = read_json(REFS / "stages.json")
    return {s["id"]: s for s in doc["stages"]}


def stage_order() -> list[str]:
    return read_json(REFS / "stages.json")["order"]


def find_root(start: Path | None = None) -> Path:
    """Nearest ancestor holding .hi/project.json; falls back to the start directory."""
    here = Path(start or Path.cwd()).resolve()
    for cand in (here, *here.parents):
        if (cand / ".hi" / "project.json").is_file():
            return cand
    return here


def load_profile(profile_id: str, profiles_dir: Path | None = None) -> dict:
    base = Path(profiles_dir) if profiles_dir else REFS / "profiles"
    path = base / f"{profile_id}.json"
    if not path.is_file() or profile_id.startswith("_"):
        raise ConfigError(f"unknown standard profile '{profile_id}' (looked in {base})")
    doc = read_json(path)
    errors = validate(doc, schema("profile"))
    if errors:
        raise ConfigError(f"profile '{profile_id}' invalid: {errors[:3]}")
    return doc


def load_project(root: Path) -> dict:
    path = Path(root) / ".hi" / "project.json"
    if not path.is_file():
        raise ConfigError(f"no project configuration at {path}; run 'hi init'")
    doc = read_json(path)
    errors = validate(doc, schema("project"))
    if errors:
        raise ConfigError(f"{path} invalid: {errors[:3]}")
    doc.setdefault("profile", DEFAULT_PROFILE)
    return doc


def effective_rigor(project: dict, profiles_dir: Path | None = None) -> dict:
    """Rigor in force for the project's profile and level; refuses unmapped levels (FR-009)."""
    profile = load_profile(project.get("profile", DEFAULT_PROFILE), profiles_dir)
    level = project["integrity_level"]
    if level not in profile["level_map"] or level not in profile["rigor"]:
        raise ConfigError(
            f"integrity level {level} is not defined by profile '{profile['id']}' "
            f"(defined: {sorted(profile['level_map'])})"
        )
    rigor: dict[str, Any] = dict(profile["rigor"][level])
    for key in ("rework_limit", "rework_max"):
        if key in project:
            rigor[key] = project[key]
    rigor["profile"] = profile["id"]
    rigor["level"] = level
    rigor["level_name"] = profile["level_map"][level]
    return rigor


def native_level_name(profile: dict, level: str) -> str:
    return profile["level_map"][level]
