"""CONTROL replay of existing native/submission/CRE chains, not model qualification.

The normal job, mission, native nonce/quiescence and isolated submission APIs are
used. Native responses and independent gate observations are deterministic test
fixtures; no live model/service/repair verifier is dispatched by the replay.
"""
# ruff: noqa: F811 - imported pytest fixtures are intentionally used by name
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import line_soak_claims as C
from forge_factory.afo import line_soak_prerequisites as P
from forge_factory.afo import local_agent as L
from forge_factory.afo import maintainer as M
from forge_factory.afo.durable import Refused, canonical, digest
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.common import utc_now
from forge_factory.reliability import promotion
from forge_factory.reliability.policy import load as cre_policy
from forge_factory.reliability.store import CREStore
from test_afo_m5_maintainer import SIG, _good_candidate
from test_line_maintenance import factory, local, order, prepare, terminal  # noqa: F401
from test_line_maintenance_dispatch import prepare_job
from test_line_soak_prerequisites import ref


@pytest.fixture
def offline(terminal, monkeypatch, tmp_path):
    from forge_factory import workorder
    from forge_factory.afo.execution_lifecycle import Executions
    from forge_factory.reliability import benchmark as BM

    case = prepare(terminal)
    monkeypatch.setattr(workorder, "factory_revision", lambda: {"commit": case["base"], "dirty": False})
    monkeypatch.setenv("FORGE_DURABLE_AUTONOMY", "1")
    job = prepare_job(terminal, case)
    store, oid, _, _, _ = terminal[0]
    _good_candidate(case)
    submission = M.submit(case, "CONTROL isolated addition correction", M.CANDIDATE_TESTS + "rpr_calc.py", SIG)
    client = SimpleNamespace(get_run=lambda _: {"lifecycle": {"status": {"kind": "SUCCEEDED"}}}, usage=lambda _: {})
    job = L.poll(store, store.order(oid), job, terminal[1], client=client, launch_fn=lambda _: "CONTROL-native-maintainer")
    job = L.poll(store, store.order(oid), job, terminal[1], client=client)
    assert job["state"] == "SUCCEEDED", job
    assert Executions(store).get(job["job_id"])["resource_lease"] == "RELEASED"
    registry = CREStore()
    policy = cre_policy()
    gates = ["protected_files", "policy_integrity", "reproducer", "prevention", "quality_process", "golden_benchmark", "holdout"]
    decision = {"schema_version": "1.0", "decision_id": "pd-control-soak-replay", "candidate_sha256": promotion.tree_sha256(submission["candidate"], Path(case["repo"])),
                "baseline_sha256": promotion.tree_sha256(case["base"], Path(case["repo"])), "policy_sha256": policy.sha256,
                "benchmark_sha256": BM.suite_sha256(*BM.SUITES.values()), "decision": "ELIGIBLE_FOR_OFFLINE_REVIEW",
                "evaluator_id": "CONTROL-independent-stub", "evaluator_kind": "INDEPENDENT_DETERMINISTIC_RUNNER",
                "evaluated_at": utc_now(), "hard_gates": [promotion._gate(g, "PASS", ["CONTROL-only:observed"]) for g in gates],
                "reasons": ["CONTROL-only: stub independent outcomes, not a real CRE qualification"], "allowed_auto_deployment": False}
    assert promotion.schema_errors(decision) == []
    with registry.conn() as c:
        c.execute("INSERT INTO cre_promotion_decisions VALUES (?,?,?,?,?,?)", (decision["decision_id"], submission["candidate"], case["base"],
                  decision["decision"], canonical(decision).decode(), decision["evaluated_at"]))
    M.record(store, case, submission, decision["decision"], decision["decision"], promotion_id=decision["decision_id"],
             tests_ref="local-agent:" + job["job_id"])
    claim = {"kind": "maintenance", "job_id": job["job_id"], "proposal_id": case["proposal_id"],
             "decision_ref": ref(tmp_path / "decision.json", decision)}
    return SimpleNamespace(store=store, registry=registry, case=case, job=job, claim=claim,
                           manifest={"source_revision": case["base"]}, decision=decision)


def test_native_and_independent_offline_candidate_chain_is_replayed_without_competence_claim(offline):
    o = offline
    before = o.store.proposal(o.case["proposal_id"])
    with ReadSnapshot(o.store.path, timeout_s=3) as reader:
        rows = P._claims([o.claim], o.manifest, reader)
    assert rows == [{"kind": "maintenance", "decision_sha256": digest(o.decision),
                     "source_deployed": False, "role_qualification_inferred": False, "repair_benefit_inferred": False,
                     "scope": "OFFLINE_CANDIDATE_ELIGIBILITY_ONLY"}]
    assert o.store.proposal(o.case["proposal_id"]) == before


