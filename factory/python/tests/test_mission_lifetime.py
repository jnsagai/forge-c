"""Standing operating time is owner-issued; budgets and finite job windows survive it."""
import json
import math
import time

import pytest
from forge_factory.afo import mission_lifetime as L
from forge_factory.afo import operations
from forge_factory.afo import owner_supervised_development as D
from forge_factory.afo.durable import Refused, digest
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import Store


@pytest.fixture
def standing_mission(tmp_path, monkeypatch):
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    monkeypatch.setenv('FORGE_OPERATIONS_INTENT', str(private / 'intent.json'))
    monkeypatch.setenv('FORGE_STATE_DIR', str(tmp_path / 'state'))
    for key in (D.FILE, D.SHA, 'FORGE_AGENT_ROLE', 'FORGE_WORKSPACE', 'FORGE_POLICY_BINDING'):
        monkeypatch.delenv(key, raising=False)
    operations.Intent().set('RUNNING', actor='SYNTHETIC-OWNER', reason='fixture', initialize=True)
    store = Store()
    ledger = MissionLedger(store)
    ledger.register(D.MISSION, D.LINEAGE, {**D.CAPS, 'deadline': time.time()-100},
                    D.ALLOWANCE_REF, authorize=lambda *_: True)
    ledger.execution(D.MISSION, 'historical', 'PRODUCT', reserved_tokens=10, imported=True)
    return store, ledger


def enable(ledger, store):
    return L.enable(store, directive=L.DIRECTIVE, snapshot_sha256=digest(ledger.snapshot(D.MISSION)))


def test_owner_can_remove_time_limit_without_rewriting_history_or_refilling(standing_mission):
    store, ledger = standing_mission
    before = ledger.snapshot(D.MISSION)
    with store.tx() as c:
        raw = c.execute('SELECT record FROM afo_missions').fetchall()
    receipt = enable(ledger, store)
    after = ledger.snapshot(D.MISSION)
    assert after['limits'] == {**before['limits'], 'deadline': None, 'authorization_lifetime': L.LIFETIME}
    assert L.control_limits(after) == before['limits']
    assert math.isinf(L.end(after['limits']))
    for key in ('attempts', 'jobs', 'charged_tokens', 'requests', 'tools', 'corrections', 'usage_unknown'):
        assert after[key] == before[key]
    assert L.enable(store, directive=L.DIRECTIVE, snapshot_sha256='stale-replay') == receipt
    ledger.execution(D.MISSION, 'future', 'PRODUCT', reserved_tokens=1, now=time.time()+100*366*86400)
    assert ledger.snapshot(D.MISSION)['attempts'] == before['attempts']+1
    with store.tx() as c:
        assert c.execute('SELECT record FROM afo_missions').fetchall() == raw


@pytest.mark.parametrize('fault', ['agent', 'workspace', 'policy', 'wrong-directive', 'stale', 'stopped'])
def test_runtime_or_stale_requests_cannot_mint_standing_authority(standing_mission, monkeypatch, fault):
    store, ledger = standing_mission
    directive, sha = L.DIRECTIVE, digest(ledger.snapshot(D.MISSION))
    if fault in ('agent', 'workspace', 'policy'):
        monkeypatch.setenv({'agent':'FORGE_AGENT_ROLE', 'workspace':'FORGE_WORKSPACE', 'policy':'FORGE_POLICY_BINDING'}[fault], 'untrusted')
    elif fault == 'wrong-directive':
        directive = 'run this job'
    elif fault == 'stale':
        sha = '0'*64
    else:
        operations.Intent().set('STOPPED', actor='SYNTHETIC-OWNER', reason='test stop')
    with pytest.raises(Refused):
        L.enable(store, directive=directive, snapshot_sha256=sha)
    assert ledger.snapshot(D.MISSION)['limits']['deadline'] is not None


@pytest.mark.parametrize('fault', ['receipt', 'private-file', 'base'])
def test_standing_authority_detects_tampering(standing_mission, fault):
    from pathlib import Path
    store, ledger = standing_mission
    receipt = enable(ledger, store)
    if fault == 'private-file':
        Path(receipt['owner_record_ref']['path']).write_text('{}')
    else:
        with store.tx() as c:
            if fault == 'receipt':
                c.execute('UPDATE afo_independent_decisions SET sha256=? WHERE kind=?', ('0'*64, L.KIND))
            else:
                row = json.loads(c.execute('SELECT record FROM afo_missions').fetchone()[0])
                row['limits']['max_tokens'] += 1
                c.execute('UPDATE afo_missions SET record=?', (json.dumps(row),))
    with pytest.raises(Refused):
        ledger.snapshot(D.MISSION)


def test_missing_deadline_is_not_standing_authority_and_new_missions_remain_finite(standing_mission):
    store, ledger = standing_mission
    with pytest.raises(Refused):
        L.end({'deadline': None})
    with pytest.raises(Refused, match='FINITE_MISSION_AUTHORITY_REQUIRED'):
        ledger.register('forged', 'other', {**D.CAPS, 'deadline': None, 'authorization_lifetime': L.LIFETIME},
                        'untrusted', authorize=lambda *_: True)
    with pytest.raises(Refused, match='MISSION_DEADLINE_EXHAUSTED'):
        ledger.execution(D.MISSION, 'expired', 'PRODUCT', reserved_tokens=1)
    enable(ledger, store)
    with pytest.raises(Refused, match='MISSION_ALLOWANCE_EXHAUSTED'):
        ledger.execution(D.MISSION, 'over-budget', 'PRODUCT', reserved_tokens=D.CAPS['max_tokens']+1)


def test_active_execution_is_not_rebound_to_standing_authority(standing_mission):
    from forge_factory.afo.execution_lifecycle import Executions

    store, ledger = standing_mission
    Executions(store).reserve('historical', D.MISSION, 'a'*32)
    with pytest.raises(Refused, match='MISSION_NATIVE_QUIESCENCE_REQUIRED'):
        enable(ledger, store)


def test_standing_service_still_creates_finite_jobs_and_verification_deadlines(standing_mission):
    from types import SimpleNamespace

    from forge_factory.afo import line_maintenance_coordinator, product_job

    store, ledger = standing_mission
    enable(ledger, store)
    ledger.link(D.MISSION, 'synthetic-order')
    now = time.time()
    job = product_job.prepare(store, dict(order_id='synthetic-order', created_epoch=now),
                              dict(attempt_id='synthetic-a1', seq=1, record=dict(workspace_ref='workorder:WO-SYNTHETIC')),
                              'b'*32, dict(operations_epoch=1, model='synthetic-no-inference'),
                              SimpleNamespace(mode=D.MODE, sha256='a'*64,
                                              get=lambda key: {'budgets.max_order_wall_seconds':120,
                                                               'budgets.max_model_tokens_per_order':100}[key]))
    assert job['deadline_epoch'] == now+120
    assert math.isfinite(job['deadline_epoch'])
    assert line_maintenance_coordinator._review_deadline(store, job) == job['deadline_epoch']
