"""Feature 020 round 3 (owner 2026-11-13 "go ahead with the round 3 fixes"; decision log D40), from the cloud control run
C04 set inspection (REWORK twice, 6 majors each):
- stale cross-references: requirements cited each other as 'SWR-025 [key]' and every reassembly renumbered the ids, so
  the cited id named another requirement -> cite by key; the assembly writes the current id in front; a bare id is
  refused (REFERENCE_BY_ID), an id whose key is unknown or moved is reported by the author gate;
- authoring-process text in requirements and open points ('needs a new key assigned by the task owner', 'is to be
  regenerated') -> AUTHOR_META_TEXT;
- the introduction said every requirement is mandatory while the budget requirements said 'not a release acceptance
  limit' -> the introduction states the work order's budget policy, budget requirements are measured
  (BUDGET_NOT_MEASURED otherwise).
Template v2 switches (references_by_key, no_author_meta_text, budget_verified_by_measurement); v1 orders unchanged.
Scripted answers only."""
from __future__ import annotations

import copy
import json

import pytest
from f020_swe1 import author
from forge_factory.lrtx import swe1_functional as F
from test_f020_template_v2 import answers_v2, ws  # noqa: F401 - the v2 SER fixture


def test_references_by_key_get_the_current_id_and_other_brackets_stay():
    idx = F.ref_index([{"key": "busy_refusal", "task": "requirements:state_behaviour", "swr": "SWR-015"},
                       {"key": "get_state", "task": "requirements:g_state", "swr": "SWR-007"},
                       {"key": "dup", "task": "requirements:a", "swr": "SWR-001"},
                       {"key": "dup", "task": "requirements:b", "swr": "SWR-002"}])
    text, miss = F.resolve_refs("as in SWR-099 [busy_refusal], [state_behaviour/busy_refusal], [get_state], bits [7:0], "
                                "[dup], [b/dup] and SWR-003 [gone_key].", idx)
    assert text == ("as in SWR-015 [busy_refusal], SWR-015 [state_behaviour/busy_refusal], SWR-007 [get_state], bits "
                    "[7:0], [dup], SWR-002 [b/dup] and SWR-003 [gone_key].")
    assert miss == ["gone_key"]  # a key used twice resolves only with its task; an unknown key keeps its text


def _ctx(ws):  # noqa: F811
    return F.context(ws)


def test_bare_ids_meta_text_and_unmeasured_budgets_are_author_findings(ws):  # noqa: F811
    ctx = _ctx(ws)
    tid = "requirements:g_state"
    task = {t["id"]: t for t in F.plan(ws)}[tid]
    good = copy.deepcopy(answers_v2(ws)[tid]["requirements"][0])
    assert F.requirement_findings(good, task["origins"], ctx) == []

    def rules_of(r):
        return {rule for rule, _ in F.requirement_findings(r, task["origins"], ctx)}

    bare = dict(good, statement=good["statement"].replace("current state", "current state as SWR-012 defines"))
    assert "REFERENCE_BY_ID" in rules_of(bare)
    keyed = dict(good, statement=good["statement"].replace("current state", "current state as [busy_refusal] defines"))
    assert "REFERENCE_BY_ID" not in rules_of(keyed)
    meta = dict(good, precondition="Open point (IQ-05 split): needs a new key assigned by the task owner")
    assert "AUTHOR_META_TEXT" in rules_of(meta)
    budget = dict(good, statement="When HAL_SER_GetState is called, the SER HAL driver shall return within 2000 "
                  "instructions.", verification_method="inspection", test_level="not_testable")
    assert "BUDGET_NOT_MEASURED" in rules_of(budget)
    assert "BUDGET_NOT_MEASURED" not in rules_of(dict(budget, verification_method="analysis"))
    doc = {"requirements": [good], "open_points": ["The consolidated workproduct is to be regenerated."]}
    assert any("[open_point 1] AUTHOR_META_TEXT" in f for f in F.validate_task(ws, doc, task, ctx))


def _with_reference(ws, ref: str):  # noqa: F811
    a = answers_v2(ws)
    r = a["requirements:g_state"]["requirements"][0]
    r["statement"] = r["statement"].replace("the current state of the handle",
                                            f"the current state of the handle, including the busy state of {ref}")
    return a


def test_the_assembly_writes_the_current_id_and_the_gate_passes(ws, monkeypatch):  # noqa: F811
    rep, _ = author(ws, monkeypatch, _with_reference(ws, "SWR-001 [state_behaviour/busy_refusal]"))
    assert rep["status"] == "PASS", rep
    attrs = json.loads((ws / F.ATTRS).read_text())
    swr = next(r["id"] for r in attrs["requirements"] if r["key"] == "busy_refusal")
    st = next(r["statement"] for r in attrs["requirements"] if r["key"] == "get_state")
    assert f"{swr} [state_behaviour/busy_refusal]" in st and swr != "SWR-001"
    assert f"{swr} [state_behaviour/busy_refusal]" in (ws / F.REQS).read_text()
    from forge_factory.assurance import swe1_functional_checks as FC

    assert FC.findings(ws) == []
    rec = json.loads((ws / ".forge-run/lrtx/SWE.1/assembly.json").read_text())
    assert rec["unresolved_references"] == {}


def test_an_unknown_key_reference_fails_the_author_gate(ws, monkeypatch):  # noqa: F811
    from forge_factory.assurance import swe1_functional_checks as FC

    rep, _ = author(ws, monkeypatch, _with_reference(ws, "SWR-001 [gone_key]"))
    assert rep["status"] == "FAILED"  # the scripted author repeats itself: the repair is refused as stuck
    found = [f for f in FC.findings(ws) if "REFERENCE_UNKNOWN" in f]
    assert len(found) == 1 and "[get_state]" in found[0] and "[gone_key]" in found[0]
    assert found[0].count("SWR-") == 1  # only the requirement's own id: the finding routes to its own task
    assert not any("requirements:g_initialisation" in i for i in rep["issues"]), rep["issues"]


def test_the_introduction_states_the_budget_policy(ws, monkeypatch):  # noqa: F811
    m = json.loads((ws / ".forge-run/manifest.json").read_text())
    if not m.get("budgets"):
        pytest.skip("the SER fixture order has no budgets")
    rep, _ = author(ws, monkeypatch, answers_v2(ws))
    assert rep["status"] == "PASS", rep
    md = (ws / F.REQS).read_text()
    assert "Work-order budgets (" in md and "verified by measurement" in md and "none is optional or deferred" in md
