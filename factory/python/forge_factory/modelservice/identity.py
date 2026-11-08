"""Served-model identity (feature 017, FR-003, FR-011, research R4).

An identity names exactly which model answers: name, revision fingerprint, precision, reasoning mode, context
limit and engine. The recipe pins one identity per catalog model in `recipe.lock.json`; the model tier verifies it
after every load, and the factory pins it per model name for a run.

The revision fingerprint is the sha256 of the canonical JSON of the sorted (relative path, sha256) list of the
weight files plus the tokenizer and chat-template digests, so it does not depend on file order and changes when
any byte of the weights, the tokenizer or the template changes.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ..common import sha256_file

SCHEMA = Path(__file__).resolve().parents[4] / "config/schemas/model-service/served-model-identity.schema.json"
FIELDS = ("name", "revision_fingerprint", "precision", "reasoning_mode", "context_limit")


class IdentityError(RuntimeError):
    """A machine reason in the message: NOT_IN_LOCK:<model>, IDENTITY_MISMATCH:<fields>, MODEL_NOT_OFFERED:<model>."""


def sha(path: Path) -> str:
    return sha256_file(Path(path))


def file_entries(weights: Path) -> list[tuple[str, str]]:
    """(relative path, sha256) of every regular file of a model directory, or of a single model file."""
    weights = Path(weights)
    if weights.is_file():
        return [(weights.name, sha(weights))]
    return [(p.relative_to(weights).as_posix(), sha(p)) for p in sorted(weights.rglob("*")) if p.is_file()]


def fingerprint_entries(entries: Iterable[tuple[str, str]], tokenizer_sha: str | None, chat_template_sha: str | None) -> str:
    doc = {"files": sorted([list(e) for e in entries]), "tokenizer": tokenizer_sha, "chat_template": chat_template_sha}
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def fingerprint(weights: Path, tokenizer: Path | None = None, chat_template: Path | None = None) -> str:
    return fingerprint_entries(file_entries(weights), tokenizer and sha(tokenizer), chat_template and sha(chat_template))


def build(*, name: str, revision_fingerprint: str, precision: str, reasoning_mode: str, context_limit: int,
          engine: dict, attested: bool, kv_cache_dtype: str | None = None, max_sequences: int | None = None) -> dict:
    out: dict[str, Any] = {"name": name, "revision_fingerprint": revision_fingerprint, "precision": precision,
                           "reasoning_mode": reasoning_mode, "context_limit": int(context_limit), "engine": dict(engine),
                           "attested": bool(attested)}
    if kv_cache_dtype is not None:
        out["kv_cache_dtype"] = kv_cache_dtype
    if max_sequences is not None:
        out["max_sequences"] = int(max_sequences)
    return out


def validate(doc: dict) -> dict:
    from jsonschema import Draft202012Validator

    errors = sorted(Draft202012Validator(json.loads(SCHEMA.read_text())).iter_errors(doc), key=lambda e: list(e.path))
    if errors:
        raise ValueError("IDENTITY_INVALID:" + "; ".join(f"{'/'.join(map(str, e.path))}: {e.message}" for e in errors))
    return doc


def verify(expected: dict, observed: dict) -> list[str]:
    """Names of the identity fields that differ (empty = same model). `attested` and engine details are not compared:
    the same weights served by a restarted engine are the same model."""
    return [f for f in FIELDS if expected.get(f) != observed.get(f)]


def require_match(expected: dict, observed: dict) -> None:
    diff = verify(expected, observed)
    if diff:
        raise IdentityError("IDENTITY_MISMATCH:" + ",".join(diff))


def from_lock(lock: dict, model: str) -> dict:
    ident = (lock.get("identities") or {}).get(model)
    if not isinstance(ident, dict):
        raise IdentityError(f"NOT_IN_LOCK:{model}")
    return ident


def short(ident: dict) -> str:
    """The 16-hex prefix carried in the x-forge-model-identity header."""
    return str(ident.get("revision_fingerprint", ""))[:16]


def inferred_from_models_endpoint(payload: dict, model: str, declared: dict) -> dict:
    """Identity of `model` on a service without the Forge-C identity extension: name and context limit from
    /v1/models, everything else from the declared (recipe or profile) values. Always `attested: false`, which the
    qualification report states as a deviation."""
    entry = next((m for m in payload.get("data") or [] if m.get("id") == model), None)
    if entry is None:
        raise IdentityError(f"MODEL_NOT_OFFERED:{model}")
    fp = declared.get("revision_fingerprint")
    if not fp:  # nothing pinned: a stable, clearly unattested placeholder derived from what the service reports
        fp = hashlib.sha256(("unattested|" + json.dumps(entry, sort_keys=True)).encode()).hexdigest()
    return build(name=model, revision_fingerprint=fp, precision=declared.get("precision", "other"),
                 reasoning_mode=declared.get("reasoning_mode", "off"),
                 context_limit=int(entry.get("max_model_len") or declared.get("min_context_limit") or 1),
                 engine=declared.get("engine") or {"name": "unknown", "version": "unknown"}, attested=False)
