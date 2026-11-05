"""Pinned0.362 native history: typed bounded-scratch logical snapshot, never payload export.

Framing follows the independently reviewed owner-retirementv5 source; this module
contains only the pure SQLite fingerprint functions, not that OPS harness.
"""

from pathlib import Path
import hashlib
import sqlite3
import struct
from .durable import Refused

HASH_CHUNK_BYTES = 65536
TEXT_CHUNK_CHARS = 16384
TERMINAL = frozenset(("succeeded", "failed", "cancelled", "canceled"))


def require(ok, code):
    if not ok:
        raise Refused("OWNER_BOOTSTRAP_" + code)


def _quote(name):
    return '"' + name.replace('"', '""') + '"'


def _field(value):
    """Typed length + repeatable <=64KiB chunks; no JSON/BLOB type collision."""
    if value is None:
        return b"N", 0, lambda: iter(())
    if type(value) is int:
        raw = str(value).encode("ascii")
        return b"I", len(raw), lambda: iter((raw,))
    if type(value) is float:
        # SQLite numeric equality/order treats signed zero identically.
        raw = struct.pack(">d", 0.0 if value == 0 else value)
        return b"R", len(raw), lambda: iter((raw,))
    if isinstance(value, str):

        def chunks():
            for i in range(0, len(value), TEXT_CHUNK_CHARS):
                yield value[i : i + TEXT_CHUNK_CHARS].encode("utf-8", errors="strict")

        return b"T", sum(len(part) for part in chunks()), chunks
    if isinstance(value, bytes):

        def chunks():
            view = memoryview(value)
            for i in range(0, len(value), HASH_CHUNK_BYTES):
                yield view[i : i + HASH_CHUNK_BYTES]

        return b"B", len(value), chunks
    raise RuntimeError("SQLITE_STORAGE_TYPE_UNSUPPORTED")


def _hash_row(hasher, row):
    fields = [_field(value) for value in row]
    size = 4 + sum(9 + length for _, length, _ in fields)
    hasher.update(size.to_bytes(8, "big"))
    hasher.update(len(fields).to_bytes(4, "big"))
    for tag, length, chunks in fields:
        hasher.update(tag)
        hasher.update(length.to_bytes(8, "big"))
        for part in chunks():
            require(len(part) <= HASH_CHUNK_BYTES, "HASH_CHUNK_BOUND")
            hasher.update(part)
    return size + 8


def table_hashes(path, names=None):
    """Complete snapshot, typed framed rows, schema/count, no total-row cutoff.

    Python's SQLite cursor retains one row (not the DB) at a time; UTF8/hash
    scratch is <=64KiB. Non-null unique primary keys use their index order.
    NULL/no-PK tables use all-column typeof/BINARY total logical-value order.
    """
    require(path.is_file() and not path.is_symlink(), "HISTORY_DB_MISSING_OR_REBOUND")
    identity = (path.stat().st_dev, path.stat().st_ino)
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=3) as c:
        c.execute("PRAGMA query_only=ON")
        c.execute("BEGIN")
        schema = hashlib.sha256(b"forge-c/sqlite-schema-stream/1\0")
        encoding = c.execute("PRAGMA encoding").fetchone()[0]
        _hash_row(schema, (encoding,))
        for row in c.execute("SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type COLLATE BINARY,name COLLATE BINARY"):
            _hash_row(schema, row)
        schema_sha = schema.hexdigest()
        if names is None:
            names = [
                row[0]
                for row in c.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name COLLATE BINARY"
                )
            ]
        out = {}
        for name in names:
            info = list(c.execute("PRAGMA table_info(" + _quote(name) + ")"))
            require(bool(info), "HISTORY_TABLE_SCHEMA_MISSING")
            columns = [row[1] for row in info]
            primary = [row[1] for row in sorted(info, key=lambda row: row[5]) if row[5]]
            no_null_keys = (
                primary
                and c.execute(
                    "SELECT 1 FROM "
                    + _quote(name)
                    + " WHERE "
                    + " OR ".join(_quote(col) + " IS NULL" for col in primary)
                    + " LIMIT 1"
                ).fetchone()
                is None
            )
            if no_null_keys:
                # A non-null PRIMARY KEY is unique; BINARY overrides declared
                # case-folding collations without adding payload sorting.
                ordering = ",".join(_quote(col) + " COLLATE BINARY" for col in primary)
                order_kind = "NONNULL_PRIMARY_KEY_BINARY"
            else:
                ordering = ",".join(
                    "typeof(" + _quote(col) + ") COLLATE BINARY," + _quote(col) + " COLLATE BINARY" for col in columns
                )
                order_kind = "TYPE_AWARE_ALL_COLUMNS_BINARY"
            counted = c.execute("SELECT COUNT(*) FROM " + _quote(name)).fetchone()[0]
            hasher = hashlib.sha256(b"forge-c/sqlite-logical-stream/1\0" + bytes.fromhex(schema_sha))
            seen = 0
            encoded_bytes = 0
            max_row_bytes = 0
            cursor = c.execute("SELECT * FROM " + _quote(name) + " ORDER BY " + ordering)
            for row in cursor:
                size = _hash_row(hasher, row)
                seen += 1
                encoded_bytes += size
                max_row_bytes = max(max_row_bytes, size)
            require(seen == counted, "HISTORY_STREAM_COUNT_MISMATCH")
            hasher.update(b"END" + seen.to_bytes(8, "big"))
            out[name] = dict(
                algorithm="forge-c/sqlite-logical-stream/1",
                schema_sha256=schema_sha,
                rows=seen,
                sha256=hasher.hexdigest(),
                ordering=order_kind,
                encoded_bytes=encoded_bytes,
                max_row_bytes=max_row_bytes,
                hash_chunk_bytes=HASH_CHUNK_BYTES,
            )
    require(identity == (path.stat().st_dev, path.stat().st_ino), "HISTORY_DB_IDENTITY_REBOUND")
    return out


