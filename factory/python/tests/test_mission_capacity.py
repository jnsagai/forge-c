"""Owner administration must not turn a new order/grant into forgotten historical expenditure."""
import json
import subprocess
import time
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from forge_factory.afo import authz, policy
from forge_factory.afo import mission_capacity as C
from forge_factory.afo import mission_deadline as D
from forge_factory.afo.durable import Refused, digest
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.queue import Store
from forge_factory.common import REPO_ROOT, load_yaml

REAL_VERIFY = authz.verify


@pytest.fixture
def mission(tmp_path, monkeypatch):
    monkeypatch.setenv('FORGE_STATE_DIR', str(tmp_path / 'state'))
    monkeypatch.delenv('FORGE_OPERATIONS_INTENT', raising=False)
    root = tmp_path / 'auth'
    root.mkdir()
    monkeypatch.setattr(authz, 'AUTH_DIR', root)
    monkeypatch.setattr(authz, 'verify', lambda *a, **k: SimpleNamespace(allow=True, code='FIXTURE_ONLY'))
    store = Store()
    ledger = MissionLedger(store)
    limits = dict(max_attempts=3, max_jobs=4, max_requests=32, max_tokens=120000,
                  max_tools=32, max_corrections=1, deadline=time.time() - 100)
    ledger.register('rcc', 'same:rcc:objective', limits, 'AUTH-OLD', authorize=lambda *a: True)
    ledger.execution('rcc', 'old1', 'PRODUCT', reserved_tokens=42000, imported=True)
    ledger.execution('rcc', 'old2', 'PRODUCT', reserved_tokens=44000, imported=True)
    base = load_yaml(REPO_ROOT / 'config/factory/afo-policy.yaml')
    base['budgets'].update(max_order_attempts=20, max_recovery_model_calls_per_order=20,
                           max_model_tokens_per_order=20000000, max_inference_requests_per_order=1000,
                           max_tool_calls_per_order=1000)
    eff = policy.Effective('PILOT', 'PILOT', 'c' * 64, base)
    doc = {'schema': C.SCHEMA, 'mission_id': 'rcc', 'snapshot_sha256': digest(ledger.snapshot('rcc')),
           'limits': dict(max_attempts=20, max_jobs=20, max_requests=1000, max_tokens=20000000,
                          max_tools=1000, max_corrections=1), 'authorization_ref': 'AUTH-CAPACITY-FIXTURE',
           'request': {'order_id': 'same-rcc-continuation', 'driver_class': 'LL', 'model': 'local'},
           'reason': 'Synthetic operator amendment, not actual owner authority', 'operator_epoch': 0}

    def grant(value, prefix='mission-capacity-amendment-014:'):
        record = {'authorization_id': value['authorization_ref'],
                  'expires_utc': datetime.fromtimestamp(time.time() + 1200, UTC).isoformat(),
                  'signed_runbook_ref': prefix + digest(value)}
        (root / (value['authorization_ref'] + '.json')).write_text(json.dumps(record))
        return record

    grant(doc)
    return SimpleNamespace(store=store, ledger=ledger, doc=doc, eff=eff, root=root, grant=grant)


def test_explicit_capacity_keeps_history_unknown_and_expired_time(mission):
    m = mission
    before = m.ledger.snapshot('rcc')
    with m.store.tx() as c:
        raw = c.execute("SELECT record FROM afo_missions WHERE mission_id='rcc'").fetchone()[0]
    receipt = C.amend(m.store, m.doc, m.eff)
    after = m.ledger.snapshot('rcc')
    assert after['limits'] == {**before['limits'], **m.doc['limits']}
    assert after['initial_limits'] == before['limits']
    assert after['authorization_ref'] == before['authorization_ref']
    assert receipt['native_effects'] is False and receipt['orders_reopened'] is False
    assert receipt['allowance_counters_reset'] is False and receipt['deadline_changed'] is False
    for field in ('attempts', 'jobs', 'requests', 'tools', 'corrections', 'charged_tokens',
                  'unique_executions', 'usage_unknown', 'unbounded_historical_usage'):
        assert after[field] == before[field]
    with m.store.tx() as c:
        assert c.execute("SELECT record FROM afo_missions WHERE mission_id='rcc'").fetchone()[0] == raw
    assert C.amend(m.store, m.doc, m.eff) == receipt
    with pytest.raises(Refused, match='DEADLINE'):
        m.ledger.execution('rcc', 'new', 'PRODUCT', reserved_tokens=1000000)
    assert m.ledger.snapshot('rcc') == after


