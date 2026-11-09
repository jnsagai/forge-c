"""Owner 2026-11-09: drivers are developed out of context, traceable to the reference manual.

"by now, it is not needed upstream requirementw for drivers, lets implement them as out of context" and "they should
be traceable to the reference manual".
"""
import json

from forge_factory import upstream as U
from forge_factory.lrtx import review, review_semantic
from forge_factory.workflow import prompts

DRAFT = {"status": "NOT_PROVIDED", "issues": ["NOT_APPROVED:status=DRAFT_TEMPLATE"], "data": None, "sha256": "s"}


def test_an_aspice_only_driver_without_approved_upstream_is_out_of_context_with_the_rm_as_baseline():
    up = U.out_of_context(DRAFT, layer="LL", purpose="ASPICE_ONLY")
    assert up["status"] == U.OUT_OF_CONTEXT and up["issues"] == []
    assert up["template_issues"] == DRAFT["issues"] and "reference manual" in up["context"]
    assert U.out_of_context(DRAFT, layer="HAL", purpose="QM")["status"] == U.OUT_OF_CONTEXT


def test_approved_upstream_safety_purposes_and_non_drivers_are_unchanged():
    approved = {**DRAFT, "status": "APPROVED", "issues": []}
    assert U.out_of_context(approved, layer="LL", purpose="ASPICE_ONLY") is approved
    for purpose in ("DEVELOPMENT", "FORMAL_REVIEW"):
        assert U.out_of_context(DRAFT, layer="LL", purpose=purpose) is DRAFT
    assert U.out_of_context(DRAFT, layer="APP", purpose="ASPICE_ONLY") is DRAFT


def _ws(tmp_path, status):
    (tmp_path / ".forge-run").mkdir()
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps({"upstream": {"status": status}}))
    return tmp_path


def test_the_inspector_judges_swe1_01_and_05_against_the_reference_manual_baseline(tmp_path, monkeypatch):
    monkeypatch.setattr("forge_factory.lrtx.c_language_context.for_workspace", lambda ws: None)
    ws = _ws(tmp_path, U.OUT_OF_CONTEXT)
    assert review.out_of_context(ws)
    for item in ("SWE1-01", "SWE1-05"):
        assert prompts.OUT_OF_CONTEXT_NOTE in review._notes(ws, "SWE.1", item)
    assert prompts.OUT_OF_CONTEXT_NOTE not in review._notes(ws, "SWE.1", "SWE1-02")
    assert "reference-manual section" in prompts.OUT_OF_CONTEXT_NOTE


def test_a_work_order_with_upstream_not_provided_gets_no_out_of_context_note(tmp_path, monkeypatch):
    monkeypatch.setattr("forge_factory.lrtx.c_language_context.for_workspace", lambda ws: None)
    ws = _ws(tmp_path, "NOT_PROVIDED")
    assert not review.out_of_context(ws)
    assert prompts.OUT_OF_CONTEXT_NOTE not in review._notes(ws, "SWE.1", "SWE1-01")


def test_an_objection_to_the_recorded_out_of_context_status_is_a_recorded_upstream_objection():
    assert review_semantic.RECORDED_UPSTREAM.search("upstream.status is OUT_OF_CONTEXT, no system requirements")
    assert review_semantic.RECORDED_UPSTREAM.search("the driver is developed out of context")
