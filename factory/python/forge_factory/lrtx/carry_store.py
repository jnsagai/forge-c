"""Feature 021 FR-001/FR-009: the validated-item store.

One sqlite index per line state directory. An item validated in one run (an author answer that passed the
deterministic validators, an inspector verdict) is recorded with its phase, item key, content sha, dependency-set sha
and provenance (the source order and the sha of the record that holds it). A rerun finds an item only for the SAME
dependency set, and only while the source record is still byte-identical (SOURCE_RECORD_CHANGED otherwise). The store
never decides validity on its own: carried items are re-validated by the current validators (FR-003)."""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from ..common import sha256_file, state_dir

SCHEMA = """CREATE TABLE IF NOT EXISTS validated_items (
  phase TEXT NOT NULL, item_key TEXT NOT NULL, content_sha TEXT NOT NULL, dep_sha TEXT NOT NULL,
  source_order TEXT NOT NULL, record TEXT NOT NULL, record_sha TEXT NOT NULL, verdicts TEXT NOT NULL, at REAL NOT NULL,
  PRIMARY KEY (phase, item_key, content_sha, dep_sha, source_order))"""


class CarryRefused(RuntimeError):
    pass


class Store:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else state_dir() / "supervisor/validated-items.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute(SCHEMA)

    def put(self, phase: str, item_key: str, *, content_sha: str, dep_sha: str, record: Path, source_order: str,
            verdicts: dict) -> None:
        with closing(sqlite3.connect(self.path)) as c, c:
            c.execute("INSERT OR REPLACE INTO validated_items VALUES (?,?,?,?,?,?,?,?,?)",
                      (phase, item_key, content_sha, dep_sha, source_order, str(Path(record).resolve()),
                       sha256_file(Path(record)), json.dumps(verdicts, sort_keys=True), time.time()))

    def find(self, phase: str, item_key: str, *, dep_sha: str, sources: list[str] | None = None) -> dict | None:
        """The item validated for exactly this dependency set: from the first of `sources` that has it (the order's
        priority), else the newest. Raises CarryRefused when its source record changed or is gone."""
        with closing(sqlite3.connect(self.path)) as c:
            c.row_factory = sqlite3.Row
            rows = [dict(r) for r in c.execute("SELECT * FROM validated_items WHERE phase=? AND item_key=? AND dep_sha=? "
                                               "ORDER BY at DESC", (phase, item_key, dep_sha))]
        if sources is not None:
            rank = {s: i for i, s in enumerate(sources)}
            rows = sorted((r for r in rows if r["source_order"] in rank), key=lambda r: rank[r["source_order"]])
        if not rows:
            return None
        hit = rows[0]
        rec = Path(hit["record"])
        if not rec.is_file() or sha256_file(rec) != hit["record_sha"]:
            raise CarryRefused(f"SOURCE_RECORD_CHANGED:{hit['source_order']}:{item_key}")
        hit["verdicts"] = json.loads(hit["verdicts"])
        return hit

    def orders_for(self, phase: str, dep_sha: str) -> list[str]:
        """The source orders that validated items of `phase` for exactly this dependency set, newest first."""
        with closing(sqlite3.connect(self.path)) as c:
            return [r[0] for r in c.execute("SELECT source_order, max(at) m FROM validated_items WHERE phase=? AND "
                                            "dep_sha=? GROUP BY source_order ORDER BY m DESC", (phase, dep_sha))]

    def latest_task_record(self, phase: str, task: str, *, dep_sha: str, source_order: str, root: Path) -> Path | None:
        """Return the latest published task snapshot, ignoring older rows pointing to working checkpoints."""
        with closing(sqlite3.connect(self.path)) as c:
            row = c.execute(
                "SELECT record, record_sha FROM validated_items WHERE phase=? AND dep_sha=? AND source_order=? "
                "AND instr(item_key, ?)=1 AND instr(record, ?)=1 ORDER BY at DESC LIMIT 1",
                (phase, dep_sha, source_order, task + "|", str(root.resolve()) + "/"),
            ).fetchone()
        if row is None:
            return None
        record, sha = Path(row[0]), row[1]
        if (record.parent != root.resolve() or record.name != f"{sha}.json" or record.is_symlink()
                or not record.is_file() or sha256_file(record) != sha):
            raise CarryRefused(f"SOURCE_RECORD_CHANGED:{source_order}:{task}")
        return record