TABLE_COLUMNS = {
    "runs": [
        ("id", "TEXT", 1),
        ("source_last_seq", "INTEGER", 0),
        ("created_at_ms", "INTEGER", 0),
        ("started_at_ms", "INTEGER", 0),
        ("last_event_at_ms", "INTEGER", 0),
        ("completed_at_ms", "INTEGER", 0),
        ("status", "TEXT", 0),
        ("archived_at_ms", "INTEGER", 0),
        ("parent_id", "TEXT", 0),
        ("title", "TEXT", 0),
        ("workflow_slug", "TEXT", 0),
        ("workflow_name", "TEXT", 0),
        ("repository_name", "TEXT", 0),
        ("automation_id", "TEXT", 0),
        ("diff_files_changed", "INTEGER", 0),
        ("diff_additions", "INTEGER", 0),
        ("diff_deletions", "INTEGER", 0),
        ("input_tokens", "INTEGER", 0),
        ("output_tokens", "INTEGER", 0),
        ("reasoning_tokens", "INTEGER", 0),
        ("cache_read_tokens", "INTEGER", 0),
        ("cache_write_tokens", "INTEGER", 0),
        ("total_usd_micros", "INTEGER", 0),
        ("summary_json", "TEXT", 0),
    ],
    "run_events": [
        ("run_id", "TEXT", 1),
        ("seq", "INTEGER", 2),
        ("event_name", "TEXT", 0),
        ("node_id", "TEXT", 0),
        ("stage_id", "TEXT", 0),
        ("session_id", "TEXT", 0),
        ("event_json", "TEXT", 0),
    ],
    "run_session_records": [
        ("session_id", "TEXT", 1),
        ("run_id", "TEXT", 0),
        ("record_json", "TEXT", 0),
        ("updated_at_ms", "INTEGER", 0),
    ],
    "legacy_run_history_activation": [
        ("singleton", "INTEGER", 1),
        ("source_fingerprint", "BLOB", 0),
        ("source_runs", "INTEGER", 0),
        ("source_events", "INTEGER", 0),
        ("activated_at_ms", "INTEGER", 0),
    ],
    "legacy_run_history_deletions": [("run_id", "TEXT", 1), ("deleted_at_ms", "INTEGER", 0)],
}


def native_status(path):
    require(path.is_file() and not path.is_symlink(), "NATIVE_DB_MISSING")
    before = (path.stat().st_dev, path.stat().st_ino)
    with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=3) as db:
        db.execute("PRAGMA query_only=ON")
        db.execute("BEGIN")
        for table, columns in TABLE_COLUMNS.items():
            require(
                [(r[1], r[2], r[5]) for r in db.execute("PRAGMA table_info(" + _quote(table) + ")")] == columns,
                "NATIVE_SCHEMA_UNKNOWN",
            )
        statuses = dict(db.execute("SELECT status,COUNT(*) FROM runs GROUP BY status"))
        require(all(k in TERMINAL for k in statuses), "NATIVE_NOT_TERMINAL")
        require(
            db.execute("SELECT COUNT(*) FROM legacy_run_history_activation").fetchone()[0] == 1, "NATIVE_HISTORY_NOT_INITIALIZED"
        )
        inventory = [{"id": r[0], "status": r[1]} for r in db.execute("SELECT id,status FROM runs ORDER BY id COLLATE BINARY")]
    require(before == (path.stat().st_dev, path.stat().st_ino), "NATIVE_DB_REBOUND")
    from .durable import digest

    require(len(inventory) <= 10000, "NATIVE_INVENTORY_BOUND")
    return {"count": len(inventory), "identity_status_sha256": digest(inventory)}


def native_checkpoint(root):
    path = Path(root) / "fabro/storage/db/fabro.sqlite3"
    native_status(path)
    snapshot = table_hashes(path, tuple(TABLE_COLUMNS))
    snapshot["inventory"] = native_status(path)
    require(snapshot["inventory"]["count"] == snapshot["runs"]["rows"], "NATIVE_CHECKPOINT_CHANGED")
    return snapshot
