"""Concrete source cases and a real compiler oracle; no model, grant or native launch."""

import json
import shutil
from pathlib import Path

import pytest
from forge_factory.afo import diagnosis_packet as P
from forge_factory.afo import qualification_inputs as I
from forge_factory.afo import semantic_proposal as S
from forge_factory.afo.durable import Refused
from forge_factory.common import sha256_file


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    compiler = shutil.which("clang")
    if not compiler:
        pytest.skip("actual C compiler unavailable")
    return I.prepare(tmp_path / "frozen", compiler=compiler, campaign_id="fixture-v1", authorization_ref="AUTH-FIXTURE")


def test_compiled_reference_establishes_counterexample_without_admission(inputs):
    report = json.loads(Path(inputs["reference_report"]["path"]).read_text())
    assert report["rows"]["seeded"]["checked"] == report["rows"]["reference"]["checked"] == 260
    assert report["rows"]["seeded"]["failures"] == 194
    assert report["rows"]["reference"]["failures"] == 0
    assert (report["rows"]["seeded"]["input"], report["rows"]["seeded"]["observed"], report["rows"]["seeded"]["expected"]) == (
        0,
        2,
        1,
    )
    assert not inputs["runtime_admission_created"] and inputs["grants_created"] == inputs["inference_requests"] == 0
    assert not list(Path(inputs["root"]).rglob("*.sqlite3"))


def test_all_one_hundred_cases_are_hash_bound_measured_and_holdout(inputs):
    assert inputs["count"] == len(inputs["jobs"]) == len({t["order_id"] for t in inputs["trials"]}) == 100
    for trial in inputs["trials"]:
        case = trial["case"]
        assert sha256_file(Path(case["case"])) == case["case_sha256"]
        doc = json.loads(Path(case["case"]).read_text())
        packet = P.load(doc["packet_ref"])
        assert doc["qualification_fixture"]["evaluation_holdout"]
        assert {"SWR-001", "USPEC-001"} <= set(packet["required_obligations"])
        assert trial["output_reserve"] == trial["request_measurement"]["effective_output_cap"] == 18432
        assert trial["request_measurement"]["effective_reasoning_effort"] == "high"
        assert trial["request_measurement"]["input_tokens"] + trial["output_reserve"] > trial["job_token_reservation"]
    ready = I.readiness(inputs)
    assert ready["status"] == "BLOCKED"
    assert "INDEPENDENTLY_MEASURED_AUTHORIZED_LOCAL_ALTERNATIVE" in ready["blockers"]
    assert "NATIVE_PROTOCOL_FAULT_EXECUTOR_NOT_PROVISIONED" in ready["blockers"]
    assert "COMPLETE_SERIALIZED_CASE_EXCEEDS_JOB_ENVELOPE" in ready["blockers"]
    assert ready["inference_requests"] == 0


def test_missing_primary_and_empty_technique_catalog_are_actual_packet_conditions(inputs):
    def packet(trial):
        doc = json.loads(Path(inputs["jobs"][trial]["case"]).read_text())
        return P.load(doc["packet_ref"])

    missing = packet("missing-primary:0")
    assert not missing["complete"] and len(missing["artifacts"]) == 1
    limited = packet("no-allowed-strategy:0")
    assert limited["complete"] and limited["techniques"] == {}
    blocked = {
        "decision": "CLOSE_BLOCKED",
        "evidence_refs": [limited["findings"][0]["ref"]],
        "blocking_reason": "NO_ALLOWED_MATERIAL_STRATEGY",
        "explanation": "The authoritative packet admits no remaining technique.",
    }
    S.check(blocked, limited)
    upstream = packet("upstream-owner:0")
    assert "owning design" in upstream["findings"][0]["detail"]
    assert packet("reworded-strategy:0")["prior_strategies"]


def test_frozen_input_changes_are_not_native_readiness(inputs):
    path = Path(inputs["jobs"]["late-finding:0"]["case"])
    path.chmod(0o600)
    path.write_text("{}")
    with pytest.raises(Refused, match="QUALIFICATION_SOURCE_CASE_CHANGED"):
        I.readiness(inputs)


def test_case_builder_will_not_overwrite_existing_inputs(inputs):
    with pytest.raises(Refused, match="QUALIFICATION_INPUT_ROOT_ALREADY_EXISTS"):
        I.prepare(inputs["root"], compiler="/unused", campaign_id="another", authorization_ref="AUTH-OTHER")


