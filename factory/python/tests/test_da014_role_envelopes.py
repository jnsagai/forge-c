"""Finite, prospective role budgets; configuration is neither authority nor qualification."""
# ruff: noqa: F811
import json
import time
from pathlib import Path

import pytest
from forge_factory.afo import local_agent as L
from forge_factory.afo import planner
from forge_factory.afo.durable import Refused
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import QueueError
from forge_factory.lrtx import profile as P
from test_afo_local_autonomy import local  # noqa: F401
from test_afo_m4_recovery import order  # noqa: F401

MODEL = "qwen3.8:27b-q8_0"
PROFILE = "local-rtx-v2-omniverse2-q38-quality"


def select(p, profile):
    _, _, _, eff, ws, _ = p
    eff.policy["engineering"]["allowed_model_profiles"] = [MODEL]
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"local_profile": {
        "id": profile["id"], "version": profile["version"],
        "config": profile["_path"], "config_sha256": profile["_sha256"],
    }}))
    (ws / ".forge-run/model-profile.json").write_text(json.dumps({"default": MODEL}))


def prepare(p, *, role="afo-recovery-planner", case=None):
    store, order, bundle, eff, ws, original = p
    return L.prepare(store, order, bundle["attempt_id"], role, case or original, ws, eff)


def durable(p, *, text="NO_INSPECTION_FOR_CURRENT_BASELINE", tokens=120000):
    store, order, bundle, _, ws, _ = p
    ledger = MissionLedger(store)
    ledger.register("prospective", "new-case-lineage", {
        "max_attempts": 3, "max_jobs": 4, "max_requests": 32, "max_tokens": tokens,
        "max_tools": 32, "max_corrections": 1, "deadline": time.time() + 600,
    }, "AUTH-fixture", authorize=lambda *a: True)
    ledger.link("prospective", order["order_id"])
    gate = ws / ".forge-run/gates/gate-log.jsonl"
    gate.parent.mkdir()
    gate.write_text(json.dumps({"phase": "SWE.3", "step": "route", "gate": {
        "phase": "SWE.3", "decision": "BLOCKED", "reason": text,
    }}) + "\n")
    case = planner.case(bundle, ws, {}, mission_id="prospective")
    return ledger, case


def test_bound_profile_reservation_survives_restart_without_a_second_charge(local):
    from forge_factory.afo.durable_agent import request_material
    from forge_factory.afo.queue import Store

    selected = P.load(PROFILE)
    select(local, selected)
    ledger, case = durable(local)
    job = prepare(local, case=case)
    assert job["reserved_tokens"] == 65536
    assert job["profile_initial_reservation"] == {
        "profile_sha256": selected["_sha256"], "profile_version": selected["version"],
        "registry_default_tokens": 16000, "configured_tokens": 65536,
    }
    measured = job["initial_request_measurement"]
    assert measured["effective_reasoning_effort"] == "xhigh"
    assert measured["effective_output_cap"] == 34816
    assert measured["input_tokens"] + 34816 <= job["reserved_tokens"]
    assert measured["method"] == "utf8_byte_upper_bound" and not measured["native_measured"]
    raw, again = request_material(job)
    assert measured == again and raw["max_tokens"] == 2048
    store, order, bundle, eff, ws, _ = local
    before = ledger.snapshot("prospective")
    same = L.prepare(Store(), order, bundle["attempt_id"], job["role"], case, ws, eff)
    assert same == job and ledger.snapshot("prospective") == before
    assert before["charged_tokens"] == 65536 and before["requests"] == 0
    assert not any(key in job for key in ["messages", "response_format", "capability_receipt"])


@pytest.mark.parametrize("field,value", [
    ("config_sha256", "0" * 64), ("config", "config/other.yaml"),
    ("version", 0), ("version", True),
])
def test_profile_budget_requires_exact_workspace_binding_before_charging(local, field, value):
    select(local, P.load(PROFILE))
    ledger, case = durable(local)
    path = local[4] / ".forge-run/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["local_profile"][field] = value
    path.write_text(json.dumps(manifest))
    with pytest.raises(P.ProfileRefused, match="PROFILE_ROLE_ENVELOPE_BINDING_CHANGED"):
        prepare(local, case=case)
    assert ledger.snapshot("prospective")["charged_tokens"] == 0
    assert not L.records(local[0], local[1]["order_id"])


def test_preflight_includes_full_evidence_and_reasoning_before_reserving(local):
    select(local, P.load(PROFILE))
    ledger, case = durable(local, text="large mandatory gate evidence " * 3000)
    with pytest.raises(Refused, match="CAPABILITY_LIMIT"):
        prepare(local, case=case)
    snapshot = ledger.snapshot("prospective")
    assert snapshot["charged_tokens"] == snapshot["jobs"] == snapshot["requests"] == 0
    assert not L.records(local[0], local[1]["order_id"])


