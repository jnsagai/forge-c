"""Runtime validation of the process lab contracts (design rev 4 §1, §4, §8, §9).

Same pattern as forge_factory.afo.contracts: Draft 2020-12 with format checking, a fixed allow-list of names, shape
only. Hashes, signatures and scope bindings are verified by the deterministic code that owns them.
"""
from __future__ import annotations

import functools
import json

from ..common import REPO_ROOT

CONTRACTS = REPO_ROOT / "specs/014-durable-local-autonomy/contracts/runtime"
NAMES = ("process-lab", "process-handoff", "swe1-oracle", "process-lab-experiment", "model-swap",
         "process-lab-disposition")


class ContractError(ValueError):
    pass


def _is_datetime(value: object) -> bool:
    """RFC 3339 date-time, as the spec validator checks it (validate_contracts.py). jsonschema's default checker only
    enforces date-time when an optional dependency is installed, so the rule is registered explicitly here."""
    import datetime as dt
    import re

    if not isinstance(value, str):
        return True  # type validation owns non-string values
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})", value):
        return False
    normalized = re.sub(r":60(?=[.Zz+-])", ":59", value).upper().replace("Z", "+00:00")
    try:
        return dt.datetime.fromisoformat(normalized).tzinfo is not None
    except ValueError:
        return False


@functools.cache
def _validator(name: str):
    import jsonschema

    if name not in NAMES:
        raise ContractError(f"UNKNOWN_PROCESS_LAB_CONTRACT:{name}")
    checker = jsonschema.FormatChecker()
    checker.checks("date-time")(_is_datetime)
    return jsonschema.Draft202012Validator(json.loads((CONTRACTS / f"{name}.schema.json").read_text()),
                                           format_checker=checker)


def errors(name: str, obj) -> list[str]:
    return [f"{name}:{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"[:200]
            for e in _validator(name).iter_errors(obj)]


def require(name: str, obj):
    """Return `obj` unchanged when it satisfies contract `name`; otherwise raise with the first violation."""
    found = errors(name, obj)
    if found:
        raise ContractError(f"PROCESS_LAB_CONTRACT_INVALID:{found[0]}")
    return obj
