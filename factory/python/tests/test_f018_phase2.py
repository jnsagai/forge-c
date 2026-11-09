"""Feature 018 phase 2: the complete set - SWE1-01..08 stay the gate, SQ-01..10 are judged first and their actionable
findings (and phase 1's carried findings) reach the checklist item they belong to (owner 2026-11-09)."""
# ruff: noqa: F811 - pytest fixtures imported from test_lrtx_swe1
import json

import pytest
from forge_factory.lrtx import review, structured, swe1
from forge_factory.lrtx import swe1_quality as Q
from test_lrtx_swe1 import ANSWERS, _gate, _scripted, pytestmark, ws  # noqa: F401

EVIDENCE = ["workproducts/SWE.1/software_requirements.md"]
GAP = "no requirement covers CRC_CR.REV_OUT although the scope names it"


def _text(p):
    return " ".join(m["content"] for m in p["_messages"])


@pytest.fixture()
def frozen(ws, monkeypatch):  # noqa: F811
    monkeypatch.setattr(structured, "call", _scripted(ANSWERS, []))
    assert swe1.visit(ws, "qwen3-coder:30b")["status"] == "PASS"
    assert _gate(ws, monkeypatch) == 0  # frozen by the unchanged SWE.1 author gate
    return ws


def _model(calls, sq_findings=None, fail_items=()):
    def call(p, **_):
        calls.append(p)
        item = p["task"].split(":", 1)[1]
        if item.startswith("SQ-"):
            doc = {"findings": (sq_findings or {}).get(item, []), "evidence_checked": EVIDENCE}
        elif item in fail_items and "QUALITY FINDINGS FOR THIS ITEM" in _text(p):
            doc = {"verdict": "FAIL", "findings": [f"SWR-001: {GAP}"], "evidence_checked": EVIDENCE}
        else:
            doc = {"verdict": "PASS", "findings": [], "evidence_checked": EVIDENCE}
        return {"doc": doc, "errors": [], "usage": None, "wall_ms": 0, "finish_reason": "stop"}
    return call


def _sq(sev="CORRECTABLE", unc=False):
    return [{"requirement_id": "SET", "severity": sev, "evidence": GAP, "required_action": "add the requirement",
             "input_uncertainty": unc}]


def test_set_quality_is_judged_before_the_gate_items_and_routes_to_its_item(frozen, monkeypatch):
    ws = frozen
    monkeypatch.setattr(review, "two_phase", lambda _ws: True)
    calls = []
    monkeypatch.setattr(structured, "call", _model(calls, {"SQ-01": _sq()}, fail_items=("SWE1-05",)))
    out = review.visit(ws, "SWE.1", "local-fixture", max_calls=400)
    tasks = [p["task"] for p in calls]
    assert tasks[:10] == [f"inspect:SQ-{n:02d}" for n in range(1, 11)]  # the set criteria first
    assert all(p["role"] == "swe1-inspector" for p in calls)
    swe1_05 = next(p for p in calls if p["task"] == "inspect:SWE1-05")
    assert GAP in _text(swe1_05) and "QUALITY FINDINGS FOR THIS ITEM" in _text(swe1_05)
    assert "QUALITY FINDINGS" not in _text(next(p for p in calls if p["task"] == "inspect:SWE1-04"))
    assert out["status"] == "REWORK"  # the item that received the finding failed: the existing rework path
    rec = json.loads((ws / ".forge-run/lrtx/SWE.1/inspection-record.json").read_text())
    assert rec["set_quality"]["SQ-01"][0]["evidence"] == GAP and "SWE1-05" in rec["quality_to_items"]
    assert set(rec["items"]) == {"SWE1-01", "SWE1-02", "SWE1-03", "SWE1-04", "SWE1-05", "SWE1-06"}  # gate unchanged


def test_editorial_na_and_input_uncertainty_findings_are_recorded_not_routed(frozen, monkeypatch):
    ws = frozen
    monkeypatch.setattr(review, "two_phase", lambda _ws: True)
    calls = []
    na = [{"requirement_id": "SET", "severity": "N/A", "evidence": "no operating modes in scope", "required_action": "",
           "input_uncertainty": False}]
    monkeypatch.setattr(structured, "call", _model(calls, {"SQ-02": na, "SQ-03": _sq("EDITORIAL"),
                                                         "SQ-01": _sq(unc=True)}, fail_items=("SWE1-05",)))
    out = review.visit(ws, "SWE.1", "local-fixture", max_calls=400)
    assert out["status"] == "PASS"
    assert not any("QUALITY FINDINGS" in _text(p) for p in calls if not p["task"].startswith("inspect:SQ"))
    rec = json.loads((ws / ".forge-run/lrtx/SWE.1/phase2/set-quality.json").read_text())
    assert rec["findings"]["SQ-02"] == na and rec["to_items"] == {}


def test_carried_phase1_findings_reach_swe1_02(frozen, monkeypatch):
    ws = frozen
    monkeypatch.setattr(review, "two_phase", lambda _ws: True)
    carried = {"requirement_id": "SWR-002", "quality_id": "IQ-05", "severity": "CORRECTABLE",
               "evidence": "two obligations in one statement", "required_action": "split", "input_uncertainty": False}
    structured.record(ws, Q.SUMMARY, {"carried_findings": [carried]})
    calls = []
    monkeypatch.setattr(structured, "call", _model(calls))
    review.visit(ws, "SWE.1", "local-fixture", max_calls=400)
    p02 = next(p for p in calls if p["task"] == "inspect:SWE1-02")
    assert "IQ-05 CORRECTABLE SWR-002" in _text(p02) and "kept after its per-requirement rework" in _text(p02)
    sq = next(p for p in calls if p["task"] == "inspect:SQ-01")
    assert any(s["path"] == review.PHASE1_SOURCE for s in sq["sources"])


def test_a_resumed_inspection_repeats_no_set_quality_call(frozen, monkeypatch):
    ws = frozen
    monkeypatch.setattr(review, "two_phase", lambda _ws: True)
    calls = []
    monkeypatch.setattr(structured, "call", _model(calls))
    review.visit(ws, "SWE.1", "local-fixture", max_calls=400)
    calls.clear()
    review.visit(ws, "SWE.1", "local-fixture", max_calls=400)
    assert calls == []  # every SQ and item verdict is checkpointed on the baseline hash


def test_without_two_phase_the_inspection_is_unchanged(frozen, monkeypatch):
    ws = frozen
    calls = []
    monkeypatch.setattr(structured, "call", _model(calls))
    review.visit(ws, "SWE.1", "local-fixture", max_calls=400)
    assert not any(p["task"].startswith("inspect:SQ") for p in calls)
    assert not any("QUALITY FINDINGS" in _text(p) for p in calls)


def test_the_owner_report_lists_both_phases(frozen, monkeypatch):
    ws = frozen
    monkeypatch.setattr(review, "two_phase", lambda _ws: True)
    monkeypatch.setattr(structured, "call", _model([], {"SQ-01": _sq()}, fail_items=("SWE1-05",)))
    review.visit(ws, "SWE.1", "local-fixture", max_calls=400)
    text = (ws / ".forge-run/lrtx" / Q.REPORT).read_text()
    assert "## Phase 2 - the complete set" in text and "| SQ-01 | 1 (CORRECTABLE) | SWE1-05 |" in text
    assert "prompt" not in text.lower()
