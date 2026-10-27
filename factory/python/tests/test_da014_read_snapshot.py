"""Real SQLite snapshot isolation and nonmutation for external qualification."""
# ruff: noqa: F811

import sqlite3

import pytest
from forge_factory.afo import queue
from forge_factory.common import sha256_file
from test_da014_fault_observer import setup  # noqa: F401


def test_read_snapshot_reuses_store_queries_and_never_migrates_or_writes(setup):
    p = setup
    before = sha256_file(p.db)
    with queue.ReadSnapshot(p.db) as view:
        assert view.schema_version() == p.store.schema_version()
        assert view.orders() == []
        with view.tx() as c, pytest.raises(sqlite3.OperationalError, match="readonly"):
            c.execute("DELETE FROM afo_missions")
    assert sha256_file(p.db) == before
    with pytest.raises(queue.QueueError, match="NOT_CURRENT"):
        view.schema_version()


def test_snapshot_is_consistent_while_the_actual_writer_commits(setup):
    p = setup
    with queue.ReadSnapshot(p.db) as view:
        with view.tx() as c:
            before = c.execute("SELECT COUNT(*) FROM afo_mission_executions").fetchone()[0]
        p.mission.execution("fixture-mission", "second-fixture", "DIAGNOSIS", reserved_tokens=10)
        with view.tx() as c:
            assert c.execute("SELECT COUNT(*) FROM afo_mission_executions").fetchone()[0] == before
    with queue.ReadSnapshot(p.db) as view, view.tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_mission_executions").fetchone()[0] == before + 1


def test_read_snapshot_never_creates_missing_storage(setup):
    p = setup
    missing = p.tmp / "must-not-create" / "database.sqlite3"
    with pytest.raises(queue.QueueError, match="DATABASE_UNAVAILABLE"):
        queue.ReadSnapshot(missing)
    assert not missing.parent.exists()


def test_row_and_byte_limits_are_cumulative_across_queries(setup):
    p = setup
    with queue.ReadSnapshot(p.db, max_rows=1) as view:
        assert view.schema_version()
        with pytest.raises(queue.QueueError, match="BOUND_EXCEEDED"):
            view.schema_version()
    with queue.ReadSnapshot(p.db, max_bytes=4096) as view, view.tx() as c:
        c.execute("SELECT '" + "x" * 2500 + "'").fetchone()
        with pytest.raises(queue.QueueError, match="BOUND_EXCEEDED"):
            c.execute("SELECT '" + "x" * 2500 + "'").fetchone()


def test_snapshot_deadline_is_checked_before_every_read(setup, monkeypatch):
    p = setup
    with queue.ReadSnapshot(p.db) as view:
        monkeypatch.setattr(queue.time, "monotonic", lambda: view.deadline + 1)
        with pytest.raises(queue.QueueError, match="NOT_CURRENT"):
            view.schema_version()


@pytest.mark.parametrize(
    "bound", [{"max_rows": 0}, {"max_rows": True}, {"max_bytes": 0}, {"timeout_s": float("nan")}, {"timeout_s": 0}]
)
def test_snapshot_requires_finite_positive_bounds(setup, bound):
    with pytest.raises(queue.QueueError, match="BOUND_INVALID"):
        queue.ReadSnapshot(setup.db, **bound)
