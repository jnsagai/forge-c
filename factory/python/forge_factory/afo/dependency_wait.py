"""Persistent model-free dependency waits in existing Conductor storage."""

from __future__ import annotations

import json
import time

from .durable import Refused, canonical, digest


def probe(store, scope, condition, observe, *, now=None, maximum=600, minimum=15):
    now = time.time() if now is None else now
    if minimum < 1 or maximum < minimum:
        raise Refused("PROBE_BOUNDS_INVALID")
    key = "wait-" + digest([scope, condition])[:24]
    with store.tx() as c:
        old = c.execute("SELECT next_probe,record FROM afo_dependency_waits WHERE wait_id=?", (key,)).fetchone()
        rec = json.loads(old["record"]) if old else {"scope": scope, "condition": condition, "failures": 0}
        if old and old["next_probe"] - now > maximum:
            # A backward wall-clock correction cannot postpone recovery indefinitely.
            due = now + maximum
            c.execute("UPDATE afo_dependency_waits SET next_probe=? WHERE wait_id=?", (due, key))
            return {**rec, "due": False, "next_probe": due, "clock_regression": True}
        if old and now < old["next_probe"]:
            return {**rec, "due": False, "next_probe": old["next_probe"]}
        # Reserve the next probe before I/O; a crashed observer cannot cause a probe storm.
        due = now + min(maximum, minimum * 2 ** min(rec["failures"], 12))
        c.execute(
            "INSERT INTO afo_dependency_waits VALUES (?,?,?,?) ON CONFLICT(wait_id) DO UPDATE SET next_probe=excluded.next_probe,record=excluded.record",
            (key, scope, due, canonical(rec).decode()),
        )
    try:
        result = observe()
        healthy = result.get("ok") is True
    except (OSError, TimeoutError, ValueError) as exc:
        result, healthy = {"ok": False, "error": type(exc).__name__}, False
    rec.update(
        last_probe=now, failures=0 if healthy else rec["failures"] + 1, healthy=healthy, result=result, due=True, next_probe=due
    )
    with store.tx() as c:
        c.execute("UPDATE afo_dependency_waits SET record=? WHERE wait_id=?", (canonical(rec).decode(), key))
    return rec
