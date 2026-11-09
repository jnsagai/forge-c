"""CAPA-205 (deploy of c052a38c refused 2026-11-09T13:01:59Z): the deployer's budget capture reads the mission with a
plain sqlite3 connection (no row factory); MissionLedger._snapshot indexed the counter rows by column name, which only
fails once the mission has TOOL counters - and since CAPA-203 the line queue holds them. A snapshot must not depend on
the connection's row type."""
from __future__ import annotations

import sqlite3
import time
from types import SimpleNamespace

from forge_factory.afo import authz
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import Store


def test_a_plain_connection_reads_the_same_snapshot_with_tool_counters(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("FORGE_OPERATIONS_INTENT", raising=False)
    monkeypatch.setattr(authz, "verify", lambda *a, **k: SimpleNamespace(allow=True, code="FIXTURE_ONLY"))
    store = Store()
    ledger = MissionLedger(store)
    limits = dict(max_attempts=3, max_jobs=4, max_requests=32, max_tokens=120000, max_tools=32, max_corrections=4,
                  deadline=time.time() + 3600)
    ledger.register("m", "same:m:objective", limits, "AUTH-T", authorize=lambda *a: True)
    for n in range(3):
        ledger.count("m", "job-1", "TOOL", f"ev-t{n}")
    ledger.count("m", "job-1", "CORRECTION", "ev-c1")
    named = ledger.snapshot("m")
    assert (named["tools"], named["corrections"]) == (3, 1)
    plain = sqlite3.connect(f"file:{store.path}?mode=ro", uri=True)
    try:
        assert MissionLedger._snapshot(plain, "m") == named
    finally:
        plain.close()
