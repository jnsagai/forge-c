import json
from contextlib import contextmanager
from types import SimpleNamespace

from forge_factory.afo import cli, mission_admin, mission_ledger, overnight


def test_mission_link_precedes_visible_order_and_restart_keeps_original_deadline(monkeypatch):
    calls = []
    old_limits = {"deadline": 1234}

    @contextmanager
    def transaction():
        yield SimpleNamespace(execute=lambda *a: SimpleNamespace(fetchone=lambda: [json.dumps({"limits": old_limits})]))

    store = SimpleNamespace(tx=transaction, submit=lambda *a, **kw: calls.append("submit") or ("order", False))
    monkeypatch.setattr(cli, "approve", lambda *a: (True, "AUTH_OK"))

    def register(store, doc, eff):
        assert doc["orders"] == [] and doc["limits"] == old_limits
        calls.append("register-original-mission")

    monkeypatch.setattr(mission_admin, "register", register)
    monkeypatch.setattr(
        mission_ledger, "MissionLedger", lambda store: SimpleNamespace(link=lambda *a: calls.append("link-before-queue"))
    )
    entry = {
        "order_id": "order",
        "envelope": {},
        "mission": {"mission_id": "mission", "limits": {"deadline": 0}, "orders": [{"order_id": "order"}]},
    }
    eff = SimpleNamespace(get=lambda *a: 3600)
    overnight.provision_order(store, entry, eff, 9999999999)
    assert calls == ["register-original-mission", "link-before-queue", "submit"]
