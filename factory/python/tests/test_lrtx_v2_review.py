"""Feature 011 M4 (F011-T025..T027; F011-AT-019, AT-020, AT-022, AT-023): evidence-grounded SWE.1 inspection.

Typed claims about the frozen baseline are adjudicated by fixed rules: a claim the baseline contradicts is REFUTED,
a claim it proves is CONFIRMED, and a judgement the rules cannot decide STANDS. Claim identity ignores wording.
A FAIL made only of refuted claims gets one reinspection and is otherwise recorded as ADJUDICATED_PASS, with every
claim kept. The verdicts go through the unchanged check_inspection operation and inspect gate.
"""
from __future__ import annotations

import json

import pytest
from forge_factory.lrtx import review_semantic as RS
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe1_semantic as SEM
from test_lrtx_swe1 import _gate, _scripted
from test_lrtx_v2_swe1 import SEM_ANSWERS, iwdg, pytestmark  # noqa: F401 - answers, v2 IWDG work order, skip marker


@pytest.fixture()
def frozen(iwdg, monkeypatch):  # noqa: F811
    monkeypatch.setattr(S, "call", _scripted(SEM_ANSWERS, []))
    assert SEM.visit(iwdg, "qwen3-coder:30b")["status"] == "PASS"
    assert _gate(iwdg, monkeypatch) == 0  # the semantic SWE.1 baseline, frozen by the unchanged gate
    return iwdg


def _c(assertion, target, detail="a concrete observation about the document", related=()):
    return {"assertion": assertion, "target_id": target, "related_ids": list(related), "detail": detail,
            "remediation": "fix it"}


def test_baseline_facts_come_from_the_frozen_work_products_only(frozen):
    f = RS.baseline_facts(frozen)
    assert len(f["reqs"]) >= 9 and f["startup"] and all(f["budgets"].values())
    assert f["gap_rows"]["Safety allocation"] and f["gap_rows"]["Budgets"]
    assert f["traced"] and f["tested"]


def _budget(f, kind):
    return next(s for s, r in f["reqs"].items() if f"bytes of {kind}" in r["statement"])


def test_refutations_confirmations_and_judgements(frozen):
    f = RS.baseline_facts(frozen)
    swr = sorted(f["reqs"])[0]
    cases = [
        (_c("requirement_not_verifiable", swr), "REFUTED"),          # it states 'passes when ...'
        (_c("requirement_not_atomic", swr), "REFUTED"),              # exactly one 'shall'
        (_c("reset_startup_missing", "document"), "REFUTED"),        # the startup requirement exists
        (_c("safety_allocation_missing", "Safety allocation"), "REFUTED"),  # the owner's recorded gap
        (_c("budget_missing", "document"), "REFUTED"),
        (_c("requirement_untraceable", swr), "REFUTED"),
        (_c("requirement_not_verifiable", "SWR-999"), "REFUTED"),    # not a requirement of the baseline
        (_c("requirement_not_verifiable", "Safety allocation"), "REFUTED"),  # aimed at an input, not a requirement
        (_c("budget_not_measurable", _budget(f, "flash")), "REFUTED"),  # '4096 bytes' is a bound with a unit
        (_c("requirement_infeasible", _budget(f, "flash")), "REFUTED"),  # meeting a budget is measured later
        (_c("safe_state_missing", "document"), "REFUTED"),           # AT-020: the recorded PENDING allocation
        (_c("failure_handling_missing", "document"), "REFUTED"),     # ADR-0009: LL is register access, no waiting
        (_c("failure_handling_missing", "Safety allocation"), "REFUTED"),  # the owner's recorded gap
        (_c("safe_state_missing", swr), "STANDS"),                   # a claim about one requirement: a judgement
        (_c("failure_handling_missing", swr), "STANDS"),
        (_c("other", swr), "STANDS"),
    ]
    got = RS.adjudicate(frozen, "SWE1-02", [c for c, _ in cases], f)
    assert [g["decision"] for g in got] == [d for _, d in cases], [(g["assertion"], g["evidence"]) for g in got]


def test_a_requirement_without_pass_criterion_is_confirmed(frozen):
    md = frozen / "workproducts/SWE.1/software_requirements.md"
    swr = sorted(RS.baseline_facts(frozen)["reqs"])[0]
    text = md.read_text()
    first = text.index(f"**{swr}**")
    v = text.index("Verification:", first)
    end = text.index("\n", v)
    md.write_text(text[:v] + "Verification: inspected by review." + text[end:])
    got = RS.adjudicate(frozen, "SWE1-06", [_c("requirement_not_verifiable", swr)])
    assert got[0]["decision"] == "CONFIRMED"


def test_claim_identity_ignores_wording(frozen):
    a = _c("requirement_not_verifiable", "SWR-001", "the requirement has no measurable criterion at all")
    b = _c("requirement_not_verifiable", "SWR-001", "verification of SWR-001 is vague and cannot be checked")
    assert RS.identity("SWE1-06", a) == RS.identity("SWE1-06", b)
    assert RS.identity("SWE1-06", a) != RS.identity("SWE1-02", a)


