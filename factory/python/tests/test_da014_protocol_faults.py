"""Fixed signed interventions through the actual response/broker boundary; zero model calls."""
# ruff: noqa: F811

import hashlib
import json

import pytest
from forge_factory.afo import authz
from forge_factory.afo import diagnosis_packet as P
from forge_factory.afo import local_agent as L
from forge_factory.afo import protocol_faults as F
from forge_factory.afo import qualification as Q
from forge_factory.afo.completion_receipt import Context, Receipts
from forge_factory.afo.durable import Refused, digest, immutable_json, strict_json
from forge_factory.afo.durable_agent import response_receipt
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.common import sha256_file
from test_afo_local_autonomy import local  # noqa: F401
from test_afo_m4_recovery import order  # noqa: F401
from test_da014_qualification_reservations import signed  # noqa: F401


def bind(signed, name, *, fixture=True):
    p = signed
    trial = name + ":0"
    recipe = F.FAULT_RECIPES[name]
    doc = json.loads(p.case.read_text())
    source = p.ws / "workproducts/SWE.3/unit_specifications.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("Explicit deterministic test contract: preserve EN mask 1.\n")
    doc["packet_ref"] = P.seal(
        p.ws,
        p.bundle,
        [{"id": "fixture-counterexample", "obligation_id": "USPEC-001", "detail": "Seeded deterministic test counterexample"}],
        [{"path": "workproducts/SWE.3/unit_specifications.md"}],
    )
    if fixture:
        doc["qualification_fixture"] = {
            "source_kind": "SEEDED_PROTOCOL_NOT_PRODUCT",
            "trial_id": trial,
            "evaluation_holdout": True,
            "prospective_fault": recipe,
        }
    p.case = p.case.parent / (name + "-case.json")
    immutable_json(p.case, doc)
    p.manifest["inputs"] = [{"path": str(p.case), "sha256": sha256_file(p.case)}]
    p.manifest["jobs"] = {
        trial: {"job_id": p.jid, "case": str(p.case), "case_sha256": sha256_file(p.case), "mission_id": "qualification-only"}
    }
    p.manifest["protocol_faults"] = {trial: recipe}
    Q.validate(p.manifest)
    p.grant["signed_runbook_ref"] = "qualification-014:" + digest(p.manifest)
    p.grant_path.write_text(json.dumps(p.grant))
    authz.sign(p.grant_path, p.key)
    job = L.prepare(
        p.store, p.order, p.bundle["attempt_id"], "afo-recovery-planner", p.case, p.ws, p.eff, qualification_manifest=p.manifest
    )
    ex = Executions(p.store)
    ex.reserve(job["job_id"], job["mission_id"], job["nonce"])
    ex.dispatch_intent(job["job_id"])
    packet = P.load(doc["packet_ref"])
    proposal = dict(
        decision="PROPOSE_REPAIR",
        evidence_refs=[packet["artifacts"][0]["ref"]],
        strategy="REWORK_LOCAL",
        target_obligations=["USPEC-001"],
        affected_phase="SWE.3",
        causal_hypothesis="Seeded effect mismatch",
        technique_id="repair-implementation",
        material_difference="Implement the required effect",
        proposed_change="Correct the register effect",
        artifact_scope=["software/hal"],
        validation_expectations=[{"test_ref": "gate:SWE.3:route=PASS", "expected_result": "PASS"}],
    )
    return job, json.dumps(proposal), packet


