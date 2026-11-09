"""CAPA-203 (WO-F014-SWE1-WWDGL-20261109-L44E): the SWE.1 set inspection could not be recorded - check_inspection was
denied MISSION_NOT_REGISTERED because runner nodes lacked FORGE_AFO_QUEUE_SCOPE and the tool charge used the conductor
queue - and the denial looped REINSPECT/REWORK 30 times."""
# ruff: noqa: F811 - pytest fixtures imported from test_lrtx_swe1 / test_f018_phase2

import pytest
from forge_factory.workflow import builder
from test_f018_phase2 import frozen  # noqa: F401
from test_lrtx_swe1 import pytestmark, ws  # noqa: F401


@pytest.fixture()
def frozen_ws(frozen):  # noqa: F811
    return frozen


def test_runner_nodes_get_the_launchers_queue_scope(monkeypatch):
    monkeypatch.setenv("FORGE_AFO_QUEUE_SCOPE", "line-local")
    assert "FORGE_AFO_QUEUE_SCOPE=line-local" in builder._env()
    monkeypatch.delenv("FORGE_AFO_QUEUE_SCOPE")
    assert "FORGE_AFO_QUEUE_SCOPE" not in builder._env()  # other graphs are unchanged


def test_the_tool_charge_uses_the_line_queue_that_holds_the_order(tmp_path, monkeypatch):
    from forge_factory.afo import tool_accounting as T

    monkeypatch.delenv("FORGE_AFO_QUEUE_SCOPE", raising=False)
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path))
    (tmp_path / "supervisor").mkdir()
    (tmp_path / "supervisor/line-queue.sqlite3").write_bytes(b"")
    seen = {}

    class FakeStore:
        def __init__(self, path=None, must_exist=None):
            self.path = path

        def order(self, oid):
            return {"order_id": oid} if self.path is not None else None
    store = T._store_for({"order_id": "afo-1", "mission_id": "m", "job_id": "j"}, FakeStore)
    assert str(store.path).endswith("supervisor/line-queue.sqlite3")
    seen["default"] = T._store_for({"mission_id": "m", "job_id": "j"}, FakeStore).path
    assert seen["default"] is None  # no order id: the default queue, as before


def test_denied_record_reply(frozen_ws, monkeypatch):
    from forge_factory.lrtx import review, structured
    from forge_factory.lrtx import tools as T

    ws = frozen_ws

    def call(p, **_):
        doc = {"verdict": "PASS", "findings": [], "evidence_checked": ["workproducts/SWE.1/software_requirements.md"]}
        return {"doc": doc, "errors": [], "usage": None, "wall_ms": 0, "finish_reason": "stop"}
    monkeypatch.setattr(structured, "call", call)
    monkeypatch.setattr(T, "call", lambda *a, **k: {"status": "BLOCKED", "issues": ["MISSION_NOT_REGISTERED"],
                                                   "summary": "denied: MISSION_NOT_REGISTERED",
                                                   "metrics": {"handler_executed": False}, "artifact_refs": []})
    out = review.visit(ws, "SWE.1", "local-fixture", max_calls=400)
    assert out["status"] == "FAILED" and out["issues"][0].startswith("LRTX_INSPECTION_RECORD_DENIED:")
