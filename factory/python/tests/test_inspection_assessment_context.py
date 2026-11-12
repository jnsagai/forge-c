"""Owner-scope input reaches both inspector paths without changing criteria or granting a verdict."""
import copy
import json

import pytest
from forge_factory.brownfield import resume
from forge_factory.common import pretty_json
from forge_factory.inspection import assessment_context as C
from forge_factory.inspection.engine import Store, load_checklist
from forge_factory.lrtx import review
from test_incremental_delivery import imported, prepared  # noqa: F401
from test_resume_from import _all_pass


def save(ws, manifest):
    (ws / ".forge-run/manifest.json").write_text(pretty_json(manifest))


def test_actual_preparation_exposes_same_bound_scope_to_native_and_structured_inspectors(prepared):  # noqa: F811
    ws, man = imported(prepared)
    st = Store(ws)
    baseline = st.latest_baseline("SWE.1")
    assert baseline
    original = load_checklist("SWE.1", brownfield=True)
    resolved = st.checklist("SWE.1")
    native = json.loads((ws / ".forge-run/checklists/SWE.1.json").read_text())
    _, sources = review.evidence(ws, "SWE.1")
    source = next(s for s in sources if s["path"].endswith("#inspection-assessment-context"))
    assert json.loads(source["text"]) == native["assessment_context"] == resolved["assessment_context"] == C.view(man)
    assert resolved["checks"] == original["checks"]  # Full frozen criteria, severity and required flags remain.
    assert resolved["policy"] == original["policy"]
    assert native["sha256"] == resolved["sha256"] != original["sha256"]
    before = resume.contract(man)
    other = copy.deepcopy(man)
    other[C.FIELD]["scope_sha256"] = "0" * 64
    assert resume.contract(other) != before


def test_performance_gap_still_fails_the_real_inspection_gate(prepared):  # noqa: F811
    ws, _ = imported(prepared)
    st = Store(ws)
    baseline = st.latest_baseline("SWE.1")
    verdicts = _all_pass("SWE.1")
    verdicts["SWE1-04"] = {"verdict": "FAIL", "evidence_refs": ["workproducts/SWE.1/software_requirements.md"],
                           "findings": ["Synthetic missing CPU and timing allocation"]}
    record = st.record_inspection("SWE.1", "swe1-inspector", baseline["baseline_id"], verdicts)
    assert record["verdict"] == "FAIL" and st.gate("SWE.1")["decision"] != "PASS"
    assert any(f["id"] == "SWE1-04" for f in record["findings"])


@pytest.mark.parametrize("field", ["purpose", "scope", C.FIELD])
def test_unbound_or_changed_assessment_context_refuses_before_inspection(prepared, field):  # noqa: F811
    ws, man = imported(prepared)
    man[field] = "FORGED_CONTEXT"
    save(ws, man)
    with pytest.raises(ValueError):
        Store(ws).checklist("SWE.1")
    with pytest.raises(ValueError):
        review.evidence(ws, "SWE.1")


def test_legacy_context_and_historical_checklist_identity_remain_unchanged(prepared):  # noqa: F811
    ws, man = imported(prepared)
    man.pop(C.FIELD)
    save(ws, man)
    assert C.view(man) is None and C.FIELD not in resume.contract(man)
    assert Store(ws).checklist("SWE.1") == load_checklist("SWE.1", brownfield=True)
    _, sources = review.evidence(ws, "SWE.1")
    assert not any(s["path"].endswith("#inspection-assessment-context") for s in sources)


def test_old_pass_is_not_reused_for_a_new_assessment_context(prepared):  # noqa: F811
    ws, man = imported(prepared)
    context = man.pop(C.FIELD)
    save(ws, man)
    st = Store(ws)
    baseline = st.latest_baseline("SWE.1")
    old = st.record_inspection("SWE.1", "swe1-inspector", baseline["baseline_id"], _all_pass("SWE.1"))
    assert old["verdict"] == "PASS" and st.gate("SWE.1")["decision"] == "PASS"
    man[C.FIELD] = context
    save(ws, man)
    assert st.gate("SWE.1")["decision"] == "REINSPECT"
    assert st.gate("SWE.1")["reason"] == "INSPECTION_ASSESSMENT_CONTEXT_CHANGED"
    assert st.inspections("SWE.1")[-1] == old  # History is untouched, including its old PASS.
