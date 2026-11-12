"""CAPA-195 (WO-F014-SWE1-GPIOL-20261107-L40G): every SWE.1 inspection was refused before any model call with
CALL_REFUSED:PRODUCT_ROLE_TRIAL_CONFIGURATION_UNDECLARED. The structured inspector (lrtx/review.py) sent no temperature
or seed, while the owner-signed product-role trial declares the json_schema inspector shape as temperature 0, seed 1.
The inspector now sends the profile's inspector sampling, as the semantic inspector does."""
import pytest
from forge_factory.afo import product_role_trial as T
from forge_factory.afo.durable import Refused
from forge_factory.lrtx import review as R
from forge_factory.lrtx import review_semantic as RS

# the two swe1-inspector shapes declared by the active signed trial (state/afo/product-role-trials/*.json)
TRIAL = {"roles": {"swe1-inspector": [
    {"task_class": "PRODUCT", "schema_mode": "tool", "reasoning": "medium", "sampling": {"temperature": None}},
    {"task_class": "PRODUCT", "schema_mode": "json_schema", "reasoning": "medium", "sampling": {"temperature": 0, "seed": 1}},
]}}
OWNER_PROFILE = {"inspector_stepwise": True, "inspector_sampling": {"default": {"temperature": 0.2, "seed": 1}}}


def _body(sampling):
    # as lrtx/structured.call builds it, after the gateway set the profile's reasoning effort for qwen3.8
    return {"response_format": {"type": "json_schema"}, "reasoning_effort": "medium", **(sampling or {})}


@pytest.fixture
def trial(monkeypatch):
    monkeypatch.setattr(T, "authorized", lambda ref, job, eff: TRIAL)
    monkeypatch.setattr(R, "INSPECTOR", {"sampling": None})


def test_reproducer_the_old_request_is_refused_by_the_signed_trial(trial):
    with pytest.raises(Refused) as e:
        T.identity({"product_role_trial": {"sha256": "x"}}, "swe1-inspector", _body(None), None)
    assert "PRODUCT_ROLE_TRIAL_CONFIGURATION_UNDECLARED" in str(e.value)


def test_prevention_the_inspector_sends_the_declared_shape(trial, monkeypatch, tmp_path):
    monkeypatch.setattr(RS, "_profile_structured", lambda ws: ("owner-profile", OWNER_PROFILE))
    sampling = R.inspector_sampling(tmp_path, "qwen3.8:27b-q8_0")
    assert sampling == {"temperature": 0, "seed": 1}  # stepwise: deterministic decoding with the profile seed
    got = T.identity({"product_role_trial": {"sha256": "x"}}, "swe1-inspector", _body(sampling), None)
    assert got["schema_mode"] == "json_schema" and got["sampling"] == {"temperature": 0, "seed": 1}


def test_a_harness_override_still_wins(trial, monkeypatch, tmp_path):
    monkeypatch.setattr(RS, "_profile_structured", lambda ws: ("owner-profile", OWNER_PROFILE))
    monkeypatch.setattr(R, "INSPECTOR", {"sampling": {"seed": 7}})
    assert R.inspector_sampling(tmp_path, "qwen3.8:27b-q8_0") == {"seed": 7}


def test_a_profile_without_inspector_sampling_keeps_the_gateway_default(trial, monkeypatch, tmp_path):
    monkeypatch.setattr(RS, "_profile_structured", lambda ws: (None, {}))
    assert R.inspector_sampling(tmp_path, "qwen3.8:27b-q8_0") is None
