"""Transport prerequisite controls only; the fake validator is never live ABI/role proof."""

import sys
from types import SimpleNamespace

import pytest
from forge_factory.afo import line_recovery_control as C
from forge_factory.afo.durable import Refused


def test_source_eligibility_without_measured_transport_always_refuses(monkeypatch):
    monkeypatch.setenv("FORGE_DURABLE_NATIVE_HEADER", "1")
    with pytest.raises(Refused, match="MEASUREMENT_REQUIRED"):
        C.require_native_transport({}, control={})


def test_signed_reference_cannot_enable_operator_native_header_flag(monkeypatch):
    monkeypatch.delenv("FORGE_DURABLE_NATIVE_HEADER", raising=False)
    with pytest.raises(Refused, match="OPT_IN_REQUIRED"):
        C.require_native_transport({}, control={"native_transport_ref": {"fixture": True}})


def test_actual_validator_owns_binary_profile_source_validation(monkeypatch):
    calls = []

    def require(ref, *, job, cfg):
        calls.append((ref, job, cfg))
        raise Refused("CONTROL_CHANGED_EXECUTING_BINARY")

    monkeypatch.setenv("FORGE_DURABLE_NATIVE_HEADER", "1")
    monkeypatch.setitem(sys.modules, "forge_factory.afo.line_native_transport", SimpleNamespace(require=require))
    job = {"job_id": "CONTROL"}
    cfg = object()
    ref = {"fixture": "not-a-proof"}
    with pytest.raises(Refused, match="CHANGED_EXECUTING_BINARY"):
        C.require_native_transport(job, cfg=cfg, control={"native_transport_ref": ref})
    assert calls == [(ref, job, cfg)]


def test_legacy_gateway_health_does_not_claim_scoped_native_enablement(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from forge_factory import llm_gateway as G

    monkeypatch.delenv("FORGE_AFO_QUEUE_SCOPE", raising=False)
    monkeypatch.setenv("FORGE_DURABLE_NATIVE_HEADER", "1")
    with TestClient(G.create_app("http://127.0.0.1:1", tmp_path / "usage.jsonl")) as client:
        assert "durable_native_header" not in client.get("/health").json()
