"""CAPA-192: V21.5 guardian 66e3bfa3 died 2026-11-08 02:56:55 UTC on sqlite3.OperationalError 'database is locked'
inside Placer.cycle (queue.tx BEGIN IMMEDIATE past the 10 s busy timeout). A busy store must defer one cycle, not end
the guardian; a persistent lock and every other error still end it."""
# ruff: noqa: F811
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.mission_ledger import MissionLedger
from test_owner_supervised_development import supervised  # noqa: F401


def run_main(supervised, monkeypatch, tmp_path, outcomes, cycles):
    from forge_factory.afo import line_launcher as LL
    from forge_factory.afo import line_orders as O

    monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "1")
    monkeypatch.setenv("FORGE_DURABLE_NATIVE_HEADER", "1")
    monkeypatch.setattr(LL.LineConfig, "from_env", lambda: SimpleNamespace(stack_root=tmp_path))
    monkeypatch.setattr(O, "RealLine", lambda _: object())
    monkeypatch.setattr(D, "provider_preflight", lambda _: {"placing": True})
    calls = []

    class Placer:
        def __init__(self, *_, **__):
            pass

        def cycle(self):
            calls.append(1)
            out = outcomes[min(len(calls), len(outcomes)) - 1]
            if isinstance(out, BaseException):
                raise out
            return {"actions": []}

    monkeypatch.setattr(O, "Placer", Placer)
    rc = D.main(["--control", supervised["control_ref"]["path"],
                 "--runtime-policy", str(supervised["runtime"]), "--line-policy", str(supervised["line"]),
                 "--campaigns", str(tmp_path / "unused-campaigns"), "--interval", "1",
                 "--expiry-ticket", str(supervised["ticket_path"]), "--max-cycles", str(cycles)])
    audit = Path(os.environ.get(D.FILE) or supervised["ref"]["path"]).with_suffix(".audit.jsonl")
    return rc, calls, audit


def audit_rows(supervised):
    import json
    path = Path(supervised["ref"]["path"]).parent
    rows = []
    for f in path.glob("*.audit.jsonl"):
        rows += [json.loads(x) for x in f.read_text().splitlines()]
    return rows


def test_one_locked_cycle_is_deferred_and_the_guardian_keeps_placing(supervised, monkeypatch, tmp_path):
    before = MissionLedger(supervised["store"]).snapshot(D.MISSION)
    locked = sqlite3.OperationalError("database is locked")
    rc, calls, _ = run_main(supervised, monkeypatch, tmp_path, [locked, None], 3)
    assert rc == 0 and len(calls) == 3
    rows = audit_rows(supervised)
    assert [r["placement"].get("deferred") for r in rows][-3:] == ["STORE_BUSY", None, None]
    assert MissionLedger(supervised["store"]).snapshot(D.MISSION) == before


def test_persistent_lock_still_ends_the_guardian(supervised, monkeypatch, tmp_path):
    locked = sqlite3.OperationalError("database is locked")
    with pytest.raises(sqlite3.OperationalError):
        run_main(supervised, monkeypatch, tmp_path, [locked], D.STORE_BUSY_LIMIT + 5)


@pytest.mark.parametrize("err", [sqlite3.OperationalError("no such table: afo_work_orders"),
                                 sqlite3.DatabaseError("database disk image is malformed"), RuntimeError("x")])
def test_other_errors_still_end_the_guardian(supervised, monkeypatch, tmp_path, err):
    with pytest.raises(type(err)):
        run_main(supervised, monkeypatch, tmp_path, [err], 3)


def test_busy_classification_is_exact():
    assert D.store_busy(sqlite3.OperationalError("database is locked"))
    assert D.store_busy(sqlite3.OperationalError("database table is locked"))
    assert not D.store_busy(sqlite3.OperationalError("disk I/O error"))
    assert not D.store_busy(RuntimeError("database is locked"))
