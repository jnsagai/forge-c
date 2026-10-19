"""EASA-T063 / AT-063: reviewer-readable assurance case — deterministic, hash-listed inputs, open claims and missing
evidence stated, invalid input never silently passes, no conformance assertion can be emitted."""
import pytest
from forge_factory.assurance import case
from test_easa_m7 import _stage, needs_r102

SUMMARY = {"mode": "OBSERVE_ONLY", "profile": "ENHANCED", "catalog_status": "UNVERIFIED", "generated_at": "t1",
           "blocking_findings": ["EASA:INDEPENDENCE_PARTIAL"], "safety_scope": {"status": "NO_APPROVED_SCOPE",
                                                                                "note": "scope not recorded"}}
ATT = {"work_order_id": "WO-X", "decision": "PARTIAL", "shared_common_cause_refs": ["same-model:deepseek-flash"]}
APPL = [{"method_id": "M-01", "resolution": "SUPPORTED"}, {"method_id": "M-02", "resolution": "NOT_SUPPORTED"},
        {"method_id": "M-03", "resolution": "PARTIAL"}]
FID = {"limitations": ["RCC_CR reset value differs from the RM"], "environments": ["HOST", "RENODE"],
       "hil": "NOT_AVAILABLE", "physical": "NOT_AVAILABLE"}


def _claims():
    return [{"claim_id": "CLM-SWE.1", "assertion": "SWE.1 objectives met by independent evidence", "status": "SUPPORTED",
             "gate_002": "PASS", "assurance_gate": "PASS", "open_requirements": []},
            {"claim_id": "CLM-SWE.4", "assertion": "SWE.4 objectives met by independent evidence", "status": "CONTESTED",
             "gate_002": "PASS", "assurance_gate": "FAIL", "open_requirements": ["MUTATION_EVIDENCE"]},
            {"claim_id": "CLM-SWE.6", "assertion": "SWE.6 objectives met by independent evidence", "status": "UNKNOWN",
             "gate_002": None, "assurance_gate": "NOT_RUN", "open_requirements": []}]


def test_at063_valid_case_is_deterministic_and_lists_open_claims():
    md, meta = case.render(SUMMARY, _claims(), ATT, APPL, FID)
    md2, _ = case.render({**SUMMARY, "generated_at": "t2"}, _claims(), ATT, APPL, FID)
    assert md == md2                                         # timestamps do not change the case
    assert meta["state"] == "CONTESTED" and meta["open_claims"] == ["CLM-SWE.4", "CLM-SWE.6"]
    assert "**CLM-SWE.4** CONTESTED" in md and "MUTATION_EVIDENCE" in md and "NOT_SUPPORTED (1): M-02" in md
    assert "HIL: NOT_AVAILABLE" in md and "not a safety sign-off" in md and len(meta["inputs"]) == 5


def test_at063_all_supported_but_partial_independence_is_not_supported():
    c = [{**x, "status": "SUPPORTED"} for x in _claims()]
    assert case.render(SUMMARY, c, ATT, APPL, FID)[1]["state"] == "UNSUPPORTED"
    assert case.render(SUMMARY, c, {**ATT, "decision": "SUPPORTED"}, APPL, FID)[1]["state"] == "SUPPORTED"


@pytest.mark.parametrize("claims,issue", [
    ([], "NO_CLAIMS"),
    ([{"assertion": "x", "status": "SUPPORTED"}], "INVALID_CLAIM_RECORD:#0"),
    ([{"claim_id": "CLM-SWE.1", "status": "PASS"}], "INVALID_CLAIM_STATUS:CLM-SWE.1:PASS"),
    ([{"claim_id": "CLM-SWE.1", "status": "SUPPORTED", "safety_conclusion": "safe"}],
     "SAFETY_CONCLUSION_IN_CLAIM:CLM-SWE.1"),
])
def test_at063_invalid_input_never_silently_passes(claims, issue):
    md, meta = case.render(SUMMARY, claims, {**ATT, "decision": "SUPPORTED"}, APPL, FID)
    assert meta["state"] == "UNSUPPORTED" and issue in meta["invalid"] and f"`{issue}`" in md


def test_at063_case_asserting_conformance_is_refused():
    c = _claims()
    c[0]["assertion"] = "The driver is ISO 26262 compliant and ASIL B certified"
    with pytest.raises(ValueError, match="ASSURANCE_CASE_ASSERTS_COMPLIANCE"):
        case.render(SUMMARY, c, ATT, APPL, FID)


@needs_r102
def test_at063_bundle_writes_hashed_case_into_the_package(tmp_path):
    import hashlib
    import json

    from forge_factory.assurance import package as P

    ws, stage = _stage(tmp_path)
    P.bundle_into(ws, stage, "BLOCKED")
    md = (stage / "assurance/ASSURANCE-CASE.md").read_bytes()
    hashes = json.loads((stage / "assurance/hashes.json").read_text())["files"]
    assert hashes["assurance/ASSURANCE-CASE.md"] == hashlib.sha256(md).hexdigest()
    meta = json.loads((stage / "assurance/case.json").read_text())
    assert meta["state"] in ("UNSUPPORTED", "CONTESTED") and b"Remaining claims and missing evidence" in md
