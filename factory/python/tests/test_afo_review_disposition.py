"""Real Maintainer records must survive the independent review worker boundary."""
# ruff: noqa: F811
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import local_agent as L
from forge_factory.afo import maintainer as M
from forge_factory.afo import policy
from forge_factory.afo.queue import Store
from test_afo_m5_maintainer import SIG, _case, _good_candidate, _head, factory  # noqa: F401


def setup_review(factory, monkeypatch, *, valid=True):
    store = Store()
    case = _case(factory)
    _good_candidate(case)
    if not valid:
        M.write_source(case, M.CANDIDATE_TESTS + 'rpr_calc.py', 'print("SYMPTOM_ABSENT")\n')
    sub = M.submit(case, 'repair calc arithmetic', M.CANDIDATE_TESTS + 'rpr_calc.py', SIG)
    eff = SimpleNamespace(sha256='same-policy', get=lambda key, default=None:
                          {'maintenance.enable_factory_maintainer': True,
                           'maintenance.allow_proposal_pr': False}.get(key, default))
    monkeypatch.setattr(L, 'authorized', lambda *a: True)
    monkeypatch.setattr(policy, 'load', lambda: eff)
    monkeypatch.setattr(M, 'evaluate', lambda *a, **kw: {
        'decision': 'ELIGIBLE_FOR_OFFLINE_REVIEW', 'decision_id': 'pd-fixture', 'allowed_auto_deployment': False})
    job = {'job_id': 'afo-agent-' + '1' * 24, 'order_id': 'synthetic-order',
           'case': str(M.case_dir(case['proposal_id']) / 'case.json'),
           'policy_sha256': eff.sha256, 'deadline_epoch': time.time() + 60}
    return store, case, sub, eff, job


def test_real_rejected_record_is_a_rejected_review_not_a_keyerror(factory, monkeypatch):
    store, case, sub, eff, job = setup_review(factory, monkeypatch, valid=False)
    result = L.review(store, job, eff)
    projection = store.proposal(case['proposal_id'])
    assert result['status'] == projection['status'] == 'REJECTED'
    assert result['outcome'] == 'REJECTED' and not Path(case['src']).exists()
    assert result['candidate_commit'] == sub['candidate']
    assert 'status' not in projection['record']  # versioned record contract remains unchanged


def test_real_eligible_record_reaches_existing_branch_broker_without_deployment(factory, monkeypatch):
    store, case, sub, eff, job = setup_review(factory, monkeypatch)
    before = _head(factory, 'main')
    result = L.review(store, job, eff)
    projection = store.proposal(case['proposal_id'])
    assert result['status'] == projection['status'] == 'PUBLISHED'
    assert result['outcome'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
    assert result['auto_deployment_allowed'] is False and result['pr_url'] is None
    assert _head(factory, result['branch_ref']) == sub['candidate']
    assert _head(factory, 'main') == before
    assert 'status' not in projection['record']


def test_eligible_review_still_requires_current_verification_fence(factory, monkeypatch):
    store, case, sub, eff, job = setup_review(factory, monkeypatch)
    with pytest.raises(RuntimeError, match='VERIFICATION_PUBLICATION_FENCED'):
        L.review(store, job, eff, verification_fence=lambda: False)
    assert store.proposal(case['proposal_id'])['status'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
    assert not M._git('branch', '--list', 'afo/proposal/*', cwd=factory).strip()


def test_changed_owner_policy_prevents_publication_but_preserves_eligible_record(factory, monkeypatch):
    store, case, sub, eff, job = setup_review(factory, monkeypatch)
    monkeypatch.setattr(policy, 'load', lambda: SimpleNamespace(sha256='newer-policy'))
    result = L.review(store, job, eff)
    assert result['status'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
    assert not M._git('branch', '--list', 'afo/proposal/*', cwd=factory).strip()


@pytest.mark.parametrize('failure', [M.MaintainerDenied('PUSH_FAILED', 'private transport detail'), OSError('private path')])
def test_publication_failure_preserves_independent_eligibility_without_leaking_details(factory, monkeypatch, failure):
    store, case, sub, eff, job = setup_review(factory, monkeypatch)
    monkeypatch.setattr(M, 'publish', lambda *a: (_ for _ in ()).throw(failure))
    result = L.review(store, job, eff)
    assert result['status'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
    assert result['publication'] == {'status': 'BLOCKED', 'code': getattr(failure, 'code', type(failure).__name__)}
    assert store.proposal(case['proposal_id'])['status'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
    assert 'private' not in str(result['publication'])
    assert result['auto_deployment_allowed'] is False
