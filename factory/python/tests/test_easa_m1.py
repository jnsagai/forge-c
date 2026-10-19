"""EASA M1: normative authority, method catalog, applicability, profiles/policy/modes, scope, capability."""
import copy

import pytest
from forge_factory.assurance import applicability, capability, catalog, contracts, normative, policy, scope
from forge_factory.assurance.store import AssuranceStore

WO = "WO-0002B-STM32N6-RCC-HAL-r102"


@pytest.fixture
def store(tmp_path):
    return AssuranceStore(tmp_path / "db.sqlite3")


@pytest.fixture
def cat():
    return catalog.load()


def scope_b(**kw):
    s = {"scope_id": "SC-1", "work_order_id": WO, "target_asil": "B", "source_requirements_hash": "a" * 64,
         "hsi_hash": "b" * 64, "allocation_review_ref": "TSR-review-17", "product_asil_source": "approved:TSC-4.2"}
    s.update(kw)
    return s


# ---- T008 / AT-008 / AT-070: catalog --------------------------------------------------------------------------
def test_at008_authored_working_index_is_valid_and_unverified(cat):
    assert catalog.validate(cat) == []
    assert len(cat["methods"]) == 47 and catalog.status(cat) == "UNVERIFIED"
    assert len(catalog.digest(cat)) == 64


def test_at070_46_entries_fail_with_missing_identifier_and_table_count(cat):
    bad = copy.deepcopy(cat)
    gone = bad["methods"].pop(20)
    issues = catalog.validate(bad)
    assert "CATALOG_COUNT_MISMATCH:46!=47" in issues
    assert f"MISSING_METHOD_ID:{gone['method_id']}" in issues
    assert any(i.startswith(f"TABLE_COUNT_MISMATCH:T{gone['table']}:") for i in issues)


def test_catalog_rejects_duplicates_table12_and_presented_as_checked(cat):
    bad = copy.deepcopy(cat)
    bad["methods"][1]["method_id"] = bad["methods"][0]["method_id"]
    bad["methods"][2]["normative_checked"] = True
    next(x for x in bad["table_inventory"] if x["table"] == 12)["asil_b_highly_recommended_count"] = 1
    issues = catalog.validate(bad)
    assert any(i.startswith("DUPLICATE_METHOD_ID") for i in issues)
    assert any(i.startswith("UNRECONCILED_ENTRY_PRESENTED_AS_CHECKED") for i in issues)
    assert "TABLE12_HAS_B_PLUS_PLUS" in issues


# ---- T002 / AT-002 / AT-083: normative authority ----------------------------------------------------------------
def test_at002_no_licensed_copy_keeps_catalog_provisional(monkeypatch, cat):
    monkeypatch.delenv(normative.ENV, raising=False)
    acc = normative.standard_access()
    assert acc["licensed_copy"] == "NOT_AVAILABLE" and acc["normative_verification"] == "BLOCKED"
    assert catalog.status(cat) == "UNVERIFIED"


def test_at083_unreviewed_catalog_with_compliance_request_rejected(cat):
    r = normative.assert_normative_claim(cat, "The driver is ISO 26262 compliant for ASIL B.")
    assert r["decision"] == "REJECTED"
    assert "COMPLIANCE_CLAIM_NOT_PERMITTED" in r["issues"] and r["issues"][0].startswith("NORMATIVE_UNVERIFIED")
    ok = normative.assert_normative_claim(cat, "Bounded engineering evidence for review.")
    assert ok["decision"] == "REJECTED" and len(ok["issues"]) == 1    # still unverified catalog


def test_licensed_copy_inside_repo_is_refused(monkeypatch):
    monkeypatch.setenv(normative.ENV, str(contracts.CATALOG))
    assert normative.standard_access()["licensed_copy"] == "REJECTED_IN_REPOSITORY"


# ---- T009 / AT-009: reconciliation -------------------------------------------------------------------------------
def _rows(cat, table, b="++"):
    return {m["method_id"]: {"A": "+", "B": b, "C": "++", "D": "++"} for m in cat["methods"] if m["table"] == table}


def test_at009_rating_change_without_source_rejected_and_recorded(store, cat, monkeypatch):
    monkeypatch.delenv(normative.ENV, raising=False)
    rec = catalog.change_rating_without_source(cat, "ISO6-T09-1B", "B", "+", store=store)
    assert rec["decision"] == "REJECTED"
    new, dec = catalog.reconcile(cat, {"table": 9, "edition": "ISO 26262-6:2018", "licensed_source_sha256": "x" * 64,
                                       "reviewer_id": "j.doe", "reviewer_competence_ref": "FSM-cert-1",
                                       "rows": _rows(cat, 9, "+")}, store=store)
    assert new is None and dec["issues"][0].startswith("LICENSED_SOURCE_UNAVAILABLE")
    assert len(store.history("reconciliation")) == 2