def test_profile_reservation_cannot_raise_policy_or_mission_allowance(local):
    select(local, P.load(PROFILE))
    ledger, case = durable(local, tokens=60000)
    with pytest.raises(Refused, match="MISSION_ALLOWANCE_EXHAUSTED"):
        prepare(local, case=case)
    assert ledger.snapshot("prospective")["charged_tokens"] == 0
    local[3].policy["budgets"]["max_model_tokens_per_order"] = 60000
    with pytest.raises(QueueError, match="RECOVERY_PROFILE_ENVELOPE_EXCEEDS_POLICY"):
        prepare(local, case=case)
    assert ledger.snapshot("prospective")["charged_tokens"] == 0


def test_maintenance_uses_its_own_finite_envelope_and_keeps_sandbox_gate(local, monkeypatch):
    from forge_factory.reliability import isolation

    select(local, P.load(PROFILE))
    monkeypatch.setattr(isolation, "available", lambda: False)
    with pytest.raises(QueueError, match="MAINTAINER_SANDBOX_UNAVAILABLE"):
        prepare(local, role="afo-factory-maintainer")
    monkeypatch.setattr(isolation, "available", lambda: True)
    job = prepare(local, role="afo-factory-maintainer")
    assert job["reserved_tokens"] == 65536
    assert job["profile_initial_reservation"]["registry_default_tokens"] == 24000
    assert "initial_request_measurement" not in job  # native tool dialogue is checked per request


@pytest.mark.parametrize("bad", [True, 0, -1, "65536", 65537])
def test_invalid_profile_envelope_is_not_coerced_or_silently_clamped(local, monkeypatch, bad):
    prof = P.load(PROFILE)
    prof.setdefault("afo", {})["role_job_tokens"] = {"afo-recovery-planner": bad}
    select(local, prof)
    monkeypatch.setattr(P, "load", lambda _: prof)
    with pytest.raises(P.ProfileRefused, match="PROFILE_ROLE_ENVELOPE_INVALID"):
        prepare(local)
    assert not L.records(local[0], local[1]["order_id"])


def test_existing_legacy_job_cannot_be_rebound_by_selecting_new_profile(local):
    first = prepare(local)
    select(local, P.load(PROFILE))
    with pytest.raises(QueueError, match="LOCAL_AGENT_JOB_REBOUND"):
        prepare(local)
    assert L.records(local[0], local[1]["order_id"])[0] == first


def test_changed_profile_after_preparation_cannot_rewrite_request_or_charge(local, monkeypatch):
    from forge_factory.afo.durable_agent import request_body

    selected = P.load(PROFILE)
    select(local, selected)
    ledger, case = durable(local)
    job = prepare(local, case=case)
    before = ledger.snapshot("prospective")
    monkeypatch.setattr(P, "load", lambda _: {**selected, "_sha256": "0" * 64})
    with pytest.raises(Refused, match="REQUEST_PROFILE_CHANGED"):
        request_body(local[0], job)
    assert ledger.snapshot("prospective") == before


@pytest.mark.parametrize("setting", [None, [], {"swe1-inspector": 65536}])
def test_malformed_or_unregistered_role_configuration_is_refused(setting):
    selected = P.load(PROFILE)
    selected["afo"] = {"role_job_tokens": setting}
    with pytest.raises(P.ProfileRefused, match="PROFILE_ROLE_ENVELOPE_INVALID"):
        P.role_job_tokens(selected, "afo-recovery-planner", 16000)


def test_old_profiles_keep_registry_limits():
    for name in ["local-rtx-v1", "local-rtx-v2", "local-rtx-v2-omniverse2", "local-rtx-v2-omniverse2-q38"]:
        selected = P.load(name)
        assert P.role_job_tokens(selected, "afo-recovery-planner", 16000) == 16000
        assert P.role_job_tokens(selected, "afo-factory-maintainer", 24000) == 24000


def test_prepared_qualification_inputs_bind_profile_defaults_without_creating_authority(tmp_path, monkeypatch):
    import shutil

    from forge_factory.afo import qualification_inputs as I

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    compiler = shutil.which("clang")
    assert compiler, "qualification fixture requires the installed compiler"
    inputs = I.prepare(tmp_path / "quality-cases", compiler=compiler, campaign_id="quality-envelope",
                       authorization_ref="AUTH-NOT-SIGNED", model=MODEL, profile=PROFILE)
    assert inputs["count"] == 100  # full frozen catalogue, not a cherry-picked sample
    assert inputs["registry_default_tokens"] == 16000
    assert inputs["profile_default_tokens"] == 65536
    assert set(inputs["requested_initial_reservations"].values()) == {65536}
    assert not inputs["allowances_authorized"] and not inputs["runtime_admission_created"]
    assert inputs["grants_created"] == inputs["inference_requests"] == 0
    selected = P.load(PROFILE)
    for trial in inputs["trials"]:
        case = json.loads(Path(trial["case"]["case"]).read_text())
        manifest = json.loads((Path(case["workspace"]) / ".forge-run/manifest.json").read_text())
        assert manifest["local_profile"] == {
            "id": PROFILE, "version": selected["version"], "config": selected["_path"],
            "config_sha256": selected["_sha256"],
        }
        assert trial["request_measurement"]["effective_reasoning_effort"] == "xhigh"
        assert trial["output_reserve"] == 34816
