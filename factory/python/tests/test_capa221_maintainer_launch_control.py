"""CAPA-221 (owner lane, 2026-11-08 L40G/L41E/L43D): every factory-maintainer job ended
NATIVE_LAUNCH_NOT_STARTED:OWNER_DEVELOPMENT_CONTROL_SCOPE_CHANGED and its order MAINTENANCE_BLOCKED. The maintainer
branch of line_recovery_runtime.authorize checked the native transport with a control derived WITHOUT the order's
request, so the owner-development permit saw order_id None. It now derives the control for this order, like every other
native caller (line_recovery_product.bind_native)."""
import types

import pytest

from forge_factory.afo import line_recovery_control as C
from forge_factory.afo import line_recovery_runtime as RT


class Stop(Exception):
    pass


def test_maintainer_launch_checks_transport_with_the_orders_control(monkeypatch, tmp_path):
    from forge_factory.afo import execution_lifecycle, local_agent, mission_ledger, operations, policy

    order = {"order_id": "afo-1", "request_id": "WO-X"}
    eff = types.SimpleNamespace(sha256="p" * 64, mode="OWNER_SUPERVISED_DEVELOPMENT")
    job = {"job_id": "afo-agent-1", "order_id": "afo-1", "role": "afo-factory-maintainer", "durable_native": "maintenance-1",
           "line_origin": {"policy_path": None}, "policy_sha256": eff.sha256, "state": "LAUNCHING", "deadline_epoch": 4e9,
           "native_context": {"FORGE_OPERATIONS_INTENT": str(tmp_path / "intent.json")}, "operations_epoch": 3,
           "mission_id": "m", "nonce": "n", "line_role_authority_ref": "ctl-ref"}
    monkeypatch.setattr(policy, "load", lambda: eff)
    monkeypatch.setattr(local_agent, "enabled", lambda role, e: True)
    monkeypatch.setattr(local_agent, "authorized_job", lambda o, e, j: True)
    monkeypatch.setattr(local_agent, "request_for", lambda o: {"order_id": o["order_id"], "driver_class": "D", "model": "M"})
    monkeypatch.setattr(operations, "Intent", lambda p: types.SimpleNamespace(read=lambda: {"mode": "RUNNING", "epoch": 3}))
    monkeypatch.setattr(mission_ledger, "MissionLedger",
                        lambda s: types.SimpleNamespace(snapshot=lambda m: {"limits": {"deadline": 4e9}}))
    monkeypatch.setattr(execution_lifecycle, "Executions", lambda s: types.SimpleNamespace(get=lambda j: {
        "authorization_state": "VALID", "resource_lease": "HELD", "mission_id": "m", "launch_nonce": "n"}))
    seen = {}

    def configuration(ref, e, *, request=None):
        seen["configuration"] = (ref, request)
        return {"native_transport_ref": "t"}

    def transport(j, *, cfg=None, control=None):
        seen["control"] = control
        raise Stop

    monkeypatch.setattr(C, "configuration", configuration)
    monkeypatch.setattr(C, "require_native_transport", transport)
    store = types.SimpleNamespace(order=lambda oid: order)
    with pytest.raises(Stop):
        RT.authorize(job, store=store)
    assert seen["control"] == {"native_transport_ref": "t"}
    assert seen["configuration"] == ("ctl-ref", {"order_id": "afo-1", "driver_class": "D", "model": "M"})


def test_a_maintainer_job_without_authority_ref_still_refuses():
    import inspect

    src = inspect.getsource(RT.authorize)
    assert "request=L.request_for(order)" in src and "if ref else None" in src
