"""AFO-T005 (AFO-FR-007) - runtime validation against the Feature 005 contracts.

The spec validator (`specs/005-.../validate_spec.py`) lints the schemas and examples at design time; this module is
what the implementation calls on every record it writes or accepts (work orders, attempts, outbox commands,
queue events, failure bundles, recovery plans, dead letters, readiness), with format checking. JSON Schema checks
shape only: signatures, hashes, epochs and gates are verified by the deterministic code that owns them.
"""
from __future__ import annotations

import functools
import json

from ..common import REPO_ROOT, load_yaml

CONTRACTS = REPO_ROOT / "specs/005-autonomous-factory-operations/contracts"
NAMES = ("afo-policy", "work-order", "attempt", "outbox-command", "queue-event", "failure-bundle", "recovery-plan",
         "maintenance-proposal", "dead-letter", "authorization", "operational-readiness")


class ContractError(ValueError):
    pass


@functools.cache
def _validator(name: str):
    import jsonschema

    if name not in NAMES:
        raise ContractError(f"UNKNOWN_CONTRACT:{name}")
    return jsonschema.Draft202012Validator(json.loads((CONTRACTS / f"{name}.schema.json").read_text()),
                                           format_checker=jsonschema.FormatChecker())


def errors(name: str, obj) -> list[str]:
    out = []
    for e in _validator(name).iter_errors(obj):
        # Put the violated limit before any untrusted value: MCP issues are capped at 120 characters.
        detail = (f"{e.validator}={e.validator_value}; actual_length={len(e.instance)}"
                  if e.validator in ("maxLength", "minLength") else e.message)
        out.append(f"{name}:{'/'.join(map(str, e.path)) or '<root>'}: {detail}"[:200])
    return out


def require(name: str, obj) -> None:
    errs = errors(name, obj)
    if errs:
        raise ContractError("; ".join(errs[:3]))


@functools.cache
def fsm() -> dict:
    return load_yaml(CONTRACTS / "queue-fsm.yaml")


@functools.cache
def taxonomy() -> dict:
    return load_yaml(CONTRACTS / "failure-taxonomy.yaml")