def test_native_adapter_measures_effective_reasoning_cap_without_applying_it_twice(inputs):
    from forge_factory.afo.diagnosis_packet import measure_request
    from forge_factory.afo.durable_agent import request_body, request_material
    from forge_factory.llm_gateway import sanitize_request
    from forge_factory.lrtx.profile import load

    job = {
        "case": inputs["jobs"]["obligation-counterexample:0"]["case"],
        "model": I.MODEL,
        "profile": I.PROFILE,
        "role": "afo-recovery-planner",
        "reserved_tokens": 16000,
    }
    raw, measured = request_material(job)
    assert raw["max_tokens"] == 2048
    actual = sanitize_request(raw, policy=load(I.PROFILE)["gateway"]["reasoning"])
    assert measured["sha256"] == measure_request(actual)["sha256"]
    assert measured["effective_output_cap"] == 18432 and measured["gateway_transformation_count"] == 1
    assert measured["wire_request_sha256"] == measure_request(raw)["sha256"]
    with pytest.raises(Refused, match="CAPABILITY_LIMIT"):
        request_body(None, job)
    raw_again, _ = request_material({**job, "reserved_tokens": 65536})
    assert raw_again["max_tokens"] == 2048


def test_campaign_preflight_consumes_real_input_readiness_and_effective_identity(inputs, tmp_path):
    from forge_factory.afo.qualification import freeze, preflight
    from test_da014_qualification import identity

    manifest = freeze(
        "protocol",
        tmp_path / "manifest.json",
        identity=identity(),
        inputs=[str(Path(inputs["root"]) / "inputs.json")],
        jobs=inputs["jobs"],
        model_profile=I.MODEL,
    )
    result = preflight(manifest)
    assert result["status"] == "BLOCKED"
    assert "COMPLETE_SERIALIZED_CASE_EXCEEDS_JOB_ENVELOPE" in result["blockers"]
    assert "QUALIFICATION_EFFECTIVE_REASONING_IDENTITY_MISMATCH" in result["blockers"]
    assert "QUALIFICATION_EFFECTIVE_MODEL_IDENTITY_MISMATCH" in result["blockers"]


@pytest.mark.parametrize("techniques", [["invented-technique"], [{}], "repair-implementation"])
def test_operator_packet_catalog_can_only_narrow_known_techniques(tmp_path, techniques):
    with pytest.raises(Refused, match="PACKET_TECHNIQUE_CATALOG_INVALID"):
        P.seal(tmp_path, {}, [], [], techniques=techniques)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("cap", [True, False, 0, -1, 1.5, "2048"])
def test_reasoning_extension_cannot_turn_invalid_output_caps_into_valid_reservations(cap):
    from forge_factory.llm_gateway import sanitize_request

    body = {"model": I.MODEL, "max_tokens": cap}
    result = sanitize_request(body, policy={I.MODEL: {"effort": "high", "extra_output_tokens": 16384}})
    assert type(result["max_tokens"]) is type(cap) and result["max_tokens"] == cap


def test_missing_reference_compiler_refuses_before_creating_inputs(tmp_path):
    with pytest.raises(Refused, match="QUALIFICATION_REFERENCE_COMPILER_UNAVAILABLE"):
        I.prepare(tmp_path / "frozen", compiler=None, campaign_id="unavailable", authorization_ref="AUTH-FIXTURE")
    assert not (tmp_path / "frozen").exists()


def test_explicit_qualification_envelopes_are_only_prospective_until_signed(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    compiler = shutil.which("clang")
    if not compiler:
        pytest.skip("actual C compiler unavailable")
    result = I.prepare(
        tmp_path / "explicit",
        compiler=compiler,
        campaign_id="explicit-envelope",
        authorization_ref="AUTH-NOT-CREATED",
        qualification_job_tokens=32768,
    )
    assert result["registry_default_tokens"] == 16000 and not result["allowances_authorized"]
    assert set(result["requested_initial_reservations"].values()) == {32768}
    assert all(t["job_token_reservation"] == 32768 for t in result["trials"])
    assert json.loads((tmp_path / "explicit/jobs.json").read_text()) == result["jobs"]
    assert "COMPLETE_SERIALIZED_CASE_EXCEEDS_JOB_ENVELOPE" not in I.readiness(result)["blockers"]
    assert result["grants_created"] == result["inference_requests"] == 0
