"""Feature 020 (research R2): the SWE.1 level of a work order - the single source every level-aware change reads.

A work order selects functional-level SWE.1 with `swe1: {level: functional, template: swe1-functional-v1}` plus its
`module` and scope rule (contracts/workorder-swe1-block.schema.json). The contract calls the scope rule `scope`; in a
work order that key already holds the declared scope text every agent reads, so the work order carries the rule as
`scope_rule` (decision log D14). Only a functional order gets manifest keys (`swe1_level`, `swe1_template`, and
`swe1_use_cases_owner` when the owner gave use cases); every other manifest stays byte-identical. A functional order
has no register contract and no defined SWE.2+ yet: those runs are refused (SWE1_FUNCTIONAL_LATER_PHASES_NOT_YET)."""
from __future__ import annotations

import json
from pathlib import Path

from ..common import CONFIG_DIR, REPO_ROOT, load_yaml

FUNCTIONAL = "functional"
REGISTER = "register"
LATER_PHASES_REFUSED = "SWE1_FUNCTIONAL_LATER_PHASES_NOT_YET"
SCHEMA = REPO_ROOT / "config/schemas/workorder/swe1-block.schema.json"
TEMPLATE = CONFIG_DIR / "swe1-functional-template.yaml"
SPEC_KEYS = ("swe1", "module", "scope_rule", "use_cases_owner")


class LevelRefused(ValueError):
    """The work order's SWE.1 level block is invalid, or the requested run is not defined for its level."""


def swe1_level(manifest: dict | None) -> str:
    """`functional` for a functional-level order, else `register` (every order prepared without the block)."""
    return FUNCTIONAL if (manifest or {}).get("swe1_level") == FUNCTIONAL else REGISTER


def of_workspace(ws: Path) -> str:
    try:
        return swe1_level(json.loads((Path(ws) / ".forge-run/manifest.json").read_text()))
    except (OSError, ValueError):
        return REGISTER


def load_template(template_id: str | None = None) -> dict:
    """The template config with this id among config/factory/swe1-functional-template*.yaml (feature 020 round 2:
    a new template version is a new file, older ones stay unchanged); None: the v1 file."""
    if template_id is None:
        return load_yaml(TEMPLATE)
    for p in sorted(TEMPLATE.parent.glob("swe1-functional-template*.yaml")):
        t = load_yaml(p)
        if t.get("template_id") == template_id:
            return t
    raise LevelRefused(f"SWE1_TEMPLATE_UNKNOWN:{template_id}")


def template(manifest: dict | None) -> dict | None:
    """The functional template config the order names (None for a register-level order)."""
    if swe1_level(manifest) != FUNCTIONAL:
        return None
    return load_template(manifest["swe1_template"])


def block(spec: dict) -> dict | None:
    """The work order's level block in the contract's shape (None when the order has none of its keys)."""
    if not any(k in spec for k in SPEC_KEYS):
        return None
    out = {k: spec[k] for k in ("swe1", "module") if k in spec}
    if "scope_rule" in spec:
        out["scope"] = spec["scope_rule"]
    if "use_cases_owner" in spec:
        out["use_cases_owner"] = spec["use_cases_owner"]
    return out


def validate(spec: dict) -> dict | None:
    """The validated block, or None; refuses an invalid block or an unknown template (before any workspace)."""
    import jsonschema

    b = block(spec)
    if b is None:
        return None
    schema = json.loads(SCHEMA.read_text())
    errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(b), key=lambda e: list(map(str, e.absolute_path)))
    if errs:
        raise LevelRefused(";".join(f"SWE1_BLOCK_INVALID:{'/'.join(map(str, e.absolute_path)) or '-'}:{e.message[:120]}"
                                    for e in errs[:6]))
    if b["swe1"]["level"] == FUNCTIONAL:
        load_template(b["swe1"]["template"])
    return b


def is_functional(spec: dict) -> bool:
    return ((spec.get("swe1") or {}).get("level")) == FUNCTIONAL


def manifest_keys(spec: dict) -> dict:
    """The manifest keys of the level setting: only for a functional order (absent otherwise)."""
    b = validate(spec)
    if b is None or b["swe1"]["level"] != FUNCTIONAL:
        return {}
    return {"swe1_level": FUNCTIONAL, "swe1_template": b["swe1"]["template"],
            **({"swe1_use_cases_owner": b["use_cases_owner"]} if b.get("use_cases_owner") else {}),
            # D36 owner rule: the predecessor runs whose validated SWE.1 artifacts this order keeps (lrtx/swe1_carry.py)
            **({"swe1_carry_from": list(b["swe1"]["carry_from"])} if b["swe1"].get("carry_from") else {})}


def check_phase_scope(spec: dict, stop_after: str | None) -> None:
    """A functional order runs SWE.1 only until the later phases are defined (research R2)."""
    if is_functional(spec) and stop_after != "SWE.1":
        raise LevelRefused(f"{LATER_PHASES_REFUSED}: a functional-level SWE.1 order runs with --stop-after SWE.1 "
                           f"(requested: {stop_after or 'all phases'})")
