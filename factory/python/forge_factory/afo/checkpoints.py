"""AFO-T030/T031 (AFO-FR-031/032/035, AT-022/023/024) - accepted SWE checkpoints and safe new-attempt recovery.

A checkpoint is recorded only for a phase whose gate is PASS on an intact, non-stale baseline with its inspection
(inspection.engine.Store.gate), keeping the baseline hash, the upstream baselines it was built on and the inspection
id. Records are immutable (INSERT OR IGNORE on attempt/phase/hash). A phase is reusable only while its whole upstream
chain is unchanged: the first phase that did not pass, or whose upstream differs, invalidates everything after it.
Recovery never continues a finished attempt: it opens attempt seq+1 (new work order, new workspace, same order id)
that resumes from the previous attempt through workorder.resume_from, which copies the reusable phases
byte-identical and re-checks that each still PASSES in the new workspace.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..common import utc_now
from .queue import QueueError, Store

PHASES = ("SWE.1", "SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6")


def capture(store: Store, order_id: str, attempt_id: str, ws: Path) -> list[str]:
    from ..inspection.engine import Store as Phases

    st, done = Phases(Path(ws)), []
    for ph in PHASES:
        g = st.gate(ph)
        bl = st.latest_baseline(ph)
        if g["decision"] != "PASS" or bl is None:
            break
        cid = "afo-ck-" + hashlib.sha256(f"{attempt_id}|{ph}|{bl['baseline_hash']}".encode()).hexdigest()[:16]
        with store.tx() as c:
            c.execute("INSERT OR IGNORE INTO afo_checkpoints VALUES (?,?,?,?,?,?,?,?,?)",
                      (cid, order_id, attempt_id, ph, bl["baseline_hash"], json.dumps(bl.get("upstream") or {},
                                                                                        sort_keys=True),
                       g["reason"], bl.get("frozen_at", ""), utc_now()))
        done.append(ph)
    return done


def checkpoints(store: Store, attempt_id: str) -> list[dict]:
    with store.tx() as c:
        return [{**dict(r), "upstream": json.loads(r["upstream"])} for r in
                c.execute("SELECT * FROM afo_checkpoints WHERE attempt_id=?", (attempt_id,))]


def reusable(cks: list[dict]) -> list[str]:
    """Leading phases whose recorded upstream hashes equal the checkpoints of their upstream phases."""
    by = {c["phase"]: c for c in cks}
    out = []
    for ph in PHASES:
        c = by.get(ph)
        if c is None or any(by.get(up, {}).get("baseline_hash") != h for up, h in c["upstream"].items()):
            break
        out.append(ph)
    return out


def new_attempt(store: Store, order_id: str, *, plan_id: str, epoch: int, max_attempts: int,
                source_wo: str) -> str:
    """WAITING_RECOVERY order -> attempt seq+1 (PREPARED) + FABRO_LAUNCH intent that resumes from `source_wo`."""
    with store.tx() as c:
        o = c.execute("SELECT state FROM afo_work_orders WHERE order_id=?", (order_id,)).fetchone()
        if o is None or o["state"] != "WAITING_RECOVERY":
            raise QueueError("NOT_WAITING_RECOVERY", order_id)
        prior = c.execute('SELECT attempt_id,record FROM afo_attempts WHERE order_id=?', (order_id,)).fetchall()
        existing = next((r['attempt_id'] for r in prior if json.loads(r['record']).get('recovery_plan_id') == plan_id), None)
        if existing:
            return existing
        n = len(prior)
        if n >= max_attempts:
            raise QueueError("ORDER_ATTEMPT_BUDGET_EXHAUSTED", f"{n} >= {max_attempts}")
        seq = n + 1
        aid = f"{order_id}-a{seq}"
        rec = {"schema_version": "1.0", "order_id": order_id, "attempt_id": aid, "attempt_seq": seq, "state": "PREPARED",
               "workspace_ref": f"pending:{aid}", "factory_revision": "pending", "created_utc": utc_now(),
               "fabro_run_id": None, "fabro_server": None, "recovery_plan_id": plan_id, "exit_status": None,
               "terminal_package_status": None, "checkpoint_refs": [f"resume_from:{source_wo}"], "evidence_refs": [],
               "finished_utc": None}
        from . import contracts

        contracts.require("attempt", rec)
        c.execute("INSERT INTO afo_attempts (attempt_id, order_id, seq, state, record, created_utc) VALUES (?,?,?,?,?,?)",
                  (aid, order_id, seq, "PREPARED", json.dumps(rec), rec["created_utc"]))
        store._enqueue(c, "FABRO_LAUNCH", f"launch:{aid}", order_id, aid, epoch,
                       {"attempt_id": aid, "resume_from": source_wo, "recovery_plan_id": plan_id})
        store._event(c, "recovery_attempt", order_id, aid, {"plan_id": plan_id, "resume_from": source_wo})
    return aid
