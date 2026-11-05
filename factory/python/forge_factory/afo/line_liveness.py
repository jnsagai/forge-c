"""M2 side-effect fence for the existing line-local durable execution/request ledger.

Read-only admission checks never migrate a store. An empty Fabro listing cannot
overrule a held inference lease or an unresolved provider request. One fresh
trusted launch may exclude only its own nonce after a transactional local claim.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import closing

from .durable import Refused, canonical, digest

KIND = "LINE_LOCAL_LAUNCH_CLAIM"


class ClaimUncertain(RuntimeError):
    """A previous launch claim may have produced a native effect; never not-started proof."""


def path(cfg):
    return cfg.stack_root / "state/supervisor/line-queue.sqlite3"


def _owner():
    from .line_orders import _proc_start

    start = _proc_start(os.getpid())
    if start is None:
        raise Refused("LINE_LAUNCH_OWNER_IDENTITY_UNAVAILABLE")
    return {"pid": os.getpid(), "start": start}


def claim(cfg, job):
    database = path(cfg)
    if not database.exists():
        if job.get("line_origin") or job.get("line_role_authority_ref"):
            raise Refused("LINE_EXECUTION_STORE_MISSING")
        return None  # unchanged legacy host fixture/runtime without a durable line execution
    from .execution_lifecycle import Executions
    from .queue import Store

    store = Store(database)
    execution = Executions(store).get(job["job_id"])
    if not execution:
        if job.get("line_origin") or job.get("line_role_authority_ref"):
            raise Refused("LINE_EXECUTION_NOT_REGISTERED")
        return None
    if (
        execution["launch_nonce"] != job["nonce"]
        or execution["resource_lease"] != "HELD"
        or execution["authorization_state"] != "VALID"
        or execution["task_outcome"] != "ACTIVE"
        or execution["admission_state"] != "DISPATCH_INTENT_RECORDED"
        or execution["native_run_ids"]
    ):
        raise ClaimUncertain("LINE_EXECUTION_ALREADY_OR_POSSIBLY_DISPATCHED")
    value = {"job_id": job["job_id"], "nonce": job["nonce"], "lease_epoch": execution["lease_epoch"], **_owner()}
    with store.tx() as c:
        created = c.execute(
            "INSERT OR IGNORE INTO afo_execution_evidence VALUES (?,?,?,?)",
            (job["job_id"], KIND, canonical(value).decode(), digest(value)),
        ).rowcount
        if not created:
            raise ClaimUncertain("LINE_LOCAL_LAUNCH_ALREADY_CLAIMED")
    return value


def clear(cfg, *, exclusion=None):
    """Refuse unknown/busy; caller translates to the existing M2 typed refusal."""
    database = path(cfg)
    if not database.exists():
        return
    if database.is_symlink() or not database.is_file():
        raise Refused("LINE_DURABLE_LIVENESS_UNAVAILABLE")
    deadline = time.monotonic() + 1
    try:
        with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=1)) as c:
            c.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            c.execute("PRAGMA query_only=ON")
            c.execute("BEGIN")
            if c.execute("SELECT 1 FROM afo_request_ledger WHERE state NOT IN ('QUIESCENT','RESERVED') LIMIT 1").fetchone():
                raise Refused("LINE_PROVIDER_REQUEST_NOT_QUIESCENT")
            rows = c.execute(
                "SELECT record FROM afo_execution_liveness WHERE json_extract(record,'$.resource_lease')='HELD' LIMIT 10001"
            ).fetchall()
            if len(rows) > 10000:
                raise Refused("LINE_DURABLE_LIVENESS_OBSERVATION_BOUND")
            ownership = c.execute("SELECT holder,epoch FROM afo_resource_ownership WHERE resource='inference'").fetchone()
            held = [json.loads(raw[0]) for raw in rows]
            owner = ownership[0] if ownership else None
            if (owner and not any(r["job_id"] == owner for r in held)) or (held and not owner):
                raise Refused("LINE_DURABLE_OWNERSHIP_UNCONFIRMED")
            for record in held:
                own = exclusion and record["job_id"] == exclusion["job_id"]
                if own:
                    proof = c.execute(
                        "SELECT record,sha256 FROM afo_execution_evidence WHERE job_id=? AND kind=?", (record["job_id"], KIND)
                    ).fetchone()
                    value = json.loads(proof[0]) if proof else None
                    own = (
                        value == exclusion
                        and digest(value) == proof[1]
                        and all(value.get(k) == v for k, v in _owner().items())
                        and record["launch_nonce"] == value["nonce"]
                        and record["lease_epoch"] == value["lease_epoch"]
                        and not record["native_run_ids"]
                        and ownership[0] == record["job_id"]
                        and ownership[1] == value["lease_epoch"]
                        and record["authorization_state"] == "VALID"
                        and record["task_outcome"] == "ACTIVE"
                        and record["admission_state"] == "DISPATCH_INTENT_RECORDED"
                    )
                    if (
                        own
                        and c.execute(
                            "SELECT 1 FROM afo_request_ledger WHERE job_id=? AND state!='QUIESCENT' LIMIT 1", (record["job_id"],)
                        ).fetchone()
                    ):
                        own = False
                if not own:
                    raise Refused("LINE_DURABLE_EXECUTION_NOT_QUIESCENT")
    except (sqlite3.Error, ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, Refused):
            raise
        raise Refused("LINE_DURABLE_LIVENESS_UNAVAILABLE") from None
