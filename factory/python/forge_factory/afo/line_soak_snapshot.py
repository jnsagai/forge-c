"""Ephemeral controller replay snapshot, never a persisted readiness/authority receipt.

Only the normal public start/fault path produces this object after validation.
Its JSON projection cannot authorize a boundary. Small bounded file hashes and
fresh ledger/UTC/intent checks fence the final effect, without holding STOP's
intent lock across role, lesson, native, or engineering-proof verification.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path

from .durable import Refused, digest

CURRENT = ContextVar("line_soak_replay", default=None)
MAX_FILES = 512
MAX_TOTAL_BYTES = 32 * 1024 * 1024


class Replay(dict):
    def __init__(self, manifest, plan):
        super().__init__()
        self.scope = (digest(manifest), digest(plan))
        self.files = {}
        self.absent = set()
        self.bytes = 0
        self.grants = []
        self.epoch = None
        self.policy = None

    def observe(self, ref, raw):
        path = ref["path"]
        if path in self.files:
            if self.files[path] != ref["sha256"]:
                raise Refused("LINE_SOAK_REPLAY_INPUT_CHANGED")
            return
        self.bytes += len(raw)
        if len(self.files) >= MAX_FILES or self.bytes > MAX_TOTAL_BYTES:
            raise Refused("LINE_SOAK_REPLAY_BOUND_EXCEEDED")
        self.files[path] = ref["sha256"]

    def file(self, path, *, optional=False):
        from .fault_observer import read_bytes
        from .line_soak_prerequisites import reference

        path = Path(path).absolute()
        if optional and not path.exists() and not path.is_symlink():
            self.absent.add(str(path))
            return None
        # reference repeats the hash check with no-follow bounded regular reads.
        raw = read_bytes(path, 1024 * 1024)
        ref = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest()}
        reference(ref, decode=False)
        self.observe(ref, raw)
        return raw

    def authority(self, aid, *, base=None, signers=None):
        """Capture bytes of authority already verified by normal Q/C/T/line APIs."""
        from . import authz, contracts

        if not isinstance(aid, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{1,127}", aid):
            raise Refused("LINE_SOAK_AUTHORITY_REFERENCE_INVALID")
        base = Path(base or authz.AUTH_DIR)
        record = json.loads(self.file(base / (aid + ".json")))
        if contracts.errors("authorization", record) or record["authorization_id"] != aid:
            raise Refused("LINE_SOAK_AUTHORITY_SCHEMA_INVALID")
        sig = Path(record["signature_ref"])
        if (sig.is_absolute() or ".." in sig.parts or sig.suffix != ".sig"
                or not (base / sig).resolve().is_relative_to(base.resolve())):
            raise Refused("LINE_SOAK_SIGNATURE_REFERENCE_INVALID")
        self.file(base / sig)
        self.file(signers or authz.ALLOWED_SIGNERS)
        self.file(base / "revoked.txt", optional=True)
        self.grants.append(record)

    def follow(self, value, depth=0):
        """Hash-bound evidence closure, including nested independent raw/proof inputs."""
        from .durable import strict_json
        from .line_soak_prerequisites import reference

        if depth > 16:
            raise Refused("LINE_SOAK_REPLAY_DEPTH_EXCEEDED")
        if isinstance(value, dict):
            if {"path", "sha256"} <= set(value) and isinstance(value["path"], str) and Path(value["path"]).is_absolute():
                ref = {k: value[k] for k in ("path", "sha256")}
                seen = ref["path"] in self.files
                raw = reference(ref, decode=False)
                if not seen:
                    try:
                        self.follow(strict_json(raw, 1024 * 1024), depth + 1)
                    except Refused as exc:
                        # Non-JSON raw logs/oracles remain byte-bound. Structural
                        # JSON validation belongs to their existing validator.
                        if exc.code != "INVALID_JSON":
                            raise
                return
            for child in value.values():
                self.follow(child, depth + 1)
        elif isinstance(value, list):
            for child in value:
                self.follow(child, depth + 1)

    def fence(self, manifest, plan):
        from .line_soak_prerequisites import reference

        if self.scope != (digest(manifest), digest(plan)) or not self.files:
            raise Refused("LINE_SOAK_REPLAY_SNAPSHOT_SCOPE_CHANGED")
        for path, sha in self.files.items():
            reference({"path": path, "sha256": sha}, decode=False)
        if any(Path(path).exists() or Path(path).is_symlink() for path in self.absent):
            raise Refused("LINE_SOAK_AUTHORITY_REVOCATION_INPUT_CHANGED")
        self.time_fence()

    def time_fence(self, deadlines=()):
        """One final UTC observation after parsing every bound, immediately before effect."""
        issued = [datetime.fromisoformat(g["issued_utc"].replace("Z", "+00:00")).timestamp() for g in self.grants]
        expires = [datetime.fromisoformat(g["expires_utc"].replace("Z", "+00:00")).timestamp() for g in self.grants]
        if not issued or any(g.get("revoked_utc") for g in self.grants):
            raise Refused("LINE_SOAK_AUTHORITY_NOT_CURRENT")
        earliest_grant, latest_issue = min(expires), max(issued)
        earliest_job = min(deadlines, default=float("inf"))
        now = time.time()
        if not latest_issue <= now < earliest_grant:
            raise Refused("LINE_SOAK_AUTHORITY_NOT_CURRENT")
        if now >= earliest_job:
            raise Refused("LINE_SOAK_START_AUTHORITY_EXPIRED")


def authority(aid, **kwargs):
    if (snapshot := CURRENT.get()) is not None:
        snapshot.authority(aid, **kwargs)