@pytest.mark.parametrize('first', ['time', 'capacity'])
def test_time_and_capacity_are_separate_signed_receipts_and_charge_new_work(mission, first):
    m = mission
    time_doc = {'schema': D.SCHEMA, 'mission_id': 'rcc', 'snapshot_sha256': '',
                'deadline_epoch': time.time() + 600, 'authorization_ref': 'AUTH-TIME-FIXTURE',
                'request': m.doc['request'], 'reason': 'Synthetic separate time-only grant'}
    for action in ([D.extend, C.amend] if first == 'time' else [C.amend, D.extend]):
        document = time_doc if action is D.extend else m.doc
        document['snapshot_sha256'] = digest(m.ledger.snapshot('rcc'))
        m.grant(document, 'mission-deadline-extension-014:' if action is D.extend
                else 'mission-capacity-amendment-014:')
        action(m.store, document, m.eff)
    after = m.ledger.snapshot('rcc')
    assert len(after['capacity_amendments']) == len(after['deadline_extensions']) == 1
    assert after['charged_tokens'] == 86000 and after['attempts'] == 2 and after['usage_unknown']
    m.ledger.execution('rcc', 'new', 'PRODUCT', reserved_tokens=1000000)
    current = m.ledger.snapshot('rcc')
    assert current['charged_tokens'] == 1086000 and current['attempts'] == 3
    assert current['initial_limits']['max_tokens'] == 120000
    with pytest.raises(Refused, match='RESET_FORBIDDEN'):
        m.ledger.register('fresh-rcc', 'same:rcc:objective', current['limits'], 'AUTH-NEW', authorize=lambda *a: True)


@pytest.mark.parametrize('count,cap', list((v, k) for k, v in C.CAPS.items()))
def test_exhausted_non_time_allowance_cannot_be_reopened(mission, monkeypatch, count, cap):
    m = mission
    original = MissionLedger._snapshot

    def snapshot(c, mid):
        value = original(c, mid)
        return {**value, count: value['limits'][cap]}

    monkeypatch.setattr(MissionLedger, '_snapshot', staticmethod(snapshot))
    m.doc['snapshot_sha256'] = digest(m.ledger.snapshot('rcc'))
    m.grant(m.doc)
    with pytest.raises(Refused, match='NON_TIME_ALLOWANCE_EXHAUSTED'):
        C.amend(m.store, m.doc, m.eff)
    with m.store.tx() as c:
        assert C.records(c, 'rcc') == []


@pytest.mark.parametrize('fault,code', [
    ('unbounded', 'NON_TIME_ALLOWANCE_EXHAUSTED'), ('snapshot', 'SNAPSHOT_CHANGED'),
    ('ordinary-grant', 'NOT_OWNER_SIGNED'), ('policy', 'EXCEEDS_POLICY'),
    ('smaller', 'NOT_PROSPECTIVE'), ('correction', 'NOT_PROSPECTIVE'),
    ('live', 'QUIESCENCE_REQUIRED'), ('prepared', 'QUIESCENCE_REQUIRED'),
    ('missing', 'AUTH_RECORD_MISSING'), ('broken', 'AUTH_NOT_JSON'), ('not-object', 'AUTH_SCHEMA_INVALID'),
    ('denied', 'FIXTURE_REVOKED'), ('extra-time', 'INPUT_INVALID')])
