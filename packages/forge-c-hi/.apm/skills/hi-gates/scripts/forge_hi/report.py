"""Profile vocabulary for reports (FR-007): the user's standard names the stages and levels, the engine stays neutral."""
from __future__ import annotations


def level_label(profile: dict, level: str) -> str:
    native = profile.get("level_map", {}).get(level)
    return level if not native or native == level else f"{level} ({native})"


def stage_label(profile: dict, stage: str) -> str:
    native = profile.get("vocabulary", {}).get(stage)
    return f"{stage}: {native}" if native else stage


def clause_refs(profile: dict, stage: str) -> str:
    refs = profile.get("clause_refs", {}).get(stage) or []
    return ", ".join(refs)


def header(profile: dict, level: str) -> list[str]:
    return [f"Standard profile: **{profile.get('title', profile.get('id'))}** (`{profile.get('id')}`), integrity level "
            f"**{level_label(profile, level)}**.", ""]
