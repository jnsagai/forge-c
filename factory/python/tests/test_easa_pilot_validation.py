"""ENFORCING precondition: the validated pilot record comes only from a human-signed, complete review worksheet and a
measured seeded-defect campaign; an agent cannot sign it, and policy.mode_preconditions accepts what it records."""

import pytest
from forge_factory.assurance import pilot_validation as PV
from forge_factory.assurance import policy
from forge_factory.assurance.store import AssuranceStore

M = {"package": "forge-c-WO-X-review.zip", "archive_sha256": "a" * 64, "pilot_check": "PASS", "seeded_applied": 6,
     "seeded_missed": ["S04", "S05"], "findings_to_review": [{"source": "package:blocking", "finding": "EASA:CLM-SWE.4:UNSUPPORTED"},
                                                              {"source": "detector:analyzers", "finding": "dead store"}]}


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    return AssuranceStore(tmp_path / "easa.db")


def _signed(**kw):
    w = PV.worksheet([M])
    for r, d in zip(w["rows"], ("CORRECT", "INCORRECT"), strict=True):
        r["disposition"] = d
    w.update({"reviewer": "Jefferson Nascimento", "reviewed_at": "2026-10-19"}, **kw)
    return w


def test_worksheet_rows_start_empty_and_an_unsigned_review_is_refused(store):
    w = PV.worksheet([M])
    assert [r["disposition"] for r in w["rows"]] == ["", ""] and w["reviewer"] == ""
    assert PV.record(w, store)["issues"][:2] == ["REVIEW_NOT_SIGNED_BY_A_HUMAN", "REVIEW_INCOMPLETE:2 rows without disposition"]
    assert PV.record(_signed(reviewer="agent:swe-inspector"), store)["issues"] == ["REVIEW_NOT_SIGNED_BY_A_HUMAN"]


def test_signed_review_records_measured_rates_that_the_mode_gate_accepts(store):
    out = PV.record(_signed(), store)
    rec = out["record"]
    assert out["decision"] == "RECORDED" and rec["pilot_status"] == "PASS"
    assert rec["false_positive_rate"] == 0.5 and rec["false_negative_rate"] == round(2 / 6, 4)
    assert rec["independent_review_by"] == "Jefferson Nascimento"
    pilot = store.get(out["record_id"])
    auth = {"approved_by": "Jefferson Nascimento", "approved_at": "2026-10-19", "reference": "OD-2026-10-19-02"}
    assert policy.mode_preconditions("PILOT", "ENFORCING", auth, pilot) == []
    assert "VALIDATED_PILOT_MISSING" in policy.mode_preconditions("PILOT", "ENFORCING", auth, None)


def test_a_failed_pilot_check_or_no_seeded_defects_never_validates(store):
    w = _signed()
    w["measurements"][0]["pilot_check"] = "FAIL"
    assert PV.record(w, store)["record"]["pilot_status"] == "FAIL"
    w["measurements"][0]["seeded_applied"] = 0
    assert PV.record(w, store)["issues"] == ["FALSE_NEGATIVES_NOT_MEASURED"]