def test_current_authority_scope_quiescence_and_snapshot_are_required(mission, monkeypatch, fault, code):
    m = mission
    if fault == 'unbounded':
        m.ledger.execution('rcc', 'unknown', 'DIAGNOSIS', reserved_tokens=0, imported=True)
        m.doc['snapshot_sha256'] = digest(m.ledger.snapshot('rcc'))
    elif fault == 'snapshot':
        m.doc['snapshot_sha256'] = '0' * 64
    elif fault == 'ordinary-grant':
        value = m.grant(m.doc)
        value['signed_runbook_ref'] = 'ordinary-live-job'
        (m.root / (m.doc['authorization_ref'] + '.json')).write_text(json.dumps(value))
    elif fault == 'policy':
        m.doc['limits']['max_tokens'] += 1
    elif fault == 'smaller':
        m.doc['limits']['max_tools'] = 31
    elif fault == 'correction':
        m.doc['limits']['max_corrections'] = 2
    elif fault == 'live':
        m.ledger.execution('rcc', 'live', 'MAINTENANCE', reserved_tokens=1, imported=True)
        Executions(m.store).reserve('live', 'rcc', 'a' * 32)
        m.doc['snapshot_sha256'] = digest(m.ledger.snapshot('rcc'))
    elif fault == 'prepared':
        with m.store.tx() as c:
            c.execute('INSERT INTO afo_local_agent_jobs VALUES (?,?,?,?,?,?)',
                      ('j', 'o', 'a', 'afo-factory-maintainer', 'PREPARED',
                       json.dumps({'mission_id': 'rcc', 'state': 'PREPARED'})))
    elif fault == 'missing':
        (m.root / (m.doc['authorization_ref'] + '.json')).unlink()
    elif fault in ('broken', 'not-object'):
        (m.root / (m.doc['authorization_ref'] + '.json')).write_text('{' if fault == 'broken' else '[]')
    elif fault == 'denied':
        monkeypatch.setattr(authz, 'verify', lambda *a, **k: SimpleNamespace(allow=False, code='FIXTURE_REVOKED'))
    elif fault == 'extra-time':
        m.doc['deadline_epoch'] = time.time() + 600
    if fault in ('unbounded', 'snapshot', 'policy', 'smaller', 'correction', 'extra-time', 'live'):
        m.grant(m.doc)
    before = m.ledger.snapshot('rcc')
    with pytest.raises(Refused, match=code):
        C.amend(m.store, m.doc, m.eff)
    assert m.ledger.snapshot('rcc') == before


def test_intent_epoch_fences_pause_and_newer_resume(mission, tmp_path, monkeypatch):
    from forge_factory.afo.operations import Intent

    root = tmp_path / 'operator'
    root.mkdir(mode=0o700)
    monkeypatch.setenv('FORGE_OPERATIONS_INTENT', str(root / 'operations.json'))
    intent = Intent()
    intent.set('RUNNING', actor='fixture', reason='fixture only', initialize=True)
    m = mission
    m.doc['operator_epoch'] = 1
    m.grant(m.doc)
    intent.set('PAUSED', actor='fixture', reason='newer operator pause')
    with pytest.raises(Refused, match='OPERATIONS_CAPACITY_FENCED'):
        C.amend(m.store, m.doc, m.eff)
    intent.set('RUNNING', actor='fixture', reason='later resume')
    with pytest.raises(Refused, match='OPERATIONS_CAPACITY_FENCED'):
        C.amend(m.store, m.doc, m.eff)
    m.doc['operator_epoch'] = 3
    m.grant(m.doc)
    C.amend(m.store, m.doc, m.eff)


def test_receipt_replay_is_historical_and_corruption_blocks_accounting(mission, monkeypatch):
    m = mission
    receipt = C.amend(m.store, m.doc, m.eff)
    after = m.ledger.snapshot('rcc')
    monkeypatch.setattr(authz, 'verify', lambda *a, **k: SimpleNamespace(allow=False, code='FIXTURE_REVOKED'))
    assert C.amend(m.store, m.doc, m.eff) == receipt and m.ledger.snapshot('rcc') == after
    with m.store.tx() as c:
        c.execute('UPDATE afo_independent_decisions SET sha256=? WHERE kind=?', ('0' * 64, C.KIND))
    with pytest.raises(Refused, match='CAPACITY_HISTORY_CHANGED'):
        m.ledger.snapshot('rcc')


