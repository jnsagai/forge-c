"""Synthetic semantic answers exercise real reviewed import/inspection/counter boundaries."""
import json
import time

import pytest
from forge_factory import provided_requirements as P
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import Store as Queue
from forge_factory.inspection import gate
from forge_factory.inspection.engine import Store
from forge_factory.lrtx import review, review_semantic, structured
from test_incremental_delivery import prepared  # noqa: F401


@pytest.mark.parametrize("limit", [0, 1])
@pytest.mark.parametrize("semantic", [False, True])
def test_structured_inspection_receipt_consumes_mission_allowance_before_recording(
        prepared, monkeypatch, limit, semantic):  # noqa: F811
    ws, _ = prepared
    result = P.materialize(ws)  # Uses the original genuinely reviewed seven-requirement input.
    assert gate.step_author(Store(ws), "SWE.1", json.dumps(result)) == 0
    queue = Queue()
    ledger = MissionLedger(queue)
    ledger.register("inspection-fixture", "fixture:inspection", dict(max_attempts=1, max_jobs=0, max_requests=10,
                    max_tokens=1000, max_tools=limit, max_corrections=0, deadline=time.time() + 600),
                    "AUTH-SYNTHETIC-NOT-LIVE", authorize=lambda *a: True)
    ledger.execution("inspection-fixture", "fixture-native", "PRODUCT", reserved_tokens=100)
    (ws / ".forge-run/durable-binding.json").write_text(json.dumps(
        {"mission_id": "inspection-fixture", "job_id": "fixture-native"}))

    for option in ("coverage", "entries", "stepwise"):
        monkeypatch.setitem(review_semantic.INSPECTOR, option, False)

    def synthetic_semantic_verdict(packet, **_):
        return {"doc": {"verdict": "PASS", ("claims" if semantic else "findings"): [], "evidence_checked": [
            "workproducts/SWE.1/software_requirements.md"]},
            "errors": [], "usage": None, "wall_ms": 0, "finish_reason": "stop"}

    monkeypatch.setattr(structured, "call", synthetic_semantic_verdict)  # No Qwen or independent semantic claim.
    inspector = review_semantic if semantic else review
    outcome = inspector.visit(ws, "SWE.1", "local-fixture", max_calls=10)
    store = Store(ws)
    assert ledger.snapshot("inspection-fixture")["tools"] == limit
    if limit:
        assert outcome["status"] == "PASS" and len(store.inspections("SWE.1")) == 1
    else:
        assert outcome["status"] != "PASS" and store.inspections("SWE.1") == []
        assert store.gate("SWE.1")["decision"] == "REINSPECT"
        assert any("MISSION_MAX_TOOLS_EXHAUSTED" in issue for issue in outcome["issues"])
    record = json.loads((ws / "evidence/tool-results.jsonl").read_text().splitlines()[-1])
    assert record["op"] == "check_inspection"
    assert record["result"]["status"] == ("PASS" if limit else "BLOCKED")