def test_reconciliation_with_registered_source_and_reviewer(store, cat, monkeypatch, tmp_path):
    lic = tmp_path / "iso26262-6-2018.pdf"
    lic.write_bytes(b"licensed copy bytes")
    monkeypatch.setenv(normative.ENV, str(lic))
    sha = normative.standard_access()["sha256"]
    base = {"edition": "ISO 26262-6:2018", "licensed_source_sha256": sha, "reviewer_id": "j.doe",
            "reviewer_competence_ref": "FSM-cert-1"}
    _, d1 = catalog.reconcile(cat, {**base, "reviewer_id": "agent-swe4", "table": 9, "rows": _rows(cat, 9)})
    assert "REVIEWER_IS_AGENT" in d1["issues"]
    _, d2 = catalog.reconcile(cat, {**base, "table": 9, "rows": dict(list(_rows(cat, 9).items())[:1])})
    assert any(i.startswith("PARTIAL_TABLE_REVIEW") for i in d2["issues"])
    new, d3 = catalog.reconcile(cat, {**base, "table": 9, "rows": _rows(cat, 9, "+")}, store=store)
    assert d3["decision"] == "ACCEPTED" and new["document_status"] == "PARTIALLY_RECONCILED"
    t9 = [m for m in new["methods"] if m["table"] == 9]
    assert all(m["normative_checked"] and m["asil_recommendations"]["B"] == "+" for m in t9)
    assert cat["methods"][0]["normative_checked"] is False        # authored catalog untouched
    assert catalog.status(new) == "UNVERIFIED"                    # other tables still unreconciled


# ---- T010 / T015 / AT-010 / AT-011: applicability ---------------------------------------------------------------
def test_applicability_alternatives_and_rationale_rules(store, cat):
    base = {"work_order_id": WO, "rationale": "", "alternative_method_ref": None, "source_version": "0.1.0",
            "reviewer_ref": None}
    got = applicability.check({**base, "method_id": "ISO6-T13-1A", "decision": "NOT_APPLICABLE_WITH_RATIONALE"}, cat)
    assert {"RATIONALE_REQUIRED:NOT_APPLICABLE_WITH_RATIONALE", "HUMAN_REVIEWER_REQUIRED"} <= set(got)
    assert any(g.startswith("rationale:") for g in got)              # the authored schema also rejects it
    alt = {**base, "method_id": "ISO6-T02-1A", "decision": "ALTERNATIVE_SELECTED",
           "rationale": "informal notation chosen for the RCC driver architecture", "reviewer_ref": "j.doe"}
    assert applicability.check({**alt, "alternative_method_ref": "ISO6-T03-1A"}, cat) == ["ALTERNATIVE_NOT_IN_SAME_TABLE"]
    assert applicability.check({**alt, "alternative_method_ref": "ISO6-T02-1B"}, cat) == []
    assert "UNKNOWN_METHOD:ISO6-T99-9Z" in applicability.check({**base, "method_id": "ISO6-T99-9Z", "decision": "UNKNOWN"}, cat)
    assert applicability.check({**base, "method_id": "ISO6-T09-1A", "decision": "MAYBE"}, cat)


def test_applicability_record_supersede_and_coverage(store, cat):
    d = {"work_order_id": WO, "method_id": "ISO6-T13-1A", "decision": "NOT_SUPPORTED",
         "rationale": "no hardware-in-the-loop rig is registered for this project",
         "alternative_method_ref": None, "source_version": "0.1.0", "reviewer_ref": None}
    rid, issues = applicability.record(store, d, cat)
    assert rid and not issues
    assert applicability.record(store, {**d, "decision": "UNKNOWN"}, cat) == (None, ["DECISION_EXISTS_SUPERSEDE_EXPLICITLY"])
    na = {**d, "decision": "NOT_APPLICABLE_WITH_RATIONALE", "reviewer_ref": "j.doe",
          "rationale": "QM work order without a target-environment test objective"}
    rid2, _ = applicability.record(store, na, cat, supersedes=rid)
    cov = applicability.coverage(store, WO, cat)
    assert cov["total"] == 47 and cov["methods"]["ISO6-T13-1A"] == "NOT_APPLICABLE_WITH_RATIONALE"
    assert cov["counts"]["UNKNOWN"] == 46
    assert store.first_pass("applicability", f"{WO}:ISO6-T13-1A")["record"]["decision"] == "NOT_SUPPORTED"


