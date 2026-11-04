"""CONTROL based on SWE6 missing-report metadata; no actual driver defects or live result inferred."""

from forge_factory.afo import bundle
from forge_factory.afo import diagnosis_packet as P
from forge_factory.afo import semantic_proposal as S


def test_header_only_trace_and_rejected_defect_report_remain_missing_authored_evidence(tmp_path):
    path = tmp_path / "workproducts/SWE.6/verification_trace.csv"
    path.parent.mkdir(parents=True)
    path.write_text("Requirement ID,Verification ID,Result\n")
    failure = {
        "bundle_id": "CONTROL-not-live",
        "order_id": "CONTROL",
        "attempt_id": "CONTROL-a1",
        "phase": "SWE.6",
        "fingerprint": "CONTROL",
        "failure_class": "PRODUCT_QUALITY",
        "error_code": "MISSING_REQUIRED_OUTPUT",
    }
    packet = P.load(
        P.seal(
            tmp_path,
            failure,
            [
                {"id": "report", "detail": "Required report absent; trace has header and zero data rows"},
                {"id": "defect-call", "detail": "report_defect status FAIL / NO_REQUIREMENT_ID; no valid defect"},
            ],
            [{"path": path.relative_to(tmp_path).as_posix()}],
            missing=["workproducts/SWE.6/software_verification_report.md"],
            required_obligations=[f"SWR-{i:03}" for i in range(1, 25)],
        )
    )
    assert len([o for o in packet["required_obligations"] if o.startswith("SWR-")]) == 24
    assert len(packet["findings"]) == 2  # obligation inventory is never turned into 24 invented driver defects
    assert not packet["complete"]
    assert (
        bundle.afo_class(failure, set())
        == "PRODUCT_QUALITY"
    )
    assert (
        S.capability_route(
            complete=False, fits=True, qualified=False, can_partition=False, alternatives=[], allowed_profiles=[], remaining=True
        )["outcome"]
        == "MISSING_EVIDENCE"
    )
    assert (
        S.capability_route(
            complete=True, fits=True, qualified=False, can_partition=False, alternatives=[], allowed_profiles=[], remaining=True
        )["outcome"]
        == "CAPABILITY_LIMIT"
    )
