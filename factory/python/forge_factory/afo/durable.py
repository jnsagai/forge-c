"""Feature 014 primitives. Persistence belongs to the existing Conductor Store.

Canonical identities reject ambiguous JSON. These helpers do not grant authority,
interpret model prose, or supply an additional scheduler/database.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
from pathlib import Path

from ..common import REPO_ROOT

CONTRACTS = REPO_ROOT / "specs/014-durable-local-autonomy/contracts"


class Refused(ValueError):
    def __init__(self, code: str, detail: str = ""):
        self.code, self.detail = code, detail
        super().__init__(f"{code}:{detail}"[:500])


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def strict_json(raw: str | bytes, max_bytes: int = 16384):
    if len(raw.encode() if isinstance(raw, str) else raw) > max_bytes:
        raise Refused("PAYLOAD_TOO_LARGE")

    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise Refused("DUPLICATE_JSON_KEY", key)
            out[key] = value
        return out

    def nonfinite(value):
        raise Refused("NONFINITE_JSON", value)

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, Refused):
            raise
        raise Refused("INVALID_JSON", type(exc).__name__) from exc


@functools.cache
def schema(name: str) -> dict:
    if name not in ("semantic-proposal", "completion-receipt", "execution-lifecycle"):
        raise Refused("UNKNOWN_CONTRACT", name)
    return strict_json((CONTRACTS / f"{name}.schema.json").read_bytes(), 65536)


def validate(name: str, value) -> None:
    from jsonschema import Draft202012Validator, FormatChecker

    errors = list(Draft202012Validator(schema(name), format_checker=FormatChecker()).iter_errors(value))
    if errors:
        e = errors[0]
        raise Refused("CONTRACT_INVALID", f"{name}:{'/'.join(map(str, e.path))}:{e.validator}")


def immutable_json(path: Path, value) -> str:
    """Publish immutable canonical bytes; identical replay is allowed, changed replay is not."""
    raw = canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    import tempfile

    fd, temp = tempfile.mkstemp(prefix=".publish-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
            os.fchmod(f.fileno(), 0o400)
        try:
            os.link(temp, path)  # atomic publication, never a partial final artifact
        except FileExistsError:
            if path.read_bytes() != raw:
                raise Refused("IMMUTABLE_ARTIFACT_CHANGED", str(path)) from None
        parent = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        os.unlink(temp)
    return hashlib.sha256(raw).hexdigest()


# Versioned additive migration in queue.MIGRATIONS. All ledger/outbox writes use Store.tx (BEGIN IMMEDIATE).
MIGRATION = """
CREATE TABLE afo_missions (mission_id TEXT PRIMARY KEY, lineage TEXT UNIQUE NOT NULL, record TEXT NOT NULL);
CREATE TABLE afo_mission_orders (order_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES afo_missions(mission_id));
CREATE TABLE afo_mission_executions (identity TEXT PRIMARY KEY, mission_id TEXT NOT NULL REFERENCES afo_missions(mission_id), kind TEXT NOT NULL, record TEXT NOT NULL);
CREATE TABLE afo_request_ledger (request_id TEXT PRIMARY KEY, mission_id TEXT NOT NULL, job_id TEXT NOT NULL, state TEXT NOT NULL, record TEXT NOT NULL);
CREATE TABLE afo_resource_ownership (resource TEXT PRIMARY KEY, holder TEXT, epoch INTEGER NOT NULL, record TEXT NOT NULL);
CREATE TABLE afo_execution_liveness (execution_id TEXT PRIMARY KEY, job_id TEXT UNIQUE NOT NULL, mission_id TEXT NOT NULL, record TEXT NOT NULL);
CREATE TABLE afo_semantic_proposals (proposal_sha256 TEXT NOT NULL, job_id TEXT NOT NULL, nonce TEXT NOT NULL, record TEXT NOT NULL, PRIMARY KEY(job_id, nonce, proposal_sha256));
CREATE TABLE afo_completion_receipts (receipt_id TEXT NOT NULL, revision INTEGER NOT NULL, record TEXT NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(receipt_id,revision));
CREATE TRIGGER afo_receipts_no_update BEFORE UPDATE ON afo_completion_receipts BEGIN SELECT RAISE(ABORT, 'APPEND_ONLY'); END;
CREATE TRIGGER afo_receipts_no_delete BEFORE DELETE ON afo_completion_receipts BEGIN SELECT RAISE(ABORT, 'APPEND_ONLY'); END;
CREATE TABLE afo_durable_effects (effect_id TEXT PRIMARY KEY, kind TEXT NOT NULL, job_id TEXT NOT NULL, epoch INTEGER NOT NULL, state TEXT NOT NULL, record TEXT NOT NULL);
CREATE TABLE afo_independent_decisions (decision_id TEXT PRIMARY KEY, kind TEXT NOT NULL, record TEXT NOT NULL, sha256 TEXT NOT NULL);
CREATE TABLE afo_verification_jobs (job_id TEXT PRIMARY KEY, state TEXT NOT NULL, epoch INTEGER NOT NULL, lease_until REAL NOT NULL, record TEXT NOT NULL);
CREATE TABLE afo_dependency_waits (wait_id TEXT PRIMARY KEY, scope TEXT NOT NULL, next_probe REAL NOT NULL, record TEXT NOT NULL);
CREATE TABLE afo_recovery_incidents (incident_id TEXT PRIMARY KEY, order_id TEXT NOT NULL, code TEXT NOT NULL, record TEXT NOT NULL);
"""
