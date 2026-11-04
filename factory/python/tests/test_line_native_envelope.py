"""Actual profile/sanitizer preflight, no model calls or budget/profile changes."""
import pytest
from forge_factory.afo.durable import Refused
from forge_factory.afo.line_recovery_control import native_envelope_minimum
from forge_factory.lrtx.profile import load, role_job_tokens

PROFILE = "local-rtx-v2-omniverse2-ornith-think-author-q38-inspector"


def job(role):
    profile = load(PROFILE)
    return {"role": role, "profile": PROFILE, "model": profile["structured"]["role_models"]["author"],
            "reserved_tokens": role_job_tokens(profile, role, 32768)}


def test_current_maintenance_reservation_cannot_fit_smallest_thinking_request():
    before = load(PROFILE)["_sha256"]
    with pytest.raises(Refused, match="NATIVE_ENVELOPE_EXCEEDS_RESERVATION"):
        native_envelope_minimum(job("afo-factory-maintainer"))
    assert load(PROFILE)["_sha256"] == before
    assert job("afo-factory-maintainer")["reserved_tokens"] == 131072


def test_planner_lower_bound_fit_is_not_native_default_measurement_or_qualification():
    report = native_envelope_minimum(job("afo-recovery-planner"))
    assert report["minimum_positive_output_cap"] == 131073
    assert report["status"] == "LOWER_BOUND_FITS_NOT_QUALIFICATION"
    assert report["native_sdk_default"] == "NOT_MEASURED" and report["model_calls"] == 0


def test_inspector_uses_its_own_declared_output_envelope():
    value = job("afo-recovery-planner")
    value["model"] = load(PROFILE)["structured"]["role_models"]["inspector"]
    extra = load(PROFILE)["gateway"]["reasoning"][value["model"]]["extra_output_tokens"]
    assert native_envelope_minimum(value)["minimum_total_tokens"] == extra + 2