@pytest.mark.parametrize("changed", ["native", "case", "receipt", "decision", "source", "role"])
def test_offline_claim_tamper_is_refused_without_any_repair_dispatch(offline, changed):
    o = offline
    if changed == "case":
        path = Path(o.job["case"])
        path.chmod(0o600)
        path.write_text("{}")
    elif changed == "receipt":
        path = Path(o.job["case"]).parent / "submission-receipt.json"
        path.chmod(0o600)
        path.write_text("{}")
    elif changed == "decision":
        path = Path(o.claim["decision_ref"]["path"])
        path.chmod(0o600)
        path.write_text("{}")
    elif changed == "source":
        o.manifest["source_revision"] = "0" * 40
    else:
        job = dict(o.job)
        if changed == "native":
            job["run_id"] = "foreign-native"
        else:
            job["role"] = "afo-recovery-planner"
        L.save(o.store, job)
    with ReadSnapshot(o.store.path, timeout_s=3) as reader:
        with pytest.raises((Refused, M.MaintainerDenied, KeyError)):
            C.maintenance(o.claim, o.manifest, reader)


def test_bounded_historical_holdout_preserves_matching_provenance(tmp_path):
    from forge_factory.knowledge.qualification import historical_holdout_refs
    evidence = tmp_path / "evidence"
    (evidence / "nested").mkdir(parents=True)
    (evidence / "z.json").write_text(json.dumps({"holdout": "WO-CONTROL"}))
    (evidence / "nested/a.json").write_text(json.dumps({"holdouts": ["/runs/WO-CONTROL/workspace"]}))
    (evidence / "other.json").write_text(json.dumps({"holdout": "WO-OTHER"}))
    expected = historical_holdout_refs("WO-CONTROL", root=tmp_path)
    assert len(expected) == 2
    assert historical_holdout_refs("WO-CONTROL", root=tmp_path, bounds=C.HISTORY_BOUNDS) == expected


@pytest.mark.parametrize("kind", ["non-json-entries", "large-file", "total-bytes", "symlink", "time"])
def test_overbound_historical_evidence_never_becomes_training(tmp_path, monkeypatch, kind):
    from forge_factory.knowledge import qualification as K
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    bound = dict(C.HISTORY_BOUNDS)
    if kind == "non-json-entries":
        bound["max_entries"] = 2
        for n in range(3):
            (evidence / str(n)).mkdir()
    elif kind == "symlink":
        (evidence / "foreign").symlink_to(tmp_path)
    elif kind == "time":
        values = iter([0, 10])
        monkeypatch.setattr(K.time, "monotonic", lambda: next(values))
    else:
        bound["max_file_bytes"] = 1000
        bound["max_bytes"] = 1000
        if kind == "large-file":
            (evidence / "a.json").write_text("x" * 1001)
        else:
            (evidence / "a.json").write_text("x" * 600)
            (evidence / "b.json").write_text("x" * 600)
    with pytest.raises(Refused):
        K.historical_holdout_refs("WO-CONTROL", root=tmp_path, bounds=bound)


@pytest.mark.parametrize("last_step", ["decode-match", "empty-traversal"])
def test_bounded_history_refuses_deadline_crossed_in_last_processing_step(tmp_path, monkeypatch, last_step):
    from forge_factory.knowledge import qualification as K
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    clock = [0]
    monkeypatch.setattr(K.time, "monotonic", lambda: clock[0])
    if last_step == "decode-match":
        (evidence / "a.json").write_text(json.dumps({"holdout": "WO-CONTROL"}))
        original = K.json.loads
        def decode(raw):
            result = original(raw)
            clock[0] = 10
            return result
        monkeypatch.setattr(K.json, "loads", decode)
    else:
        original = K.os.scandir
        class Entries:
            def __enter__(self):
                return self
            def __iter__(self):
                with original(evidence) as entries:
                    yield from entries
                clock[0] = 10  # Directory became overbound at iterator exhaustion.
            def __exit__(self, *args):
                return False
        monkeypatch.setattr(K.os, "scandir", lambda _: Entries())
    with pytest.raises(Refused, match="HISTORY_TIME_BOUND_EXCEEDED"):
        K.historical_holdout_refs("WO-CONTROL", root=tmp_path, bounds=C.HISTORY_BOUNDS)
