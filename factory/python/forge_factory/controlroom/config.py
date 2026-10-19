"""Control Room configuration: config/factory/controlroom.yaml validated against the feature-007 contract.
An invalid file fails closed (ValueError) - the Control Room never runs on a half-read configuration."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from ..common import REPO_ROOT

CONFIG = REPO_ROOT / "config/factory/controlroom.yaml"
SCHEMA = REPO_ROOT / "specs/007-kpi-control-room/contracts/controlroom-config.schema.json"


def load(path: Path | None = None) -> dict:
    from jsonschema import Draft202012Validator

    p = path or CONFIG
    try:
        doc = yaml.safe_load(p.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"CONTROLROOM_CONFIG_UNREADABLE:{p}:{type(exc).__name__}") from exc
    errs = sorted(e.message for e in Draft202012Validator(json.loads(SCHEMA.read_text())).iter_errors(doc))
    if errs:
        raise ValueError(f"CONTROLROOM_CONFIG_INVALID:{p}:{errs[0]}")
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZoneInfo(doc["tz"])
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"CONTROLROOM_CONFIG_INVALID:{p}:unknown time zone {doc['tz']!r}") from exc
    return doc
