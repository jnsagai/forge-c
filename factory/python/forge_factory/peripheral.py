"""Feature 009 - peripheral profiles (`config/factory/peripherals/<id>.yaml`): the identity of the peripheral a work
order builds (RM register prefix, base address, RM sections, file names, API prefixes, register block, simulator
model). A work order names its profile (`peripheral`, default `rcc`); the RCC profile equals the factory's
historical constants, so RCC work orders are unchanged."""
from __future__ import annotations

import functools
import json
from pathlib import Path

from .common import REPO_ROOT, load_yaml, sha256_file

DIR = REPO_ROOT / "config/factory/peripherals"
CONTRACT = REPO_ROOT / "specs/009-peripheral-generic-iwdg/contracts/peripheral-profile.schema.json"
DEFAULT = "rcc"


class ProfileError(ValueError):
    pass


@functools.lru_cache(maxsize=16)
def load(pid: str = DEFAULT) -> dict:
    import jsonschema

    p = DIR / f"{pid}.yaml"
    if not p.is_file():
        raise ProfileError(f"PERIPHERAL_PROFILE_MISSING:{pid}")
    prof = load_yaml(p) or {}
    errs = [e.message[:120] for e in jsonschema.Draft202012Validator(json.loads(CONTRACT.read_text())).iter_errors(prof)]
    if errs or prof.get("id") != pid:
        raise ProfileError(f"PERIPHERAL_PROFILE_INVALID:{pid}:{errs[:3] or 'id mismatch'}")
    return {**prof, "sha256": sha256_file(p)}


def of_ws(ws) -> dict:
    """The profile of a workspace (its manifest's `peripheral`, else RCC)."""
    try:
        pid = json.loads((Path(ws) / ".forge-run/manifest.json").read_text()).get("peripheral") or DEFAULT
    except (OSError, ValueError):
        pid = DEFAULT
    return load(pid)
