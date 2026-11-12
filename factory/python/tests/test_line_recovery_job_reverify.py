"""Reverifying a job inside the mission writer must not wait on itself.

`reserve_request` holds BEGIN IMMEDIATE and calls `authorize()`, which reaches `valid_job`. The private launch
rehearsal found a second writer connection there: every model request failed with `database is locked`.
"""
import sqlite3
import time

import pytest
from forge_factory.afo import line_recovery as R
from forge_factory.afo.queue import Store
from forge_factory.common import canonical_json, sha256_bytes


@pytest.fixture
def writer(tmp_path, monkeypatch):
    state = tmp_path / "state"
    monkeypatch.setenv("FORGE_STATE_DIR", str(state))
    monkeypatch.setenv("FORGE_CRE_DB_TIMEOUT_S", "2")
    monkeypatch.setattr(R, "state_dir", lambda: state)
    (state / "supervisor").mkdir(parents=True)
    return Store(state / "supervisor/line-queue.sqlite3")


JOB = dict(order_id="order", attempt_id="attempt", source_workspace="/absent", line_origin={"campaign_path": "/c"})


def bound(value):
    return {**JOB, "line_context_sha256": sha256_bytes(canonical_json(value))}


def test_reverify_answers_while_the_same_process_holds_the_writer(writer, monkeypatch):
    seen = []

    def context(store, *args):
        seen.append(store.order("order"))
        return {"bound": True}

    monkeypatch.setattr(R, "context", context)
    started = time.monotonic()
    with writer.tx():
        assert R.valid_job(bound({"bound": True})) is True
    assert seen == [None] and time.monotonic() - started < 1.5


def test_changed_context_still_refuses(writer, monkeypatch):
    monkeypatch.setattr(R, "context", lambda *a: {"bound": "changed"})
    assert R.valid_job(bound({"bound": True})) is False


def test_snapshot_cannot_write(writer, monkeypatch):
    def context(store, *args):
        with store.tx() as c:
            c.execute("INSERT INTO afo_schema_version VALUES (999, 'x')")

    monkeypatch.setattr(R, "context", context)
    assert R.valid_job(bound({})) is False


def test_missing_database_is_refused_without_creating_one(tmp_path, monkeypatch):
    state = tmp_path / "state"
    monkeypatch.setattr(R, "state_dir", lambda: state)
    assert R.valid_job(bound({})) is False
    assert not (state / "supervisor/line-queue.sqlite3").exists()


def test_explicit_store_argument_is_unchanged(writer, monkeypatch):
    seen = []
    monkeypatch.setattr(R, "context", lambda store, *a: seen.append(store) or {"bound": True})
    assert R.valid_job(bound({"bound": True}), writer) is True
    assert seen == [writer] and sqlite3.sqlite_version