@pytest.mark.parametrize("name", sorted(F.SUPPORTED))
def test_signed_faults_bind_exact_fixture_and_preserve_immutable_intervention_hashes(signed, name):
    p = signed
    job, raw, packet = bind(p, name)
    changed = F.apply_response(p.store, job, raw, p.eff)
    assert F.apply_response(p.store, job, raw, p.eff) == changed
    with p.store.tx() as c:
        rows = c.execute("SELECT record FROM afo_execution_evidence WHERE kind='PROTOCOL_RESPONSE_FAULT'").fetchall()
    assert len(rows) == 1
    fact = json.loads(rows[0][0])
    assert fact["original_response_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert fact["injected_response_sha256"] == hashlib.sha256(changed.encode()).hexdigest()
    assert fact["manifest_sha256"] == digest(p.manifest)
    assert raw not in rows[0][0] and "reasoning" not in rows[0][0]
    row = {
        "trial_id": name + ":0",
        "job_id": job["job_id"],
        "declared_fault": job["qualification_fault"],
        "execution": Executions(p.store).get(job["job_id"]),
        "fault_observation": fact,
    }
    assert F.observation_matches(p.manifest, row)
    assert not F.observation_matches(p.manifest, {**row, "fault_observation": None})
    assert not F.observation_matches(p.manifest, {**row, "fault_observation": {**fact, "case_sha256": "0" * 64}})
    if name == "empty-output":
        assert changed == ""
        with pytest.raises(Refused, match="EMPTY_MODEL_OUTPUT"):
            response_receipt(p.store, job, {"choices": [{"message": {"content": raw}}]}, p.eff)
        assert not Receipts(p.store).for_job(Context.from_job(p.store, job["job_id"]))
    else:
        receipt = response_receipt(p.store, job, {"choices": [{"message": {"content": raw}}]}, p.eff)
        if name == "unqualified-local-alternative":
            from forge_factory.afo.semantic_proposal import check

            with pytest.raises(Refused, match="LOCAL_ALTERNATIVE_NOT_QUALIFIED_AND_AUTHORIZED"):
                check(strict_json(changed), packet)
        else:
            assert receipt["submission_state"] == "REJECTED"
    with pytest.raises(Refused, match="QUALIFICATION_FAULT_REPLAY_CHANGED"):
        F.apply_response(p.store, job, raw + " ", p.eff)
    assert p.ledger.snapshot("qualification-only")["requests"] == 0


@pytest.mark.parametrize("fault", ["revoked", "nonce", "unbound-metadata", "inactive", "scope", "deadline"])
def test_fault_cannot_run_after_revocation_binding_change_or_execution_retirement(signed, fault):
    p = signed
    job, raw, _ = bind(p, "administrative-forgery")
    if fault == "revoked":
        (p.grant_path.parent / "revoked.txt").write_text("AUTH-QUAL\n")
        code = "AUTH_REVOKED"
    elif fault == "nonce":
        job = {**job, "nonce": "different"}
        code = "QUALIFICATION_FAULT_JOB_BINDING_INVALID"
    elif fault == "unbound-metadata":
        job = {**job, "qualification_fault": {**job["qualification_fault"], "manifest_sha256": "0" * 64}}
        code = "QUALIFICATION_FAULT_NOT_BOUND_TO_JOB"
    elif fault == "scope":
        p.grant["scope"]["order_ids"] = ["another-order"]
        p.grant_path.write_text(json.dumps(p.grant))
        authz.sign(p.grant_path, p.key)
        code = "AUTH_OUT_OF_SCOPE"
    elif fault == "deadline":
        L.save(p.store, {**job, "deadline_epoch": 0})
        code = "QUALIFICATION_FAULT_POLICY_OR_DEADLINE_CHANGED"
    else:
        Executions(p.store).outcome(job["job_id"], "BLOCKED", "explicit test stop")
        code = "QUALIFICATION_FAULT_EXECUTION_NOT_ACTIVE"
    with pytest.raises(Refused, match=code):
        F.apply_response(p.store, job, raw, p.eff)
    with p.store.tx() as c:
        assert c.execute("SELECT COUNT(*) FROM afo_execution_evidence WHERE kind='PROTOCOL_RESPONSE_FAULT'").fetchone()[0] == 0


def test_signed_catalogue_does_not_enable_faults_for_ordinary_product_cases(signed):
    before = signed.ledger.snapshot("qualification-only")
    with pytest.raises(Refused, match="QUALIFICATION_FAULT_REQUIRES_EXPLICIT_FROZEN_FIXTURE"):
        bind(signed, "administrative-forgery", fixture=False)
    assert signed.ledger.snapshot("qualification-only") == before


def test_missing_and_unsupported_fault_executors_remain_blocked():
    with pytest.raises(Refused, match="QUALIFICATION_FAULT_RECIPE_UNSUPPORTED"):
        F.validate_catalogue(
            {"cancel-ack-still-live:0": F.FAULT_RECIPES["cancel-ack-still-live"]}, {"cancel-ack-still-live:0": {}}
        )
    raw = '{"visible":"unchanged"}'
    assert F.apply_response(None, {}, raw, None) is raw


@pytest.mark.parametrize("content", ["", "  \n", None, False, {"forged": "content"}])
def test_empty_or_invalid_unmodified_model_content_never_creates_a_semantic_receipt(signed, content):
    p = signed
    job = L.prepare(p.store, p.order, p.bundle["attempt_id"], "afo-recovery-planner", p.case, p.ws, p.eff)
    with pytest.raises(Refused, match="EMPTY_MODEL_OUTPUT|INVALID_MODEL_OUTPUT_TYPE"):
        response_receipt(p.store, job, {"choices": [{"message": {"content": content}}]}, p.eff)
    assert not Receipts(p.store).for_job(Context.from_job(p.store, job["job_id"]))


def test_truncation_removes_json_brace_even_with_trailing_whitespace(signed):
    p = signed
    job, raw, _ = bind(p, "malformed-output")
    with pytest.raises(Refused, match="INVALID_JSON"):
        strict_json(F.apply_response(p.store, job, raw + "  \n", p.eff))
