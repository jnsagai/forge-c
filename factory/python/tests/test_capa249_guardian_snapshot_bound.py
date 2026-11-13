"""CAPA-249 (local line, L50 set inspection 2026-11-13 14:26Z): the live owner-development guardian crashed with
OBSERVATION_SNAPSHOT_BOUND_EXCEEDED. Its call-authority check reads the whole mission ledger through one ReadSnapshot,
and that snapshot was capped at 10,000 rows and 16 MiB. The ledger grows with every model call: on the live queue,
prior_conserved plus the mission ledger alone read 5,937 rows and 16,461,885 bytes. The gateway refused the
inspector's calls (CALL_REFUSED:AUTH_RECORD_MISSING) and the guardian then exited, taking the line down.

Owner rule (limits very high): a bound protects against a runaway read, not against normal growth of the line's
own history. The live-queue snapshots now take a very high default bound."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from forge_factory.afo import queue

SRC = Path(queue.__file__).parent


def _grown(tmp_path, rows, size):
    db = tmp_path / "line-queue.sqlite3"
    import sqlite3

    c = sqlite3.connect(db)
    c.execute("CREATE TABLE ledger (id INTEGER PRIMARY KEY, record TEXT)")
    c.executemany("INSERT INTO ledger (record) VALUES (?)", (("x" * size,) for _ in range(rows)))
    c.commit()
    c.close()
    return db


def test_a_grown_ledger_of_more_than_16_mib_and_10000_rows_reads_in_one_snapshot(tmp_path):
    db = _grown(tmp_path, 12000, 2048)  # 12,000 rows, ~24 MiB: both former caps exceeded
    with queue.ReadSnapshot(db, timeout_s=120) as view, view.tx() as c:
        assert len(c.execute("SELECT record FROM ledger").fetchall()) == 12000


def test_a_runaway_read_is_still_bounded(tmp_path):
    db = _grown(tmp_path, 10, 64)
    with queue.ReadSnapshot(db, max_rows=3) as view, view.tx() as c:
        with pytest.raises(queue.QueueError, match="OBSERVATION_SNAPSHOT_BOUND_EXCEEDED"):
            c.execute("SELECT record FROM ledger").fetchall()
    with pytest.raises(queue.QueueError, match="OBSERVATION_BOUND_INVALID"):
        queue.ReadSnapshot(db, max_bytes=0)


@pytest.mark.parametrize("module", ["owner_supervised_development.py", "line_recovery.py", "line_stack_lifecycle.py"])
def test_the_live_queue_snapshots_take_the_high_default(module):
    src = (SRC / module).read_text()
    calls = [ln for ln in src.splitlines() if "ReadSnapshot(" in ln and "line-queue.sqlite3" in ln]
    assert calls, module
    for line in calls:
        assert not re.search(r"max_(rows|bytes)=", line), (module, line)


def test_the_default_bound_covers_years_of_ledger_growth():
    import inspect

    p = inspect.signature(queue.ReadSnapshot.__init__).parameters
    assert p["max_rows"].default >= 1_000_000 and p["max_bytes"].default >= 1_000_000_000