def test_real_public_signature_is_required_for_exact_document(mission, tmp_path, monkeypatch):
    m = mission
    key = tmp_path / 'fixture-key'
    subprocess.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(key)], check=True)
    signers = tmp_path / 'allowed-signers'
    signers.write_text('FixtureOwner ' + key.with_suffix('.pub').read_text())
    monkeypatch.setattr(authz, 'ALLOWED_SIGNERS', signers)
    record = {'schema_version': '1.0', 'authorization_id': m.doc['authorization_ref'], 'approver': 'FixtureOwner',
              'approval_evidence_ref': 'SYNTHETIC_TEST_KEY_NOT_OWNER_AUTHORITY',
              'issued_utc': datetime.fromtimestamp(time.time() - 10, UTC).isoformat(),
              'expires_utc': datetime.fromtimestamp(time.time() + 1200, UTC).isoformat(),
              'policy_sha256': m.eff.sha256, 'mode': 'PILOT', 'allowed_actions': ['recover_workorder'],
              'scope': {'order_ids': ['same-rcc-continuation'], 'driver_classes': ['LL'], 'models': ['local']},
              'signature_ref': m.doc['authorization_ref'] + '.sig',
              'signed_runbook_ref': 'mission-capacity-amendment-014:' + digest(m.doc)}
    path = m.root / (m.doc['authorization_ref'] + '.json')
    path.write_text(json.dumps(record))
    authz.sign(path, key)
    monkeypatch.setattr(authz, 'verify', REAL_VERIFY)
    m.doc['limits']['max_tokens'] -= 1
    with pytest.raises(Refused, match='NOT_OWNER_SIGNED'):
        C.amend(m.store, m.doc, m.eff)
    m.doc['limits']['max_tokens'] += 1
    assert C.amend(m.store, m.doc, m.eff)['allowance_counters_reset'] is False


def test_actual_charged_exhaustion_is_not_revived_by_a_new_grant(mission):
    m = mission
    m.ledger.execution('rcc', 'spent-maintenance', 'MAINTENANCE', reserved_tokens=34000, imported=True)
    before = m.ledger.snapshot('rcc')
    assert before['charged_tokens'] == before['limits']['max_tokens'] == 120000
    m.doc['snapshot_sha256'] = digest(before)
    m.grant(m.doc)
    with pytest.raises(Refused, match='NON_TIME_ALLOWANCE_EXHAUSTED'):
        C.amend(m.store, m.doc, m.eff)
    assert m.ledger.snapshot('rcc') == before


def test_amendment_chain_has_a_hard_bound_and_preserves_original_caps(mission):
    m = mission
    for n in range(8):
        m.doc['limits']['max_tokens'] = 1000000 + n
        m.doc['snapshot_sha256'] = digest(m.ledger.snapshot('rcc'))
        m.doc['authorization_ref'] = f'AUTH-CAP-FIXTURE-{n}'
        m.grant(m.doc)
        C.amend(m.store, m.doc, m.eff)
    before = m.ledger.snapshot('rcc')
    assert before['initial_limits']['max_tokens'] == 120000
    assert len(before['capacity_amendments']) == 8 and before['charged_tokens'] == 86000
    m.doc['limits']['max_tokens'] += 1
    m.doc['snapshot_sha256'] = digest(before)
    m.doc['authorization_ref'] = 'AUTH-CAP-FIXTURE-EXCESS'
    m.grant(m.doc)
    with pytest.raises(Refused, match='AMENDMENT_LIMIT'):
        C.amend(m.store, m.doc, m.eff)
    assert m.ledger.snapshot('rcc') == before


def test_authenticated_cli_requires_owner_account_and_reason(mission, tmp_path, monkeypatch, capsys):
    from forge_factory.afo import cli

    m = mission
    document = tmp_path / 'capacity.json'
    document.write_text(json.dumps(m.doc))
    monkeypatch.setattr(cli, 'Store', lambda: m.store)
    monkeypatch.setattr(cli, 'load', lambda: m.eff)
    monkeypatch.setattr(cli, 'operator_ok', lambda: False)
    before = m.ledger.snapshot('rcc')
    args = ['mission-amend-capacity', str(document), '--reason', 'Synthetic owner decision']
    assert cli.main(args) == 3
    assert m.ledger.snapshot('rcc') == before
    monkeypatch.setattr(cli, 'operator_ok', lambda: True)
    assert cli.main(args[:2]) == 3
    assert m.ledger.snapshot('rcc') == before
    capsys.readouterr()
    assert cli.main(args) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt['native_effects'] is False and receipt['deadline_changed'] is False


def test_rehashed_but_broken_capacity_chain_is_rejected(mission):
    m = mission
    C.amend(m.store, m.doc, m.eff)
    with m.store.tx() as c:
        row = c.execute('SELECT decision_id,record FROM afo_independent_decisions WHERE kind=?', (C.KIND,)).fetchone()
        record = json.loads(row['record'])
        record['old_limits']['max_tokens'] += 1
        c.execute('UPDATE afo_independent_decisions SET record=?,sha256=? WHERE decision_id=?',
                  (json.dumps(record), digest(record), row['decision_id']))
    with pytest.raises(Refused, match='CAPACITY_HISTORY_CHANGED'):
        m.ledger.snapshot('rcc')
