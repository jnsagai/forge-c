"""Canonical administrative binding consumes a correction, never a new engineering attempt."""
# ruff: noqa: F811
import copy
import json
from pathlib import Path

import pytest
from forge_factory.afo import maintainer as M
from forge_factory.afo import maintenance_binding as B
from forge_factory.afo.durable import Refused
from forge_factory.reliability.policy import load as cre_policy
from forge_factory.reliability.store import CREStore
from test_afo_local_autonomy import local, order  # noqa: F401
from test_afo_m5_maintainer import REPRO, SIG, factory  # noqa: F401
from test_afo_maintenance_rework import reject, setup_parent


def rejected(local, factory, monkeypatch, **kwargs):
    p = setup_parent(local, factory, monkeypatch, reproducer_source=REPRO,
                     signature='SYMPTOM_PRESENT:' + SIG, **kwargs)
    reject(p)
    assert not Path(p.case['src']).exists()
    return p


def test_exact_prefix_binding_runs_unchanged_triage_and_preserves_raw_evidence(local, factory, monkeypatch):
    p = rejected(local, factory, monkeypatch)
    d = M.case_dir(p.case['proposal_id'])
    paths = [d / n for n in ('case.json', 'submission.json', 'submission-receipt.json', 'reproducer/manifest.yaml')]
    original = {path: path.read_bytes() for path in paths}
    before = p.ledger.snapshot('retained-test')
    ref = B.prepare(p.store, p.job, p.eff, verification_fence=lambda: True)
    assert B.prepare(p.store, p.job, p.eff, verification_fence=lambda: True) == ref
    after = p.ledger.snapshot('retained-test')
    assert after['corrections'] == before['corrections'] + 1
    assert all(after[k] == before[k] for k in ('jobs', 'attempts', 'requests', 'charged_tokens', 'limits'))
    bound = B.bound_submission(p.store, p.case, p.sub, ref)
    assert json.loads(Path(bound['staged']['manifest']).read_text())['reproducers'][0]['symptom_signature'] == SIG
    assert bound['candidate'] == p.sub['candidate']
    def evaluate(*a, **k):
        return {'decision': 'ELIGIBLE_FOR_OFFLINE_REVIEW', 'decision_id': 'pd-unit-binding',
                'allowed_auto_deployment': False}
    result = M.process(p.store, p.case['proposal_id'], CREStore(), cre_policy(),
                       evaluator=evaluate, binding_ref=ref)
    assert result['outcome'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
    assert any(x == 'administrative-binding:' + ref['binding_id'] for x in result['evidence_refs'])
    # Actual existing triage ran the unchanged script on the baseline and required SYMPTOM_PRESENT.
    assert result['capa_id'] and result['reproducer_id'] == p.sub['staged']['id']
    assert all(path.read_bytes() == raw for path, raw in original.items())
    count = p.store.proposal(p.case['proposal_id'])['seq']
    assert M.process(p.store, p.case['proposal_id'], CREStore(), cre_policy(),
                     evaluator=lambda *a, **k: pytest.fail('must adopt the existing binding result'), binding_ref=ref) == result
    assert p.store.proposal(p.case['proposal_id'])['seq'] == count
    assert p.ledger.snapshot('retained-test') == after


@pytest.mark.parametrize('gate', ['fence', 'authority', 'live', 'corrections', 'job_rebound'])
def test_binding_refuses_without_remaining_correction_or_authority(local, factory, monkeypatch, gate):
    p = rejected(local, factory, monkeypatch)
    def fence():
        return gate != 'fence'
    job = copy.deepcopy(p.job)
    if gate == 'authority':
        from forge_factory.afo import local_agent
        monkeypatch.setattr(local_agent, 'authorized', lambda *a: False)
    elif gate == 'live':
        from forge_factory.afo.execution_lifecycle import Executions
        monkeypatch.setattr(Executions, 'pending', lambda *a: ['a-live-native'])
    elif gate == 'corrections':
        p.ledger.count('retained-test', job['job_id'], 'CORRECTION', 'already-used')
    elif gate == 'job_rebound':
        job['nonce'] = 'different'
    before = p.ledger.snapshot('retained-test')
    with pytest.raises(Refused):
        B.prepare(p.store, job, p.eff, verification_fence=fence)
    assert p.ledger.snapshot('retained-test') == before


def test_reference_rebinding_and_changed_manifest_are_refused(local, factory, monkeypatch):
    p = rejected(local, factory, monkeypatch)
    ref = B.prepare(p.store, p.job, p.eff, verification_fence=lambda: True)
    with pytest.raises(Refused):
        B.bound_submission(p.store, p.case, p.sub, {**ref, 'job_id': 'afo-agent-' + '0' * 24})
    path = M.case_dir(p.case['proposal_id']) / 'administrative-bindings' / ref['binding_id'] / 'manifest.yaml'
    path.chmod(0o600)
    path.write_text('{}')
    with pytest.raises(Refused):
        B.bound_submission(p.store, p.case, p.sub, ref)


def test_incomplete_binding_publication_reuses_one_correction(local, factory, monkeypatch):
    p = rejected(local, factory, monkeypatch)
    original = B.immutable_json

    def fail_ready(path, obj, *args):
        if path.name == 'ready.json':
            raise OSError('SYNTHETIC_BINDING_PUBLICATION_FAILURE')
        return original(path, obj, *args)

    with monkeypatch.context() as stopped:
        stopped.setattr(B, 'immutable_json', fail_ready)
        with pytest.raises(OSError, match='SYNTHETIC_BINDING_PUBLICATION_FAILURE'):
            B.prepare(p.store, p.job, p.eff, verification_fence=lambda: True)
    once = p.ledger.snapshot('retained-test')
    ref = B.prepare(p.store, p.job, p.eff, verification_fence=lambda: True)
    assert B.bound_submission(p.store, p.case, p.sub, ref)
    assert p.ledger.snapshot('retained-test') == once and once['corrections'] == 1


def test_different_baseline_marker_is_not_repaired_by_binding(local, factory, monkeypatch):
    p = setup_parent(local, factory, monkeypatch, reproducer_source=REPRO.replace(SIG, 'other-defect'),
                     signature='SYMPTOM_PRESENT:' + SIG)
    reject(p)
    before = p.ledger.snapshot('retained-test')
    with pytest.raises(Refused, match='NOT_ADMINISTRATIVE_ONLY'):
        B.prepare(p.store, p.job, p.eff, verification_fence=lambda: True)
    assert p.ledger.snapshot('retained-test') == before


def test_candidate_rejection_stays_rejected_and_reuses_genuine_capa_on_retry(local, factory, monkeypatch):
    p = rejected(local, factory, monkeypatch)
    ref = B.prepare(p.store, p.job, p.eff, verification_fence=lambda: True)
    cre = CREStore()
    from forge_factory.reliability.capa import CapaRegistry

    with pytest.raises(OSError, match='SYNTHETIC_VERIFIER_FAILURE'):
        M.process(p.store, p.case['proposal_id'], cre, cre_policy(), binding_ref=ref,
                  evaluator=lambda *a, **k: (_ for _ in ()).throw(OSError('SYNTHETIC_VERIFIER_FAILURE')))
    registry = CapaRegistry(cre, cre_policy())
    assert len(registry.all()) == 1
    assert registry.all()[0]['incident_ids'] == [p.order['order_id']]
    result = M.process(p.store, p.case['proposal_id'], cre, cre_policy(), binding_ref=ref,
                       evaluator=lambda *a, **k: {'decision': 'REJECTED', 'decision_id': 'pd-unit-rejection',
                                                 'allowed_auto_deployment': False})
    assert result['outcome'] == 'REJECTED' and len(registry.all()) == 1


def test_existing_review_worker_uses_binding_without_another_model_job(local, factory, monkeypatch):
    from forge_factory.afo import local_agent as L

    p = setup_parent(local, factory, monkeypatch, reproducer_source=REPRO,
                     signature='SYMPTOM_PRESENT:' + SIG)
    monkeypatch.setattr(M, 'evaluate', lambda *a, **k: {
        'decision': 'ELIGIBLE_FOR_OFFLINE_REVIEW', 'decision_id': 'pd-unit-auto-binding',
        'allowed_auto_deployment': False})
    before = p.ledger.snapshot('retained-test')
    result = L.review(p.store, p.job, p.eff, verification_fence=lambda: True)
    assert result['outcome'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
    assert result['administrative_binding']['binding_id']
    after = p.ledger.snapshot('retained-test')
    assert after['corrections'] == before['corrections'] + 1
    assert after['jobs'] == before['jobs'] and after['attempts'] == before['attempts']


def test_partial_reference_cannot_be_consumed_before_ready_publication(local, factory, monkeypatch):
    p = rejected(local, factory, monkeypatch)
    ref = B.prepare(p.store, p.job, p.eff, verification_fence=lambda: True)
    ready = M.case_dir(p.case['proposal_id']) / 'administrative-bindings' / ref['binding_id'] / 'ready.json'
    ready.unlink()
    with pytest.raises(Refused, match='REFERENCE_NOT_PUBLISHED'):
        B.bound_submission(p.store, p.case, p.sub, ref)
