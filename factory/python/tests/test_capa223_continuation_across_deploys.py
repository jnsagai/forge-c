"""CAPA-223 (owner lane, 2026-11-09 SWE2-WWDGL-L44 and every later SWE.2 continuation): a phase continuation
(resume_from a passed SWE.1 order) was refused LINE_PRODUCT_CONTINUATION_CONTROL_CHANGED because each deploy issues a
new owner-development control and the parent order ran under an earlier deploy's control. On the owner-development
lane a parent that is no longer active is now an independently validated frozen input (no mission continuation link,
its historical consumption stays where it is); an active parent or any other mode still refuses."""
import types

import pytest

from forge_factory.afo import line_orders
from forge_factory.afo import line_recovery_product as P
from forge_factory.afo.durable import Refused

OLD = {"path": "/q/owner-allowance-ecec42e9-main/control.json", "sha256": "b" * 64}
NEW = {"path": "/q/owner-allowance-c1738241-main/control.json", "sha256": "c" * 64}
SPEC = {"resume_from": "WO-F014-SWE1-WWDGL-20261109-L44F", "durable_control": NEW}
CONTROL = {"mission": {"mission_id": "mission-e"}}


def _setup(monkeypatch, state, control):
    parent = {"request_id": SPEC["resume_from"], "order_id": "afo-p", "state": state}
    monkeypatch.setattr(line_orders, "_load", lambda path: {"durable_control": control})
    store = types.SimpleNamespace(orders=lambda: [parent])
    ledger = types.SimpleNamespace(for_order=lambda oid: "mission-e")
    return store, ledger, parent


def test_a_passed_parent_from_an_earlier_deploy_is_a_frozen_input_on_the_development_lane(monkeypatch):
    store, ledger, _ = _setup(monkeypatch, "BLOCKED", OLD)
    assert P.continuation_parent(store, SPEC, ledger, CONTROL, development_mode=True) is None


def test_the_same_control_still_links_the_continuation(monkeypatch):
    store, ledger, parent = _setup(monkeypatch, "BLOCKED", NEW)
    assert P.continuation_parent(store, SPEC, ledger, CONTROL, development_mode=True) == parent


@pytest.mark.parametrize("state,dev", [("RUNNING", True), ("WAITING_RECOVERY", True), ("BLOCKED", False)])
def test_an_active_parent_or_another_mode_still_refuses(monkeypatch, state, dev):
    store, ledger, _ = _setup(monkeypatch, state, OLD)
    with pytest.raises(Refused) as e:
        P.continuation_parent(store, SPEC, ledger, CONTROL, development_mode=dev)
    assert "LINE_PRODUCT_CONTINUATION_CONTROL_CHANGED" in str(e.value)


def test_link_mission_uses_it():
    import inspect

    assert "continuation_parent(store, spec, ledger, control" in inspect.getsource(P.link_mission)