def test_a_missing_mandatory_safety_input_is_never_refuted(frozen):
    """F011-AT-023: an ASIL target with owner safety document issues keeps a missing-allocation claim."""
    man = json.loads((frozen / ".forge-run/manifest.json").read_text())
    man["safety_target"] = "B"
    man["owner_safety_document_issues"] = ["software safety analysis: NOT_PROVIDED"]
    (frozen / ".forge-run/manifest.json").write_text(json.dumps(man))
    got = RS.adjudicate(frozen, "SWE1-01", [_c("safety_allocation_missing", "Safety allocation")])
    assert got[0]["decision"] == "STANDS"


def test_swe1_03_rules_keep_hal_failure_handling_and_missing_safety_inputs(frozen):
    """F011-T029 diagnostic (SWE1-03 false rejections of the owner-ruled clean LL baselines): the layer allocation
    refutes only an LL document-level claim, the recorded allocation only a safe-state claim; a HAL work order's
    failure handling, an unrecorded allocation and a missing mandatory ASIL input still stand."""
    path = frozen / ".forge-run/manifest.json"
    man = json.loads(path.read_text())
    assert man["layer"] == "LL"
    path.write_text(json.dumps({**man, "layer": "HAL"}))
    got = RS.adjudicate(frozen, "SWE1-03", [_c("failure_handling_missing", "document"),
                                            _c("safe_state_missing", "document")])
    assert [g["decision"] for g in got] == ["STANDS", "REFUTED"]
    gaps = frozen / "traceability/upstream_gaps.md"
    text = gaps.read_text()
    gaps.write_text("\n".join(x for x in text.splitlines() if not x.startswith("| Safety allocation |")))
    got = RS.adjudicate(frozen, "SWE1-03", [_c("safe_state_missing", "document")])
    assert got[0]["decision"] == "CONFIRMED"
    gaps.write_text(text)
    path.write_text(json.dumps({**man, "safety_target": "B",
                                "owner_safety_document_issues": ["software safety analysis: NOT_PROVIDED"]}))
    got = RS.adjudicate(frozen, "SWE1-03", [_c("safe_state_missing", "document"),
                                            _c("failure_handling_missing", "document")])
    assert [g["decision"] for g in got] == ["STANDS", "STANDS"]


def _inspector(verdicts):
    """A scripted inspector: verdicts[item] is a list of answers, one per call of that item."""
    seen: dict[str, int] = {}

    def call(p, **_k):
        item = p["task"].split(":")[-1]
        n = seen.get(item, 0)
        seen[item] = n + 1
        answers = verdicts.get(item, [{"verdict": "PASS", "claims": [], "evidence_checked": [
            "workproducts/SWE.1/software_requirements.md"]}])
        doc = answers[min(n, len(answers) - 1)]
        return {"doc": json.loads(json.dumps(doc)), "errors": S.validate(doc, p["output_schema"]),
                "usage": {"prompt_tokens": 1000, "completion_tokens": 100}, "wall_ms": 1.0, "finish_reason": "stop"}
    return call, seen


def test_a_clean_baseline_with_a_refuted_fail_is_adjudicated_pass_and_recorded(frozen, monkeypatch):
    """F011-AT-020: the clean baseline's PENDING/NOT_PROVIDED gap judged as a failure is refuted, not a rejection."""
    fail = {"verdict": "FAIL", "claims": [_c("safety_allocation_missing", "Safety allocation",
                                            "no software safety requirements are allocated")],
            "evidence_checked": ["traceability/upstream_gaps.md"]}
    call, seen = _inspector({"SWE1-01": [fail, fail]})
    monkeypatch.setattr(S, "call", call)
    rep = RS.visit(frozen, "SWE.1", "qwen3-coder:30b")
    assert rep["status"] == "PASS", rep
    assert seen["SWE1-01"] == 2  # one selective reinspection with the refutation
    rec = json.loads((frozen / ".forge-run/lrtx/SWE.1/inspection-record.json").read_text())
    assert rec["items"]["SWE1-01"]["outcome"] == "ADJUDICATED_PASS"
    assert rec["items"]["SWE1-01"]["rounds"][0]["claims"][0]["decision"] == "REFUTED"
    assert any(i.startswith("LRTX_ADJUDICATED_PASS:SWE1-01") for i in rep["issues"])


def test_a_real_defect_claim_stands_and_the_item_fails(frozen, monkeypatch):
    swr = sorted(RS.baseline_facts(frozen)["reqs"])[0]  # a claim about one requirement (document level: AT-020)
    claim = _c("safe_state_missing", swr, "the requirement states no safe state after a failed register write")
    fail = {"verdict": "FAIL", "claims": [claim], "evidence_checked": ["workproducts/SWE.1/software_requirements.md"]}
    call, seen = _inspector({"SWE1-03": [fail]})
    monkeypatch.setattr(S, "call", call)
    rep = RS.visit(frozen, "SWE.1", "qwen3-coder:30b")
    assert rep["status"] == "REWORK" and seen["SWE1-03"] == 1  # standing claims: no reinspection, a real FAIL
    rec = json.loads((frozen / ".forge-run/lrtx/SWE.1/inspection-record.json").read_text())
    assert rec["items"]["SWE1-03"]["outcome"] == "FAIL"


def test_a_pass_with_claims_or_a_fail_without_is_refused():
    assert RS.validate({"verdict": "PASS", "claims": [_c("other", "document")], "evidence_checked": ["a"]}, {"a"})
    assert RS.validate({"verdict": "FAIL", "claims": [], "evidence_checked": ["a"]}, {"a"})
    assert RS.validate({"verdict": "PASS", "claims": [], "evidence_checked": ["b"]}, {"a"})
