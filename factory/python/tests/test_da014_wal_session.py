"""A bounded WAL session retains independent FULL commits and crash recovery."""
import sqlite3
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from forge_factory.afo.queue import Store


@pytest.fixture
def store(tmp_path, monkeypatch):
    # Isolated storage fixture, not the authoritative factory database.
    monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "0")
    s = Store(tmp_path / "state.sqlite3")
    with s.tx() as c:
        c.execute("CREATE TABLE probe (n INTEGER PRIMARY KEY, receipt TEXT NOT NULL)")
    return s


def test_session_holds_no_transaction_or_writer_lock_and_commits_remain_visible(store, monkeypatch):
    connect = store.connect
    opened = []

    def track():
        c = connect()
        opened.append(c)
        return c

    monkeypatch.setattr(store, "connect", track)
    with store.wal_session() as authority:
        assert authority is None  # no new connection/write authority exposed
        keeper = opened[0]
        assert not keeper.in_transaction
        assert keeper.execute("PRAGMA synchronous").fetchone()[0] == 2
        with store.tx() as c:
            c.execute("INSERT INTO probe VALUES (1, 'first independent receipt')")
        assert Path(str(store.path) + "-wal").stat().st_size > 0
        other = connect()
        try:
            other.execute("PRAGMA busy_timeout=20")
            assert other.execute("SELECT receipt FROM probe WHERE n=1").fetchone()[0] == "first independent receipt"
            other.execute("BEGIN IMMEDIATE")
            other.execute("INSERT INTO probe VALUES (2, 'concurrent writer receipt')")
            other.execute("COMMIT")
        finally:
            other.close()
        assert not keeper.in_transaction
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        keeper.execute("SELECT 1")
    c = connect()
    try:
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert c.execute("SELECT COUNT(*) FROM probe").fetchone()[0] == 2
    finally:
        c.close()


def test_exception_closes_session_without_rolling_back_prior_commits(store):
    with pytest.raises(RuntimeError, match="cycle failed"):
        with store.wal_session():
            with store.tx() as c:
                c.execute("INSERT INTO probe VALUES (1, 'committed')")
            with pytest.raises(ValueError, match="bad operation"):
                with store.tx() as c:
                    c.execute("INSERT INTO probe VALUES (2, 'rolled back')")
                    raise ValueError("bad operation")
            raise RuntimeError("cycle failed")
    with store.tx() as c:
        assert [tuple(r) for r in c.execute("SELECT * FROM probe")] == [(1, "committed")]


def test_full_commits_survive_process_crash_before_session_close(store):
    code = """import os,sys
from pathlib import Path
from forge_factory.afo.queue import Store
s=Store(Path(sys.argv[1]))
with s.wal_session():
 for n in range(16):
  with s.tx() as c:c.execute('INSERT INTO probe VALUES (?,?)',(n,'receipt-'+str(n)))
 os._exit(17)
"""
    result = subprocess.run([sys.executable, "-c", code, str(store.path)], timeout=20)
    assert result.returncode == 17
    assert Path(str(store.path) + "-wal").is_file()
    reopened = Store(store.path)
    with reopened.tx() as c:
        assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert [tuple(r) for r in c.execute("SELECT * FROM probe ORDER BY n")] == [
            (n, "receipt-" + str(n)) for n in range(16)
        ]


def test_durable_conductor_bounds_keeper_to_one_cycle_and_closes_on_failure(store, monkeypatch):
    from forge_factory.afo import conductor, policy, queue

    monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "1")
    monkeypatch.setattr(queue, "Store", lambda: store)
    monkeypatch.setattr(policy, "load", lambda **kw: policy.Effective("PILOT", "PILOT", "hash", {}))
    events = []
    original = store.wal_session

    @contextmanager
    def session():
        with original():
            events.append("open")
            try:
                yield
            finally:
                events.append("close")

    monkeypatch.setattr(store, "wal_session", session)

    def cycle(n, **kw):
        assert kw["store"] is store and events[-1] == "open"
        if n == 1:
            raise RuntimeError("injected cycle exception")
        return "PILOT", True, "unchanged cycle"

    monkeypatch.setattr(conductor, "_cycle", cycle)
    assert conductor.cycle(0) == ("PILOT", True, "unchanged cycle")
    with pytest.raises(RuntimeError, match="injected"):
        conductor.cycle(1)
    assert events == ["open", "close", "open", "close"]


def test_disabled_absent_database_stays_absent_and_legacy_cycle_keeps_contract(tmp_path, monkeypatch):
    from forge_factory.afo import conductor, policy, queue

    monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "1")
    monkeypatch.setattr(policy, "load", lambda **kw: policy.Effective("DISABLED", None, None, None))
    monkeypatch.setattr(queue, "default_path", lambda: tmp_path / "absent.sqlite3")
    monkeypatch.setattr(queue, "Store", lambda: pytest.fail("disabled factory created database"))
    assert conductor.cycle(0) == ("DISABLED", True, "")
    assert not (tmp_path / "absent.sqlite3").exists()
    monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "0")
    monkeypatch.setattr(conductor, "_cycle", lambda n: ("LEGACY", True, str(n)))
    assert conductor.cycle(7) == ("LEGACY", True, "7")
