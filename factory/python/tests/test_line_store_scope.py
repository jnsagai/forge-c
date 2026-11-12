"""Role MCP/gateway processes resolve the same M3 database, never an arbitrary caller-supplied path."""
import os
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from forge_factory.afo.queue import Store, default_path, QueueError
from forge_factory.afo import local_agent as L
from test_line_recovery_executor import bound, local, order, prepare  # noqa: F401


def test_fixed_scope_preserves_legacy_and_routes_line_children_to_existing_store(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("FORGE_AFO_QUEUE_SCOPE", raising=False)
    assert default_path() == tmp_path / "conductor/conductor.sqlite3"
    monkeypatch.setenv("FORGE_AFO_QUEUE_SCOPE", "line-local")
    canonical = tmp_path / "supervisor/line-queue.sqlite3"
    with pytest.raises(QueueError, match="AUTHORITATIVE_DATABASE_UNAVAILABLE"):
        Store()
    assert not canonical.parent.exists()
    Store(canonical)  # Explicit M3 bootstrap; scoped role consumers only open an existing authority.
    assert Store().path == canonical
    for scope in ["cloud", "../../foreign", str(tmp_path / "other.db")]:
        monkeypatch.setenv("FORGE_AFO_QUEUE_SCOPE", scope)
        with pytest.raises(QueueError, match="SCOPE_INVALID"):
            default_path()


def test_bound_line_job_carries_fixed_scope_and_does_not_parse_campaign_as_json(bound):
    s, o, _, _, _, case, _, _ = bound
    path = case.parent / "campaign.yaml"
    path.write_text("schema: forge-c/line-campaign/1\n")
    o["input_manifest_ref"] = str(path)
    job = prepare(bound)
    assert job["native_context"]["FORGE_AFO_QUEUE_SCOPE"] == "line-local"
    assert L.execution_context(job)["FORGE_AFO_QUEUE_SCOPE"] == "line-local"


def test_gateway_advertises_its_actual_fixed_store_and_startup_source_only_when_scoped(tmp_path, monkeypatch):
    from forge_factory import llm_gateway, workorder

    monkeypatch.setattr(workorder, "factory_revision", lambda: {"commit": "a" * 40, "dirty": False})
    monkeypatch.delenv("FORGE_AFO_QUEUE_SCOPE", raising=False)
    with TestClient(llm_gateway.create_app("http://127.0.0.1:1", tmp_path / "usage-legacy")) as c:
        assert "afo_queue_scope" not in c.get("/health").json()
    monkeypatch.setenv("FORGE_AFO_QUEUE_SCOPE", "line-local")
    with TestClient(llm_gateway.create_app("http://127.0.0.1:1", tmp_path / "usage-line")) as c:
        h = c.get("/health").json()
        assert h["afo_queue_scope"] == "line-local" and h["factory_revision"]["commit"] == "a" * 40