def test_at011_hil_na_only_by_policy_and_missing_evidence_blocks():
    dec = {"ISO6-T13-1A": "NOT_APPLICABLE_WITH_RATIONALE"}
    assert applicability.gate_view(dec, {}, set())["issues"] == ["NA_NOT_ALLOWED_BY_POLICY:ISO6-T13-1A"]
    assert applicability.gate_view(dec, {}, {"ISO6-T13-1A"})["state"] == "PASS"
    assert applicability.gate_view({"ISO6-T13-1A": "APPLICABLE"}, {}, {"ISO6-T13-1A"})["issues"] == [
        "EVIDENCE_MISSING:ISO6-T13-1A"]


def test_at010_profiles_change_requirements_never_asil():
    pol = contracts.load(contracts.POLICY_EXAMPLE)
    s = scope_b()
    effs = {p: policy.effective(dict(pol, profile=p), s) for p in policy.PROFILES}
    assert {e["target_asil"] for e in effs.values()} == {"B"}
    std, enh, high = (effs[p]["requirements"] for p in policy.PROFILES)
    for ph in std:
        assert set(std[ph]) < set(enh[ph]) < set(high[ph])
    assert "SELECTED_MCDC" in high["SWE.4"] and "SELECTED_MCDC" not in enh["SWE.4"]


# ---- T013 / AT-013 / AT-067: policy pinning, reload, modes ------------------------------------------------------
def test_at013_policy_validation_pinning_and_safe_reload(store, tmp_path):
    import yaml

    pol = contracts.load(contracts.POLICY_EXAMPLE)
    assert policy.validate(pol) == []
    assert "MODE_WITHOUT_HUMAN_AUTHORIZATION" in policy.validate(dict(pol, mode="PILOT"))
    p = tmp_path / "assurance-policy.yaml"
    p.write_text(yaml.safe_dump(dict(pol, profile="HIGH_ASSURANCE")))
    h = policy.PolicyHolder(store, p)
    assert h.source == "builtin-default"                       # not approved -> previous (default) stays
    assert h.reload()[1] == ["POLICY_NOT_APPROVED"]
    with pytest.raises(PermissionError):
        policy.approve(store, dict(pol, profile="HIGH_ASSURANCE"), "agent-swe3")
    policy.approve(store, dict(pol, profile="HIGH_ASSURANCE"), "j.doe")
    assert h.reload() == (True, []) and h.active["profile"] == "HIGH_ASSURANCE"
    p.write_text("mode: [unclosed")
    ok, issues = h.reload()
    assert not ok and issues[0].startswith("POLICY_UNREADABLE") and h.active["profile"] == "HIGH_ASSURANCE"
    p.write_text(yaml.safe_dump(dict(pol, allow_change_asil_from_profile=True)))
    assert not h.reload()[0] and h.active["profile"] == "HIGH_ASSURANCE"


def test_at067_enforcing_without_authorized_pilot_rejected(store):
    pol = contracts.load(contracts.POLICY_EXAMPLE)
    r = policy.request_mode(store, pol, "ENFORCING")
    assert r["decision"] == "REJECTED" and r["mode"] == "OBSERVE_ONLY"
    assert {"HUMAN_AUTHORIZATION_MISSING", "VALIDATED_PILOT_MISSING", "ENFORCING_REQUIRES_PILOT_FIRST"} <= set(r["issues"])
    auth = {"approved_by": "j.doe", "approved_at": "2026-10-17T12:00:00Z", "reference": "owner-decision-42"}
    assert policy.request_mode(store, pol, "PILOT", {**auth, "approved_by": "agent-x"})["mode"] == "OBSERVE_ONLY"
    assert policy.request_mode(store, pol, "PILOT", auth)["mode"] == "PILOT"
    piloting = dict(pol, mode="PILOT", authorization=auth)
    weak = store.append("mode", "pilot-result", {"pilot_status": "PASS", "false_positive_rate": None,
                                                 "false_negative_rate": None}, actor="easa")
    assert "PILOT_ERROR_RATES_NOT_MEASURED" in policy.request_mode(store, piloting, "ENFORCING", auth, weak)["issues"]
    good = store.append("mode", "pilot-result", {"pilot_status": "PASS", "false_positive_rate": 0.0,
                                                 "false_negative_rate": 0.1, "independent_review_by": "k.roe"},
                        actor="easa")
    assert policy.request_mode(store, piloting, "ENFORCING", auth, good)["mode"] == "ENFORCING"
    assert policy.request_mode(store, piloting, "OBSERVE_ONLY")["mode"] == "OBSERVE_ONLY"   # downgrade always ok


