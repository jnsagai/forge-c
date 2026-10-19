"""AFO-T055 (AFO-FR-059/060; AT-037/038/040/042) - alert outbox with deduplication and a local fallback.

* One row per dedupe key (`dlq:<case>`, ...), created in the SAME transaction as the fact it reports. A repeat inside
  the policy window (notifications.dedupe_window_seconds) only counts; after the window a still-pending fact may be
  re-announced once per window - rate-limited, never a storm.
* Delivery is at-least-once. The local fallback ALWAYS records the notice: an append-only 0600 JSONL notice log under
  the Conductor state and the 002 event ledger (channel `human`). Optional channel adapters (callables) are tried
  after it; a failing adapter is retried with bounded backoff and never blocks the queue.
* Payloads carry ids, codes and refs only, redacted again before persistence (no secrets, no file contents).
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime

from ..common import state_dir, utc_now
from ..events.redact import redact_obj

MAX_ATTEMPTS = 5


def _epoch(utc: str) -> float:
    return datetime.fromisoformat(utc.replace("Z", "+00:00")).replace(tzinfo=UTC).timestamp()


def _stamp(now: float) -> str:
    return datetime.fromtimestamp(now, UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def enqueue(c, dedupe_key: str, severity: str, payload: dict, *, window_s: float = 900,
            now: float | None = None) -> tuple[str, str]:
    """Inside the caller's transaction. Returns (notification_id, 'new' | 'counted' | 'rearmed')."""
    now = now or time.time()
    stamp = _stamp(now)
    row = c.execute("SELECT * FROM afo_notifications WHERE dedupe_key=?", (dedupe_key,)).fetchone()
    if row is None:
        nid = "afo-ntf-" + hashlib.sha256(dedupe_key.encode()).hexdigest()[:20]
        body, _ = redact_obj(payload)
        c.execute("INSERT INTO afo_notifications (notification_id, dedupe_key, delivery_state, channel, severity,"
                  " first_utc, last_utc, count, payload) VALUES (?,?,?,?,?,?,?,?,?)",
                  (nid, dedupe_key, "PENDING", "local", severity, stamp, stamp, 1, json.dumps(body, sort_keys=True)))
        return nid, "new"
    # re-announce only a fact still being reported a full window after its last DELIVERY (not after the last count)
    rearm = row["delivery_state"] in ("DELIVERED", "DELIVERED_LOCAL_ONLY") and row["delivered_utc"] is not None \
        and now - _epoch(row["delivered_utc"]) >= window_s
    c.execute("UPDATE afo_notifications SET count=count+1, last_utc=?, delivery_state=?, next_epoch=? "
              "WHERE notification_id=?", (stamp, "PENDING" if rearm else row["delivery_state"],
                                          0 if rearm else row["next_epoch"], row["notification_id"]))
    return row["notification_id"], "rearmed" if rearm else "counted"


def notice_log():
    d = state_dir() / "conductor"
    d.mkdir(parents=True, exist_ok=True)
    return d / "notifications.jsonl"


def deliver(store, adapters: dict | None = None, *, now: float | None = None, emit=None) -> list[dict]:
    """Deliver PENDING notifications: local fallback first (always), then each adapter; bounded retries."""
    from ..events.emit import emit as emit_default

    emit = emit or emit_default
    now = now or time.time()
    out = []
    with store.tx() as c:
        rows = [dict(r) for r in c.execute("SELECT * FROM afo_notifications WHERE delivery_state IN ('PENDING','RETRY')"
                                           " AND next_epoch<=? ORDER BY first_utc", (now,))]
    for r in rows:
        payload = json.loads(r["payload"])
        if r["delivery_state"] == "PENDING":  # local fallback: exactly one line per (re)announcement
            log = notice_log()
            fd = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            with os.fdopen(fd, "a") as f:
                f.write(json.dumps({"notification_id": r["notification_id"], "utc": utc_now(), "severity": r["severity"],
                                    "dedupe_key": r["dedupe_key"], "count": r["count"], "payload": payload},
                                   sort_keys=True) + "\n")
            emit("human", "WARN" if r["severity"] in ("WARN", "ERROR", "CRITICAL") else "INFO",
                 f"AFO alert {r['dedupe_key']}", correlation_id=payload.get("order_id"), payload_ref=r["notification_id"])
        failed = []
        for name, send in (adapters or {}).items():
            try:
                send({"notification_id": r["notification_id"], "severity": r["severity"], **payload})
            except Exception as exc:  # noqa: BLE001 - an adapter failure is retried, never fatal to the Conductor
                failed.append(f"{name}:{type(exc).__name__}")
        attempts = r["attempts"] + 1
        state = "DELIVERED" if not failed else ("RETRY" if attempts < MAX_ATTEMPTS else "DELIVERED_LOCAL_ONLY")
        with store.tx() as c:
            c.execute("UPDATE afo_notifications SET delivery_state=?, attempts=?, next_epoch=?, delivered_utc=? "
                      "WHERE notification_id=?", (state, attempts, now + min(3600, 60 * 2 ** attempts) if failed else 0,
                                                  _stamp(now), r["notification_id"]))
        out.append({"notification_id": r["notification_id"], "state": state, "failed": failed})
    return out


def notifications(store) -> list[dict]:
    with store.tx() as c:
        return [dict(r) for r in c.execute("SELECT * FROM afo_notifications ORDER BY first_utc")]
