"""T034/T036/T041 — normalized, idempotent event store + collector (factory JSONL + Fabro run events).

* Unique `event_id` (INSERT OR IGNORE) + per-source offsets => replaying the same stream yields the same set.
* Every event validated against contracts/event.schema.json and redacted before persistence.
* Fabro AI events keep metadata (model, tokens, tool-call ids, outcome) — message text and any reasoning are
  dropped unless raw capture is explicitly enabled (then a redacted <=160-char excerpt only).
* Retention purge per channel (audit >= 365 d); search via FTS5; no DB access is exposed to browsers.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ..common import schema_errors, state_dir, truncate
from .emit import events_dir
from .policy import CapturePolicy, PolicyHolder
from .redact import redact_obj, redact_text

COLUMNS = ["event_id", "ts_utc", "channel", "level", "message", "redacted", "correlation_id", "run_id", "phase",
           "agent_id", "tool_id", "incident_id", "payload_ref", "duration_ms", "model", "input_tokens",
           "output_tokens", "token_count_provenance", "trace_id", "span_id", "workflow_id"]
SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
  ts_utc TEXT NOT NULL, channel TEXT NOT NULL, level TEXT NOT NULL, message TEXT NOT NULL, redacted INTEGER NOT NULL,
  correlation_id TEXT NOT NULL, run_id TEXT, phase TEXT, agent_id TEXT, tool_id TEXT, incident_id TEXT,
  payload_ref TEXT, duration_ms REAL, model TEXT, input_tokens INTEGER, output_tokens INTEGER,
  token_count_provenance TEXT, trace_id TEXT, span_id TEXT, workflow_id TEXT, source TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ev_filter ON events(channel, level, run_id);
CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(message, content='events', content_rowid='seq');
CREATE TRIGGER IF NOT EXISTS ev_ai AFTER INSERT ON events BEGIN
  INSERT INTO events_fts(rowid, message) VALUES (new.seq, new.message); END;
CREATE TRIGGER IF NOT EXISTS ev_ad AFTER DELETE ON events BEGIN
  INSERT INTO events_fts(events_fts, rowid, message) VALUES('delete', old.seq, old.message); END;
CREATE TABLE IF NOT EXISTS offsets (source TEXT PRIMARY KEY, offset INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS prefs (user TEXT PRIMARY KEY, prefs TEXT NOT NULL);
"""
LEVEL_RANK = {"ERROR": 1, "WARN": 2, "INFO": 3, "DEBUG": 4, "TRACE": 5}