# ---- T005 / T012 / AT-012 / AT-078 / AT-079: scope ---------------------------------------------------------------
def test_at078_asil_b_without_hsi_and_tool_confidence_blocks():
    r = scope.evaluate(scope_b(hsi_hash=None), {"software_safety_analysis": "doc:ssa-1"})
    assert r["state"] == "BLOCKED" and r["safety_approval"] is None
    assert {"SAFETY_EVIDENCE_MISSING:hsi", "SAFETY_EVIDENCE_MISSING:tool_assurance_assessment"} <= set(r["issues"])
    na = {"tool_assurance_assessment": {"rationale": "x" * 40, "approved_by": "j.doe"}}
    assert "NA_NOT_PERMITTED_FOR_ASIL:tool_assurance_assessment" in scope.evaluate(scope_b(), {}, na)["issues"]


def test_at012_qm_na_needs_rationale_and_human_and_asil_source_must_be_approved():
    qm = scope_b(target_asil="QM", hsi_hash=None, allocation_review_ref=None)
    assert scope.evaluate(qm, {})["issues"] == ["QM_NA_WITHOUT_RATIONALE:software_safety_analysis",
                                                "QM_NA_WITHOUT_RATIONALE:tool_assurance_assessment"]
    na = {d: {"rationale": "QM scope approved by owner; no safety allocation", "approved_by": "j.doe"}
          for d in scope.SAFETY_DOCS}
    assert scope.evaluate(qm, {}, na)["state"] == "SATISFIED"
    assert "ASIL_SOURCE_NOT_APPROVED_ALLOCATION" in scope.validate(scope_b(product_asil_source="assurance-profile"))


def test_at079_qm_scope_rejects_asil_d_text():
    qm = scope_b(target_asil="QM")
    f = scope.claim_text_findings(qm, "This HAL is ASIL D compliant and ISO 26262 certified.")
    assert any(x.startswith("ASIL_MISMATCH_TEXT:ASIL D") for x in f)
    assert any(x.startswith("FALSE_COMPLIANCE_TEXT") for x in f)
    assert scope.claim_text_findings(qm, "Offline review candidate; QM scope.") == []


# ---- T014 / AT-014 / AT-074: capability resolver, no fabricated metric ------------------------------------------
def test_at014_resolver_uses_real_ops_and_marks_gaps(cat):
    ops = {"forge-tests-mcp.llvm_coverage": {"status": "OK"}, "forge-tests-mcp.run_unit": {"status": "OK"},
           "forge-analysis-mcp.cppcheck": {"status": "OK"}, "forge-analysis-mcp.clang_analyze": {"status": "MISSING"}}
    res = {r["method_id"]: r for r in capability.resolve(cat, ops)}
    assert len(res) == 47
    assert res["ISO6-T09-1B"]["resolution"] == "SUPPORTED"
    assert res["ISO6-T07-1H"]["resolution"] == "PARTIAL"
    assert res["ISO6-T13-1A"]["resolution"] == "NOT_SUPPORTED"
    assert res["ISO6-T02-1A"]["resolution"] == "CONTROLLED_REVIEW"
    live = {r["method_id"]: r for r in capability.resolve(cat)}      # real op catalog of this host
    assert live["ISO6-T13-1B"]["resolution"] == "NOT_SUPPORTED"


def test_at074_not_run_mcdc_reported_as_100_percent_rejected():
    rec = {"code_hash": "c" * 64, "kind": "MCDC", "measured": True, "covered": 10, "total": 10, "scope": "hal",
           "test_run_refs": [], "uncovered_rationale_refs": [], "tool_id": "llvm-cov", "status": "NOT_SUPPORTED"}
    assert "FABRICATED_METRIC:MCDC:NOT_SUPPORTED" in capability.metric_findings(rec)
    ok = dict(rec, measured=False, covered=None, total=None)
    assert capability.metric_findings(ok) == []
    m = dict(rec, status="MEASURED")
    assert "MEASURED_WITHOUT_TEST_RUN_REF" in capability.metric_findings(m)
