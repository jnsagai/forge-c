"""CAPA-187 (2026-11-07, SPI L41B): a busy store at worker attach is not a missing schema and never blocks the order."""
import sqlite3

import pytest
from forge_factory.afo import line_recovery_worker as W
from forge_factory.afo import queue as Q


def test_a_locked_store_is_busy_not_a_missing_schema(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    path = tmp_path / "state/supervisor/line-queue.sqlite3"
    Q.Store(path)  # an initialised M3 store
    real = sqlite3.connect

    def locked(database, *a, **k):
        if "mode=ro" in str(database):
            raise sqlite3.OperationalError("database is locked")
        return real(database, *a, **k)

    monkeypatch.setattr(Q.sqlite3, "connect", locked)
    with pytest.raises(Q.QueueError) as exc:
        Q.Store(path, must_exist=True)
    assert exc.value.code == "AUTHORITATIVE_DATABASE_BUSY"


def test_a_missing_schema_still_refuses(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    path = tmp_path / "state/supervisor/line-queue.sqlite3"
    path.parent.mkdir(parents=True)
    sqlite3.connect(path).close()
    with pytest.raises(Q.QueueError) as exc:
        Q.Store(path, must_exist=True)
    assert exc.value.code != "AUTHORITATIVE_DATABASE_BUSY"


def test_record_refusal_never_blocks_a_busy_store(monkeypatch):
    monkeypatch.setattr(W, "Store", lambda *a, **k: pytest.fail("a busy store must not be reopened to block the order"))
    out = W.record_refusal("afo-cmd-x", Q.QueueError("AUTHORITATIVE_DATABASE_BUSY"))
    assert out == {"action": "store_busy_retry_next_cycle", "inference_release": False}
