"""CAPA-076 (owner option A, 2026-10-31): an inspector answer rejected as "PASS with findings" and repaired into a clean
PASS kept no trace of the findings it dropped (standalone SWE.1 run, SWE1-01/SWE1-03). The rejected findings are now
kept in the task checkpoint and reported as withdrawn_in_repair; the verdict and the gate are unchanged."""
import json

from forge_factory import provided_requirements as P
from forge_factory.inspection import gate
from forge_factory.inspection.engine import Store
from forge_factory.lrtx import review, structured
from test_incremental_delivery import prepared  # noqa: F401

FINDING = "SWR-001 states the write but not that the other CRC registers are preserved."
EVIDENCE = ["workproducts/SWE.1/software_requirements.md"]


def _scripted(repair_keeps):
    def call(packet, **_):
        repairing = bool(packet.get("findings"))
        if not repairing:
            doc = {"verdict": "PASS", "findings": [FINDING], "evidence_checked": EVIDENCE}
        elif repair_keeps:
            doc = {"verdict": "FAIL", "findings": [FINDING], "evidence_checked": EVIDENCE}
        else:
            doc = {"verdict": "PASS", "findings": [], "evidence_checked": EVIDENCE}
        return {"doc": doc, "errors": [], "usage": None, "wall_ms": 0, "finish_reason": "stop"}
    return call


def _frozen(ws):
    result = P.materialize(ws)
    assert gate.step_author(Store(ws), "SWE.1", json.dumps(result)) == 0


def test_findings_dropped_in_repair_are_recorded_as_withdrawn(prepared, monkeypatch):  # noqa: F811
    ws, _ = prepared
    _frozen(ws)
    monkeypatch.setattr(structured, "call", _scripted(repair_keeps=False))
    outcome = review.visit(ws, "SWE.1", "local-fixture", max_calls=40)
    assert outcome["status"] == "PASS"  # option A: no verdict or gate change
    record = json.loads((ws / ".forge-run/lrtx/SWE.1/inspection-record.json").read_text())
    withdrawn = record["withdrawn_in_repair"]
    assert withdrawn and all(v == [FINDING] for v in withdrawn.values())
    assert set(withdrawn) == set(record["items"])
    assert any(i.startswith("LRTX_INSPECTOR_FINDING_WITHDRAWN_IN_REPAIR:") for i in outcome["issues"])
    ck = next((ws / ".forge-run/lrtx/SWE.1/packets").glob("inspect__*.json"))
    first = json.loads(ck.read_text())["attempts"][0]
    assert first["rejected_findings"] == [FINDING] and first["errors"]


def test_findings_kept_by_a_fail_are_not_reported_as_withdrawn(prepared, monkeypatch):  # noqa: F811
    ws, _ = prepared
    _frozen(ws)
    monkeypatch.setattr(structured, "call", _scripted(repair_keeps=True))
    outcome = review.visit(ws, "SWE.1", "local-fixture", max_calls=40)
    assert outcome["status"] == "REWORK"
    record = json.loads((ws / ".forge-run/lrtx/SWE.1/inspection-record.json").read_text())
    assert record["withdrawn_in_repair"] == {}
    assert not any("WITHDRAWN_IN_REPAIR" in i for i in outcome["issues"])
