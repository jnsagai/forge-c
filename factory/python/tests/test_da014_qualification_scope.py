"""Frozen complete campaigns with scoped readiness and signed finite mission inputs; no model calls."""
# ruff: noqa: F811

import copy
import json
import shutil
import time
from pathlib import Path

import pytest
from forge_factory.afo import authz
from forge_factory.afo import local_agent as L
from forge_factory.afo import protocol_faults as F
from forge_factory.afo import qualification as Q
from forge_factory.afo import qualification_inputs as I
from forge_factory.afo.durable import Refused, digest
from test_afo_local_autonomy import local  # noqa: F401
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_qualification_reservations import signed  # noqa: F401


@pytest.fixture
def campaign(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    compiler = shutil.which("clang")
    if not compiler:
        pytest.skip("actual C compiler unavailable")
    inputs = I.prepare(
        tmp_path / "inputs",
        compiler=compiler,
        campaign_id="scope-fixture",
        authorization_ref="AUTH-UNSIGNED",
        qualification_job_tokens=32768,
    )
    config = inputs["model_configuration"]
    identity = {
        "role": "afo-recovery-planner",
        "model_digest": config["model_digest"],
        "precision": config["precision"],
        "reasoning": config["reasoning_effort"],
        "schema_mode": "json_schema",
        "adapter_revision": Q.revision(),
        "context_tokens": 65536,
        "sampling": {"temperature": 0},
        "task_class": "single-obligation-protocol",
    }
    mission = {
        "mission_id": inputs["mission_id"],
        "lineage": "explicit-distinct-protocol-scope",
        "limits": {
            "max_attempts": 0,
            "max_jobs": 100,
            "max_requests": 100,
            "max_tokens": 3276800,
            "max_tools": 0,
            "max_corrections": 0,
            "deadline": time.time() + 3600,
        },
    }
    manifest = Q.freeze(
        "protocol",
        tmp_path / "manifest.json",
        identity=identity,
        inputs=[Path(inputs["root"]) / "inputs.json"],
        jobs=inputs["jobs"],
        model_profile=config["model"],
        job_token_reservations=inputs["requested_initial_reservations"],
        mission=mission,
        protocol_faults={
            t["trial_id"]: t["prospective_fault"] for t in inputs["trials"] if t["trial_id"].rsplit(":", 1)[0] in F.SUPPORTED
        },
    )
    return inputs, manifest


def test_one_eligible_trial_keeps_full_frozen_matrix_and_does_not_claim_full_gate(campaign):
    inputs, manifest = campaign
    full = Q.preflight(manifest)
    assert "INDEPENDENTLY_MEASURED_AUTHORIZED_LOCAL_ALTERNATIVE" in full["blockers"]
    # Every declared intervention now has a signed executor; capability prerequisites still block.
    assert "NATIVE_PROTOCOL_FAULT_EXECUTOR_NOT_PROVISIONED" not in full["blockers"]
    before = digest(manifest)
    ready = Q.preflight(manifest, trial_ids=["obligation-counterexample:0"])
    # An uncommitted generator remains an independent blocker in a development
    # checkout. The exact clean-revision run must have no such blocker.
    expected = ["QUALIFICATION_INPUT_GENERATOR_SOURCE_DIRTY"] if inputs["generator_revision"]["dirty"] else []
    assert ready["blockers"] == expected
    assert ready["campaign_denominator"] == 100 and ready["trial_scope"] == ["obligation-counterexample:0"]
    assert len(manifest["jobs"]) == 100 and len(manifest["cases"]) == 20 and digest(manifest) == before
    assert Q.protocol_report(manifest, [])["expected_denominator"] == 100
    assert Q.protocol_report(manifest, [])["status"] == "NOT_RUN"
    assert inputs["runtime_admission_created"] is False and inputs["inference_requests"] == 0


def test_scoped_preparation_retains_its_own_fault_and_capability_prerequisites(campaign):
    _, manifest = campaign
    alternative = Q.preflight(manifest, trial_ids=["qualified-local-alternative:0"])
    # All twelve recipes now have executors, but a trial still needs its own signed recipe.
    unsigned = copy.deepcopy(manifest)
    del unsigned["protocol_faults"]["cancel-ack-still-live:0"]
    fault = Q.preflight(unsigned, trial_ids=["cancel-ack-still-live:0"])
    assert "INDEPENDENTLY_MEASURED_AUTHORIZED_LOCAL_ALTERNATIVE" in alternative["blockers"]
    assert "NATIVE_PROTOCOL_FAULT_EXECUTOR_NOT_PROVISIONED" not in alternative["blockers"]
    assert "NATIVE_PROTOCOL_FAULT_EXECUTOR_NOT_PROVISIONED" in fault["blockers"]
    assert "INDEPENDENTLY_MEASURED_AUTHORIZED_LOCAL_ALTERNATIVE" not in fault["blockers"]
    signed = Q.preflight(manifest, trial_ids=["cancel-ack-still-live:0"])
    assert "NATIVE_PROTOCOL_FAULT_EXECUTOR_NOT_PROVISIONED" not in signed["blockers"]
    with pytest.raises(Refused, match="QUALIFICATION_TRIAL_SCOPE_INVALID"):
        Q.preflight(manifest, trial_ids=["invented-favorable-trial:0"])


def test_scoped_readiness_still_detects_tampering_elsewhere_in_the_frozen_matrix(campaign):
    inputs, manifest = campaign
    path = Path(inputs["jobs"]["qualified-local-alternative:4"]["case"])
    path.chmod(0o600)
    path.write_text("{}")
    scoped = Q.preflight(manifest, trial_ids=["obligation-counterexample:0"])
    assert "QUALIFICATION_SOURCE_CASE_CHANGED" in scoped["blockers"]


@pytest.mark.parametrize(
    "change", ["tokens", "jobs", "requests", "product", "tools", "corrections", "nonfinite", "wrong-lineage-type"]
)
def test_mission_preparation_cannot_extend_frozen_work_or_smuggle_unbounded_limits(campaign, change):
    _, original = campaign
    manifest = copy.deepcopy(original)
    limits = manifest["mission"]["limits"]
    if change == "wrong-lineage-type":
        manifest["mission"]["lineage"] = {"model_supplied": True}
    elif change == "nonfinite":
        limits["deadline"] = float("inf")
    else:
        key = {
            "tokens": "max_tokens",
            "jobs": "max_jobs",
            "requests": "max_requests",
            "product": "max_attempts",
            "tools": "max_tools",
            "corrections": "max_corrections",
        }[change]
        limits[key] += 1
    with pytest.raises(Refused, match="QUALIFICATION_MISSION|FINITE_MISSION"):
        Q.validate(manifest)


@pytest.mark.parametrize("mismatch", [False, True])
def test_initial_job_requires_exact_registered_mission_matching_the_new_signature(signed, mismatch):
    p = signed
    before = p.ledger.snapshot("qualification-only")
    p.manifest["mission"] = {k: copy.deepcopy(before[k]) for k in ("mission_id", "lineage", "limits")}
    if mismatch:
        # A separately signed document cannot rewrite a registered mission,
        # including a smaller cap under the same identity.
        p.manifest["mission"]["limits"]["max_tokens"] -= 1
    p.grant["signed_runbook_ref"] = "qualification-014:" + digest(p.manifest)
    p.grant_path.write_text(json.dumps(p.grant))
    authz.sign(p.grant_path, p.key)
    if mismatch:
        with pytest.raises(Refused, match="QUALIFICATION_REGISTERED_MISSION_DIFFERS_FROM_SIGNED_SCOPE"):
            L.prepare(
                p.store,
                p.order,
                p.bundle["attempt_id"],
                "afo-recovery-planner",
                p.case,
                p.ws,
                p.eff,
                qualification_manifest=p.manifest,
            )
        assert p.ledger.snapshot("qualification-only") == before and not L.records(p.store, p.order["order_id"])
    else:
        job = L.prepare(
            p.store,
            p.order,
            p.bundle["attempt_id"],
            "afo-recovery-planner",
            p.case,
            p.ws,
            p.eff,
            qualification_manifest=p.manifest,
        )
        assert job["reserved_tokens"] == 32768
        assert p.ledger.snapshot("qualification-only")["requests"] == 0


def test_report_cli_cannot_turn_a_subset_into_a_smaller_campaign(campaign, tmp_path):
    with pytest.raises(SystemExit) as stopped:
        Q.main(["report", "--manifest", str(tmp_path / "manifest.json"), "--trial", "obligation-counterexample:0"])
    assert stopped.value.code == 2


def test_scoped_preflight_cannot_reopen_an_expired_mission(campaign):
    _, manifest = campaign
    manifest["mission"]["limits"]["deadline"] = 0
    scoped = Q.preflight(manifest, trial_ids=["obligation-counterexample:0"])
    assert "QUALIFICATION_MISSION_DEADLINE_EXHAUSTED" in scoped["blockers"]
