"""CAPA-085 (run WO-F014-SWE1-IWDG-20261101-02, Omniverse2, 2026-11-01): the structured inspector refused the frozen
SWE.1 baseline before any model call (SOURCE_TOO_LARGE) and the route re-inspected 166 times in 4 minutes. A refusal
that repeats unchanged with zero calls now blocks the route; failures after model calls keep re-inspection."""
from __future__ import annotations

import json

from forge_factory import development_execution as D
from forge_factory.inspection import gate
from forge_factory.inspection.engine import Store
from forge_factory.lrtx import review
from test_lrtx_swe1 import pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import ws1  # noqa: F401 - fixture


def _refuse(ws_, monkeypatch, n):
    monkeypatch.setattr(review, "source_char_limit", lambda _ws: 10)
    for _ in range(n):
        rep = review.visit(ws_, "SWE.1", "m")
        assert rep["status"] == "FAILED" and rep["issues"][0].startswith("SOURCE_TOO_LARGE:")


def test_a_repeated_zero_call_refusal_blocks_the_route(ws1, monkeypatch):  # noqa: F811
    _refuse(ws1, monkeypatch, 2)
    assert Store(ws1).gate("SWE.1")["decision"] == "REINSPECT"  # a transient refusal still gets re-inspected
    _refuse(ws1, monkeypatch, 1)
    g = Store(ws1).gate("SWE.1")
    assert g["decision"] == "BLOCKED" and g["reason"].startswith("INSPECTOR_REFUSED_REPEATEDLY:SOURCE_TOO_LARGE:")
    assert gate.step_route(Store(ws1), "SWE.1") == 1


def _rows(ws_, rows):
    p = ws_ / ".forge-run/lrtx/SWE.1/inspections.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_failures_after_model_calls_or_with_changing_issues_keep_reinspection(ws1):  # noqa: F811
    at = "9999-01-01T00:00:00Z"
    _rows(ws1, [{"at": at, "status": "FAILED", "calls": 5, "issues": ["LRTX_TIMEOUT"]}] * 4)
    assert Store(ws1).gate("SWE.1")["decision"] == "REINSPECT"
    _rows(ws1, [{"at": at, "status": "FAILED", "calls": 0, "issues": [f"X{i}"]} for i in range(4)])
    assert Store(ws1).gate("SWE.1")["decision"] == "REINSPECT"


def test_refusals_before_the_current_baseline_do_not_count(ws1):  # noqa: F811
    _rows(ws1, [{"at": "2000-01-01T00:00:00Z", "status": "FAILED", "calls": 0, "issues": ["SOURCE_TOO_LARGE:x"]}] * 5)
    assert Store(ws1).gate("SWE.1")["decision"] == "REINSPECT"


def test_the_high_allowance_ladder_does_not_override_the_refusal_block(ws1, monkeypatch):  # noqa: F811
    m = json.loads((ws1 / ".forge-run/manifest.json").read_text())
    m["purpose"] = "ASPICE_ONLY"
    m["development_execution"] = D.binding(D.HIGH, "ASPICE_ONLY")
    (ws1 / ".forge-run/manifest.json").write_text(json.dumps(m))
    assert D.selected(ws1) is not None
    _refuse(ws1, monkeypatch, 3)
    assert gate.step_route(Store(ws1), "SWE.1") == 1
    route = [json.loads(x) for x in (ws1 / ".forge-run/gates/gate-log.jsonl").read_text().splitlines()
             if '"step": "route"' in x][-1]
    assert route["gate"]["decision"] == "BLOCKED" and "INSPECTOR_REFUSED_REPEATEDLY" in route["gate"]["reason"]