class EventStore:
    def __init__(self, path: Path | None = None):
        self.path = path or state_dir() / "events" / "events.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        c.row_factory = sqlite3.Row
        try:
            yield c
        finally:
            c.close()

    def insert(self, ev: dict, source: str, policy: CapturePolicy) -> bool:
        if not policy.captures(ev["channel"], ev["level"]):
            return False
        ev, red = redact_obj(ev)
        ev["redacted"] = bool(ev.get("redacted") or red)
        ev["message"] = truncate(ev["message"], 160)
        ev.setdefault("schema_version", "0.4")
        errs = schema_errors("event.schema.json", {k: v for k, v in ev.items() if k in COLUMNS or k == "schema_version"})
        if errs:
            raise ValueError(f"event schema violation: {errs[:2]}")
        cols = [k for k in COLUMNS if k in ev]
        with self.conn() as c:
            cur = c.execute(f"INSERT OR IGNORE INTO events({','.join(cols)},source) VALUES({','.join('?' * len(cols))},?)",  # noqa: S608
                            [int(ev[k]) if k == "redacted" else ev[k] for k in cols] + [source])
            return cur.rowcount == 1

    # offsets ------------------------------------------------------------------------------------
    def get_offset(self, source: str) -> int:
        with self.conn() as c:
            r = c.execute("SELECT offset FROM offsets WHERE source=?", (source,)).fetchone()
            return int(r["offset"]) if r else 0

    def set_offset(self, source: str, off: int) -> None:
        with self.conn() as c:
            c.execute("INSERT INTO offsets(source, offset) VALUES(?,?) ON CONFLICT(source) DO UPDATE SET offset=?",
                      (source, off, off))

    # query (display filters only; never change capture) -----------------------------------------
    def query(self, channels: list[str] | None = None, min_level: str = "INFO", run_id: str | None = None,
              agent_id: str | None = None, phase: str | None = None, q: str | None = None, after_seq: int = 0,
              limit: int = 100, allowed_channels: set[str] | None = None) -> dict:
        limit = max(1, min(500, limit))
        where, args = ["seq > ?"], [after_seq]
        chans = [c for c in (channels or []) if (allowed_channels is None or c in allowed_channels)]
        if channels is not None:
            if not chans:
                return {"items": [], "next_cursor": None}
            where.append(f"channel IN ({','.join('?' * len(chans))})")
            args += chans
        elif allowed_channels is not None:
            where.append(f"channel IN ({','.join('?' * len(allowed_channels))})")
            args += sorted(allowed_channels)
        lv = [k for k, v in LEVEL_RANK.items() if v <= LEVEL_RANK.get(min_level, 3)]
        where.append(f"level IN ({','.join('?' * len(lv))})")
        args += lv
        for col, val in (("run_id", run_id), ("agent_id", agent_id), ("phase", phase)):
            if val:
                where.append(f"{col} = ?")
                args.append(val)
        if q:
            where.append("seq IN (SELECT rowid FROM events_fts WHERE events_fts MATCH ?)")
            args.append(" ".join(f'"{t}"' for t in q.replace('"', " ").split()[:8]))
        sql = f"SELECT * FROM events WHERE {' AND '.join(where)} ORDER BY seq LIMIT ?"  # noqa: S608
        with self.conn() as c:
            rows = [dict(r) for r in c.execute(sql, (*args, limit + 1))]
        more = len(rows) > limit
        rows = rows[:limit]
        for r in rows:
            r["redacted"] = bool(r["redacted"])
            r.pop("source", None)
        return {"items": rows, "next_cursor": str(rows[-1]["seq"]) if more and rows else None}

    def count(self, **filters: Any) -> int:
        with self.conn() as c:
            if not filters:
                return c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            k, v = next(iter(filters.items()))
            return c.execute(f"SELECT COUNT(*) FROM events WHERE {k}=?", (v,)).fetchone()[0]  # noqa: S608

    def purge(self, policy: CapturePolicy, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        n = 0
        with self.conn() as c:
            for ch, days in policy.retention_days.items():
                days = max(days, 365) if ch == "audit" else days
                cutoff = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
                n += c.execute("DELETE FROM events WHERE channel=? AND ts_utc < ?", (ch, cutoff)).rowcount
        return n


# --- Fabro normalisation -----------------------------------------------------------------------------
def normalize_fabro(e: dict, raw_ai: bool) -> dict | None:
    ev, p = e["event"], e.get("properties") or {}
    base = {"schema_version": "0.4", "event_id": f"fabro-{e['id']}", "ts_utc": e["ts"], "correlation_id": e["run_id"],
            "run_id": e["run_id"], "redacted": False}
    node = e.get("node_id")
    if node:
        base["phase"] = node[:80]
    if ev in ("run.started", "run.completed", "run.failed", "run.cancelled"):
        status = p.get("status") or p.get("reason") or ""
        return {**base, "channel": "human", "level": "WARN" if ev != "run.started" and status != "succeeded" else "INFO",
                "message": f"Run {ev.split('.')[1]} {status}".strip()}
    if ev in ("stage.started", "stage.completed", "stage.failed"):
        lvl = "WARN" if ev == "stage.failed" else ("INFO" if ev == "stage.completed" else "DEBUG")
        msg = f"{node} {ev.split('.')[1]}" + (f": {(p.get('failure') or {}).get('message', '')}" if ev == "stage.failed" else "")
        return {**base, "channel": "workflow", "level": lvl, "message": msg}
    if ev == "agent.tool.completed":
        d = p.get("event", {}).get("ToolCallCompleted", {})
        denied = d.get("error_kind") == "denied"
        return {**base, "channel": "security" if denied else "tools", "level": "WARN" if d.get("is_error") else "INFO",
                "message": f"{d.get('tool_name')} {'DENIED' if denied else ('error' if d.get('is_error') else 'ok')} "
                           f"out={d.get('output_bytes_observed', 0)}B", "tool_id": str(d.get("tool_name"))[:100],
                "payload_ref": f"fabro-call:{d.get('tool_call_id')}"}
    if ev == "agent.message":
        m = p.get("event", {}).get("AssistantMessage", {})
        tok = (m.get("usage") or {}).get("tokens") or {}
        msg = f"model {m.get('model')} tools={m.get('tool_call_count', 0)} in={tok.get('input')} out={tok.get('output')}"
        if raw_ai and m.get("text"):
            msg = truncate(redact_text(m["text"])[0].replace("\n", " "), 160)
        return {**base, "channel": "ai", "level": "INFO", "message": msg, "model": str(m.get("model"))[:100],
                "input_tokens": tok.get("input"), "output_tokens": tok.get("output"),
                "token_count_provenance": "reported" if tok else "unknown"}
    if ev == "agent.error":
        err = p.get("event", {}).get("Error", {}).get("error", {})
        return {**base, "channel": "ai", "level": "ERROR", "message": f"model error {err.get('llm_kind', '')}: "
                f"{err.get('message', '')}"}
    if ev.startswith("sandbox.") or ev.startswith("checkpoint"):
        return {**base, "channel": "workflow", "level": "TRACE", "message": ev}
    return None


class Collector:
    def __init__(self, store: EventStore | None = None, policy: PolicyHolder | None = None):
        self.store = store or EventStore()
        self.policy = policy or PolicyHolder()
        self.rejected = 0

    def _insert(self, ev: dict, src: str, pol: CapturePolicy) -> int:
        try:
            return int(self.store.insert(ev, src, pol))
        except (ValueError, KeyError, TypeError):
            self.rejected += 1  # malformed event never blocks ingestion of the rest of the stream
            return 0

    def ingest_segment(self, path: Path | None = None) -> int:
        path = path or events_dir() / "factory-events.jsonl"
        if not path.is_file():
            return 0
        src = f"file:{path}"
        off = self.store.get_offset(src)
        pol = self.policy.current()
        n = 0
        with open(path, "rb") as f:
            f.seek(off)
            for line in f:
                if not line.endswith(b"\n"):
                    break  # partial write: resume at this offset next time
                off += len(line)
                try:
                    ev = json.loads(line)
                except ValueError:
                    continue
                n += self._insert(ev, src, pol)
        self.store.set_offset(src, off)
        return n

    def ingest_fabro_run(self, run_id: str, client=None) -> int:
        from ..fabro.client import FabroClient, load_token

        c = client or FabroClient(token=load_token(), timeout=10)
        src = f"fabro:{run_id}"
        seq = self.store.get_offset(src)
        pol = self.policy.current()
        n = 0
        for e in c.iter_events(run_id, since_seq=seq):
            seq = max(seq, int(e["seq"]))
            ev = normalize_fabro(e, pol.raw_ai)
            if ev:
                n += self._insert(ev, src, pol)
        self.store.set_offset(src, seq)
        return n
