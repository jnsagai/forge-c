"""Recoverable CPU verification work in the existing AFO store/outbox.

A lease expiry alone never duplicates a live worker. Linux boot/pid-start identity
fences PID reuse; completed verification is reusable, publication remains draft-only.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .durable import Refused, canonical, digest


def identity(pid=None):
    pid = os.getpid() if pid is None else pid
    try:
        stat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return {"pid": pid, "start": stat[19], "boot": Path("/proc/sys/kernel/random/boot_id").read_text().strip()}
    except (OSError, IndexError):
        return None


class VerificationJobs:
    def __init__(self, store):
        self.store = store

    def ensure(self, job_id, case_sha256):
        with self.store.tx() as c:
            row = c.execute("SELECT record FROM afo_verification_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row:
                rec = json.loads(row[0])
                if rec["case_sha256"] != case_sha256:
                    raise Refused("VERIFIER_CASE_REBOUND")
                return rec
            rec = {
                "job_id": job_id,
                "case_sha256": case_sha256,
                "dispatches": 0,
                "owner": None,
                "verification_id": "verify-" + digest([job_id, case_sha256])[:24],
            }
            c.execute("INSERT INTO afo_verification_jobs VALUES (?,'READY',0,0,?)", (job_id, canonical(rec).decode()))
            return rec

    def get(self, job_id):
        with self.store.tx() as c:
            row = c.execute("SELECT * FROM afo_verification_jobs WHERE job_id=?", (job_id,)).fetchone()
        return {**dict(row), "record": json.loads(row["record"])} if row else None

    def dispatch(self, job_id, spawn, *, now=None):
        now = time.time() if now is None else now
        with self.store.tx() as c:
            rows = c.execute("SELECT * FROM afo_verification_jobs").fetchall()
            target = next((r for r in rows if r["job_id"] == job_id), None)
            if target is None:
                raise Refused("VERIFIER_JOB_UNKNOWN")
            for row in rows:
                if row["state"] not in ("DISPATCHING", "RUNNING"):
                    continue
                rec = json.loads(row["record"])
                owner = rec.get("owner")
                # Missing owner within the bounded spawn grace remains occupied.
                if (not owner and row["lease_until"] > now) or owner and identity(owner["pid"]) == owner:
                    return None
                if row["lease_until"] > now:
                    return None
                c.execute(
                    "UPDATE afo_verification_jobs SET state='READY' WHERE job_id=? AND epoch=?", (row["job_id"], row["epoch"])
                )
            target = c.execute("SELECT * FROM afo_verification_jobs WHERE job_id=?", (job_id,)).fetchone()
            if target["state"] != "READY":
                return None
            rec = json.loads(target["record"])
            epoch = target["epoch"] + 1
            if rec["dispatches"] >= 3:
                c.execute("UPDATE afo_verification_jobs SET state='BLOCKED' WHERE job_id=?", (job_id,))
                return None
            rec.update(dispatches=rec["dispatches"] + 1, owner=None)
            c.execute(
                "UPDATE afo_verification_jobs SET state='DISPATCHING',epoch=?,lease_until=?,record=? WHERE job_id=?",
                (epoch, now + 30, canonical(rec).decode(), job_id),
            )
        spawn(epoch)  # lost acknowledgment is settled by worker claim or expiry + absence; no latch remains forever
        return epoch

    def claim(self, job_id, epoch, *, now=None):
        now = time.time() if now is None else now
        with self.store.tx() as c:
            row = c.execute("SELECT * FROM afo_verification_jobs WHERE job_id=?", (job_id,)).fetchone()
            if not row or row["epoch"] != epoch or row["state"] != "DISPATCHING" or row["lease_until"] <= now:
                raise Refused("VERIFIER_CLAIM_FENCED")
            rec = json.loads(row["record"])
            rec["owner"] = identity()
            c.execute(
                "UPDATE afo_verification_jobs SET state='RUNNING',lease_until=?,record=? WHERE job_id=?",
                (now + 60, canonical(rec).decode(), job_id),
            )
            return rec

    def finish(self, job_id, epoch, result):
        with self.store.tx() as c:
            row = c.execute("SELECT * FROM afo_verification_jobs WHERE job_id=?", (job_id,)).fetchone()
            rec = json.loads(row["record"]) if row else {}
            if not row or row["epoch"] != epoch or row["state"] != "RUNNING" or rec.get("owner") != identity():
                raise Refused("VERIFIER_RESULT_FENCED")
            rec.update(result=result, result_sha256=digest(result))
            c.execute(
                "UPDATE afo_verification_jobs SET state='COMPLETE',record=?,lease_until=0 WHERE job_id=?",
                (canonical(rec).decode(), job_id),
            )
            return rec
