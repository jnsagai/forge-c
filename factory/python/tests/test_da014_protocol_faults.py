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
    implementation = p.ws / "software/hal/reg32.c"
    implementation.parent.mkdir(parents=True, exist_ok=True)
    implementation.write_text(F.IMPLEMENTATION)
    from forge_factory.afo.semantic_proposal import signature

    prior = {
        "decision": "PROPOSE_REPAIR",
        "strategy": "REWORK_LOCAL",
        "affected_phase": "SWE.3",
        "technique_id": "repair-implementation",
        "target_obligations": ["USPEC-001"],
        "artifact_scope": ["software/hal"],
        "validation_expectations": [{"test_ref": "gate:SWE.3:route=PASS"}],
    }
    doc["packet_ref"] = P.seal(
        p.ws,
        p.bundle,
        [{"id": "fixture-counterexample", "obligation_id": "USPEC-001", "detail": "Seeded deterministic test counterexample"}],
        [{"path": "workproducts/SWE.3/unit_specifications.md"}, {"path": "software/hal/reg32.c"}],
        prior_strategies=[signature(prior)] if name == "reworded-strategy" else [],
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
    if name == "cross-case-reference":
        foreign_ws = p.ws.parent / "foreign-workspace"
        foreign_source = foreign_ws / "workproducts/SWE.3/unit_specifications.md"
        foreign_source.parent.mkdir(parents=True)
        foreign_source.write_text("Different seeded qualification case: do not import its register contract.\n")
        foreign_packet = P.seal(
            foreign_ws,
            {**p.bundle, "bundle_id": "qualification-foreign-case"},
            [{"id": "foreign", "obligation_id": "USPEC-FOREIGN", "detail": "A distinct fixture finding"}],
            [{"path": "workproducts/SWE.3/unit_specifications.md"}],
        )
        foreign_case = p.case.parent / "foreign-case.json"
        immutable_json(foreign_case, {"packet_ref": foreign_packet})
        p.manifest["jobs"]["unicode-contract:0"] = {
            "job_id": "afo-agent-" + "f" * 24,
            "case": str(foreign_case),
            "case_sha256": sha256_file(foreign_case),
            "mission_id": "qualification-only",
        }
        p.manifest["job_token_reservations"]["afo-agent-" + "f" * 24] = 32768
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


@pytest.mark.parametrize("name", sorted(F.RESPONSE))
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
    if name == "empty-output":
        assert changed == ""
        with pytest.raises(Refused, match="EMPTY_MODEL_OUTPUT") as incident:
            response_receipt(p.store, job, {"choices": [{"message": {"content": raw}}]}, p.eff)
        row["job_error"] = incident.value.code
        assert not Receipts(p.store).for_job(Context.from_job(p.store, job["job_id"]))
    else:
        receipt = response_receipt(p.store, job, {"choices": [{"message": {"content": raw}}]}, p.eff)
        if name in ("unqualified-local-alternative", "cross-case-reference", "reworded-strategy"):
            from forge_factory.afo.semantic_proposal import check

            expected = {
                "unqualified-local-alternative": "LOCAL_ALTERNATIVE_NOT_QUALIFIED_AND_AUTHORIZED",
                "cross-case-reference": "PROPOSAL_EVIDENCE_NOT_IN_CASE",
                "reworded-strategy": "SEMANTIC_STRATEGY_ALREADY_TRIED",
            }[name]
            with pytest.raises(Refused, match=expected):
                check(strict_json(changed), packet)
        else:
            assert receipt["submission_state"] == "REJECTED"
        row["receipt"] = Receipts(p.store).admit(
            receipt["receipt_id"],
            packet=packet,
            bundle=json.loads(p.case.read_text())["bundle"],
            eff=p.eff,
            authorize=lambda: True,
            auth_models=[job["model"]],
        )
    assert F.observation_matches(p.manifest, row)
    assert not F.observation_matches(p.manifest, {**row, "fault_observation": None})
    assert not F.observation_matches(p.manifest, {**row, "fault_observation": {**fact, "case_sha256": "0" * 64}})
    assert not F.observation_matches(
        p.manifest, {**row, "receipt": {"reason_codes": ["UNRELATED_DENIAL"]}, "job_error": "UNRELATED_DENIAL"}
    )
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


@pytest.mark.parametrize("name", sorted(F.PRIMARY))
def test_real_primary_intervention_rejects_evidence_and_replays_without_replacing_again(signed, name, monkeypatch):
    from forge_factory.afo.durable_agent import request_material

    p = signed
    job, _, _ = bind(p, name)
    before = p.ledger.snapshot("qualification-only")
    fact = F.apply_primary(p.store, job, p.eff)
    code = "EVIDENCE_MISSING_OR_CHANGED" if name == "stale-primary" else "EVIDENCE_PATH_ESCAPE"
    with pytest.raises(Refused, match=code) as incident:
        request_material(job)
    with monkeypatch.context() as guard:
        guard.setattr(F.os, "replace", lambda *a, **kw: pytest.fail("replay must adopt the existing intervention"))
        assert F.apply_primary(p.store, job, p.eff) == fact
    row = {
        "trial_id": name + ":0",
        "job_id": job["job_id"],
        "declared_fault": job["qualification_fault"],
        "execution": Executions(p.store).get(job["job_id"]),
        "fault_observation": fact,
        "job_error": incident.value.code,
    }
    assert F.observation_matches(p.manifest, row)
    assert not F.observation_matches(p.manifest, {**row, "fault_observation": {**fact, "path": "other.c"}})
    with p.store.tx() as c:
        assert (
            c.execute("SELECT COUNT(*) FROM afo_execution_evidence WHERE kind LIKE 'PROTOCOL_PRIMARY_FAULT%'").fetchone()[0] == 2
        )
    assert p.ledger.snapshot("qualification-only") == before


@pytest.mark.parametrize("name", sorted(F.PRIMARY))
@pytest.mark.parametrize("crash", ["before-replacement", "after-replacement"])
def test_primary_intervention_recovers_persisted_intent_across_effect_crashes(signed, name, crash, monkeypatch):
    p = signed
    job, _, _ = bind(p, name)
    original_record = F._record

    def record(store, jid, kind, value):
        if kind == "PROTOCOL_PRIMARY_FAULT":
            raise RuntimeError("simulated crash after atomic effect")
        return original_record(store, jid, kind, value)

    with monkeypatch.context() as injection:
        if crash == "before-replacement":

            def replace(*_):
                raise RuntimeError("simulated crash before atomic effect")

            injection.setattr(F.os, "replace", replace)
        else:
            injection.setattr(F, "_record", record)
        with pytest.raises(RuntimeError, match="simulated crash"):
            F.apply_primary(p.store, job, p.eff)
    with p.store.tx() as c:
        assert (
            c.execute("SELECT COUNT(*) FROM afo_execution_evidence WHERE kind='PROTOCOL_PRIMARY_FAULT_INTENT'").fetchone()[0] == 1
        )
        assert c.execute("SELECT COUNT(*) FROM afo_execution_evidence WHERE kind='PROTOCOL_PRIMARY_FAULT'").fetchone()[0] == 0
    fact = F.apply_primary(p.store, job, p.eff)
    assert F.apply_primary(p.store, job, p.eff) == fact


def test_primary_fault_cannot_follow_a_replaced_parent_or_alter_outside_content(signed, tmp_path):
    p = signed
    job, _, _ = bind(p, "stale-primary")
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "reg32.c"
    sentinel.write_text("EXTERNAL_SENTINEL_UNCHANGED")
    parent = p.ws / "software/hal"
    parent.rename(parent.with_name("original-hal"))
    parent.symlink_to(outside, target_is_directory=True)
    with pytest.raises(Refused, match="EVIDENCE_PATH_ESCAPE"):
        F.apply_primary(p.store, job, p.eff)
    assert sentinel.read_text() == "EXTERNAL_SENTINEL_UNCHANGED"


def test_fault_evidence_cannot_be_overwritten_after_storage_corruption(signed):
    p = signed
    job, raw, _ = bind(p, "administrative-forgery")
    F.apply_response(p.store, job, raw, p.eff)
    with p.store.tx() as c:
        c.execute("UPDATE afo_execution_evidence SET record='{}' WHERE kind='PROTOCOL_RESPONSE_FAULT'")
    with pytest.raises(Refused, match="QUALIFICATION_FAULT_EVIDENCE_CORRUPT"):
        F.apply_response(p.store, job, raw, p.eff)


@pytest.mark.parametrize("entry", ["oversized", "fifo"])
def test_primary_fault_refuses_non_regular_or_oversized_entries_without_blocking(signed, entry):
    import os

    p = signed
    job, _, _ = bind(p, "stale-primary")
    path = p.ws / F.PRIMARY_PATH
    path.unlink()
    if entry == "fifo":
        os.mkfifo(path)
    else:
        path.write_bytes(b"x" * (len(F.STALE_BYTES) + 1))
    with pytest.raises(Refused, match="QUALIFICATION_PRIMARY_ENTRY_CHANGED"):
        F.apply_primary(p.store, job, p.eff)


def test_escape_marker_cannot_follow_a_symlinked_state_subdirectory(signed, tmp_path, monkeypatch):
    p = signed
    job, _, _ = bind(p, "symlink-escape")
    outside = tmp_path / "outside-marker-root"
    outside.mkdir()
    (tmp_path / "marker-state").mkdir()
    (tmp_path / "marker-state/lrtx").symlink_to(outside, target_is_directory=True)
    # Context still resolves the real private job store and case; only the
    # destination root is replaced to exercise the intervention's path guard.
    monkeypatch.setattr(F, "state_dir", lambda: tmp_path / "marker-state")
    with pytest.raises(Refused, match="EVIDENCE_PATH_ESCAPE"):
        F.apply_primary(p.store, job, p.eff)
    assert not list(outside.iterdir())
    assert (p.ws / F.PRIMARY_PATH).read_text() == F.IMPLEMENTATION
