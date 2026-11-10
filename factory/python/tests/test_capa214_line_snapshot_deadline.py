"""CAPA-214 (TIM LL L43K, 2026-11-10 09:57Z): the in-run model swap re-verifies the owner-development record through a
read-only queue snapshot with a 3 s deadline. Under a host load average of about 12 (parallel test suites) hashing the
control and policy files took longer, the snapshot expired (OBSERVATION_SNAPSHOT_NOT_CURRENT) and the SWE.1 run failed.
The line's authorization snapshots now use the queue's maximum deadline (120 s; owner 2026-11-09 "limits very high")."""
from __future__ import annotations

import re
from pathlib import Path

from forge_factory.afo import owner_supervised_development as D

AFO = Path(D.__file__).resolve().parent
LINE = ("owner_supervised_development.py", "line_stack_lifecycle.py", "line_recovery.py", "line_recovery_control.py")


def test_the_owner_development_snapshot_allows_a_loaded_host(monkeypatch):
    from forge_factory.afo import queue

    seen = {}
    monkeypatch.setattr(queue, "ReadSnapshot", lambda path, **kw: seen.update(kw) or kw)
    D._snapshot_store()
    assert seen["timeout_s"] >= 60


def test_no_line_authorization_snapshot_keeps_the_3_second_deadline():
    for name in LINE:
        src = (AFO / name).read_text()
        assert not re.search(r"ReadSnapshot\([^)]*timeout_s=3\b", src), name


def test_the_snapshot_connection_waits_for_a_busy_writer_within_its_deadline(tmp_path):
    import sqlite3

    from forge_factory.afo import queue

    db = tmp_path / "q.sqlite3"
    sqlite3.connect(db).execute("CREATE TABLE t (x)").connection.commit()
    seen = {}
    real = sqlite3.connect
    queue.sqlite3.connect = lambda *a, **kw: seen.update(kw) or real(*a, **kw)
    try:
        with queue.ReadSnapshot(db, timeout_s=120):
            pass
    finally:
        queue.sqlite3.connect = real
    assert seen["timeout"] >= 30
