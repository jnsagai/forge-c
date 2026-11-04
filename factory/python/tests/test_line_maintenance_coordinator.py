"""Controller/CRE boundary fixtures; these never claim model or production qualification."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import line_maintenance_coordinator as C
from forge_factory.afo.durable import Refused, digest
from forge_factory.afo.queue import Store
from forge_factory.afo.verification_job import VerificationJobs
from test_line_maintenance import terminal, local, order, factory, prepare  # noqa: F401
from test_line_maintenance_dispatch import prepare_job


@pytest.fixture
def line_terminal(monkeypatch, request, tmp_path):
    # The shared runtime guard reads this fixed queue. Select it before the
    # imported terminal/order fixtures construct and populate their Store.
    monkeypatch.setenv('FORGE_AFO_QUEUE_SCOPE', 'line-local')
    monkeypatch.setenv('FORGE_STATE_DIR', str(tmp_path / 'state'))
    # Fixture bootstrap is explicit; production implicit readers must refuse a
    # missing authoritative queue rather than silently constructing one.
    Store(tmp_path / 'state/supervisor/line-queue.sqlite3')
    value = request.getfixturevalue('terminal')
    from forge_factory.common import state_dir

    assert value[0][0].path == state_dir() / 'supervisor/line-queue.sqlite3'
    return value


@pytest.fixture
def scoped(tmp_path, monkeypatch):
    state = tmp_path / 'state'
    monkeypatch.setenv('FORGE_STATE_DIR', str(state))
    store = Store(state / 'supervisor/line-queue.sqlite3')
    bundle = {'order_id': 'afo-case', 'attempt_id': 'afo-case-a1', 'bundle_id': 'afo-fb-frozen',
              'failure_class': 'FACTORY_CODE_DEFECT', 'fingerprint': 'frozen-fingerprint', 'error_code': 'FACTORY_BUG'}
    case_path = state / 'afo/maintainer/mnt-case-a1/case.json'
    case_path.parent.mkdir(parents=True)
    case = {'proposal_id': 'mnt-case-a1', 'base': 'b' * 40, 'incident': bundle.copy(),
            'line_failure_bundle': {'sha256': digest(bundle), 'record': bundle}}
    case_path.write_text(json.dumps(case))
    job = {'job_id': 'afo-agent-' + '1' * 24, 'state': 'RUNNING', 'role': C.ROLE,
           'case': str(case_path), 'case_sha256': 'c' * 64, 'deadline_epoch': 2000000000,
           'order_id': bundle['order_id'], 'attempt_id': bundle['attempt_id'],
           'run_id': '01NATIVE_FIXTURE', 'nonce': 'frozen-fixture-nonce'}
    job['mission_id'] = 'mission-coordinator-fixture'
    C.MissionLedger(store).register(job['mission_id'], job['mission_id'], {
        'max_attempts': 0, 'max_jobs': 0, 'max_requests': 0, 'max_tokens': 0,
        'max_tools': 0, 'max_corrections': 0, 'deadline': job['deadline_epoch'],
    }, 'ISOLATED_CPU_FIXTURE', authorize=lambda *a: True)
    calls = []
    monkeypatch.setattr(C.binding, 'prepare', lambda *a, **k: copy.deepcopy(case))
    monkeypatch.setattr(C.L, 'prepare', lambda *a, **k: (calls.append(('prepare', k)) or copy.deepcopy(job)))
    monkeypatch.setattr(C.L, 'poll', lambda *a, **k: (calls.append(('poll', k)) or copy.deepcopy(job)))
    monkeypatch.setattr(C, '_authorized', lambda *a: calls.append(('authorized', {})))
    monkeypatch.setattr(C.M, 'case_dir', lambda pid: case_path.parent)
    monkeypatch.setattr(C.M, 'submission', lambda *a, **k: (calls.append(('submission', k)) or ({'candidate': 'd' * 40}, {})))
    monkeypatch.setattr(C.M, 'load_case', lambda *a: copy.deepcopy(case))
    actual_quiet = C._quiet
    monkeypatch.setattr(C, '_quiet', lambda *a: True)
    client = SimpleNamespace(list_runs=lambda **k: [])

    def step(**overrides):
        data = {'store': store, 'order': {'order_id': bundle['order_id']},
                'attempt': {'attempt_id': bundle['attempt_id'], 'state': 'FAILED'},
                'bundle': copy.deepcopy(bundle), 'workspace': tmp_path / 'source', 'eff': SimpleNamespace(),
                'line_origin': {'campaign_path': '/controller/campaign.yaml'},
                'line_role_authority_ref': None, 'client': client}
        data.update(overrides)
        return C.step(**data)

    return SimpleNamespace(store=store, bundle=bundle, case=case, job=job, calls=calls, step=step,
                           client=client, actual_quiet=actual_quiet)


def test_foreign_or_nonfactory_source_never_reaches_model(scoped):
    for changed in ({'failure_class': 'PRODUCT_QUALITY'}, {'order_id': 'foreign'}, {'attempt_id': 'foreign'}):
        result = scoped.step(bundle={**scoped.bundle, **changed})
        assert result['status'] == 'BLOCKED'
    assert scoped.calls == []


def test_failure_evidence_change_never_becomes_an_opaque_repair_job(scoped):
    result = scoped.step(bundle={**scoped.bundle, 'redacted_summary': 'changed source evidence'})
    assert result['status'] == 'BLOCKED' and result['code'] == 'LINE_MAINTENANCE_FULL_FAILURE_REQUIRED'
    assert scoped.calls == []


def test_existing_role_job_and_exact_controller_authority_are_used(scoped):
    ref = {'path': '/signed/controller-only.json', 'sha256': 'a' * 64}
    result = scoped.step(line_role_authority_ref=ref)
    assert result['status'] == 'MAINTENANCE_PENDING'
    assert scoped.calls[0][1]['line_role_authority_ref'] == ref
    assert scoped.calls[0][1]['line_origin'] == {'campaign_path': '/controller/campaign.yaml'}
    assert VerificationJobs(scoped.store).get(scoped.job['job_id']) is None


def test_native_success_without_quiescence_does_not_start_cre(scoped, monkeypatch):
    scoped.job['state'] = 'SUCCEEDED'
    monkeypatch.setattr(C, '_quiet', lambda *a: False)
    result = scoped.step()
    assert result['status'] == 'MAINTENANCE_PENDING' and result['code'] == 'QUIESCENCE_UNPROVEN'
    assert not any(name == 'submission' for name, _ in scoped.calls)


def test_success_without_nonce_bound_submission_cannot_start_cre(scoped, monkeypatch):
    scoped.job['state'] = 'SUCCEEDED'

    def missing(*a, **k):
        raise C.M.MaintainerDenied('SUBMISSION_RECEIPT_MISMATCH')

    monkeypatch.setattr(C.M, 'submission', missing)
    assert scoped.step()['status'] == 'BLOCKED'
    assert VerificationJobs(scoped.store).get(scoped.job['job_id']) is None


def test_complete_offline_review_is_reused_without_publication_or_reexecution(scoped, monkeypatch):
    scoped.job['state'] = 'SUCCEEDED'
    queue = VerificationJobs(scoped.store)
    queue.ensure(scoped.job['job_id'], scoped.job['case_sha256'], deadline_epoch=scoped.job['deadline_epoch'])
    epoch = queue.dispatch(scoped.job['job_id'], lambda _: None)
    queue.claim(scoped.job['job_id'], epoch)
    queue.finish(scoped.job['job_id'], epoch, {'status': 'ELIGIBLE_FOR_OFFLINE_REVIEW', 'source_deployed': False})
    monkeypatch.setattr(C, '_dispatch_review', lambda *a: None)
    result = scoped.step()
    assert result['status'] == 'WAITING_EXTERNAL_CHANGE' and result['publication'] == 'OFFLINE_ONLY'
    assert result['source_deployed'] is False
    assert queue.get(scoped.job['job_id'])['record']['dispatches'] == 1


def test_unknown_api_or_unreleased_execution_is_never_quiet(scoped, monkeypatch):
    execution = {'execution_liveness': 'QUIESCENT', 'resource_lease': 'RELEASED',
                 'native_run_ids': [scoped.job['run_id']]}
    monkeypatch.setattr(C.Executions, 'get', lambda *a: execution)
    unavailable = SimpleNamespace(get_run=lambda *a: (_ for _ in ()).throw(ConnectionError()))
    assert scoped.actual_quiet(scoped.store, unavailable, scoped.job) is False
    native = {'id': scoped.job['run_id'], 'lifecycle': {'status': {'kind': 'succeeded'}},
              'labels': {'afo_agent': scoped.job['job_id'], 'afo_nonce': scoped.job['nonce']},
              'source_directory': str(C.L.directory(scoped.job['job_id']) / 'workspace')}
    client = SimpleNamespace(get_run=lambda *a: native)
    assert scoped.actual_quiet(scoped.store, client, scoped.job) is True
    native['labels']['afo_nonce'] = 'foreign'
    assert scoped.actual_quiet(scoped.store, client, scoped.job) is False
    native['labels']['afo_nonce'] = scoped.job['nonce']
    native['lifecycle']['status']['kind'] = 'mystery'
    assert scoped.actual_quiet(scoped.store, client, scoped.job) is False
    execution['resource_lease'] = 'HELD'
    assert scoped.actual_quiet(scoped.store, client, scoped.job) is False


def test_review_rechecks_fence_and_keeps_existing_independent_pipeline(scoped, monkeypatch):
    from forge_factory.afo import completion_receipt, policy
    from forge_factory.reliability import policy as cre_policy
    scoped.job['state'] = 'SUCCEEDED'
    monkeypatch.setattr(completion_receipt.Context, 'from_job', lambda *a: None)
    monkeypatch.setattr(policy, 'load', lambda: SimpleNamespace())
    monkeypatch.setattr(cre_policy, 'load', lambda: SimpleNamespace())
    monkeypatch.setattr(C.Store, 'proposal', lambda *a: None)
    seen = []

    def process(*a, **k):
        seen.append(k)
        return {'outcome': 'ELIGIBLE_FOR_OFFLINE_REVIEW', 'cre_promotion_id': 'pd-independent',
                'auto_deployment_allowed': False}

    monkeypatch.setattr(C.M, 'process', process)
    monkeypatch.setattr(C.M, 'publish', lambda *a, **k: pytest.fail('line repair must remain offline'))
    result = C.review(scoped.store, scoped.job, SimpleNamespace(), fence=lambda: True, client=scoped.client)
    assert result['status'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW' and result['source_deployed'] is False
    assert callable(seen[0]['evaluator']) and seen[0]['tests_ref'] == 'local-agent:' + scoped.job['job_id']
    with pytest.raises(Refused, match='FENCED'):
        C.review(scoped.store, scoped.job, SimpleNamespace(), fence=lambda: False, client=scoped.client)


@pytest.mark.parametrize('change', ['policy', 'intent', 'deadline', 'source', 'case', 'signed_intent', 'signed_mission'])
def test_independent_review_refuses_revoked_or_changed_authority(line_terminal, monkeypatch, tmp_path, change):
    from forge_factory.afo.operations import Intent
    from forge_factory import workorder

    terminal = line_terminal
    args, eff, _, _, _ = terminal
    store = args[0]
    private = tmp_path / 'private-intent'
    private.mkdir(mode=0o700)
    intent = Intent(private / 'operations.json')
    control = intent.set('RUNNING', actor='qualification-fixture', reason='unit-only authority fixture', initialize=True)
    monkeypatch.setenv('FORGE_OPERATIONS_INTENT', str(intent.path))
    monkeypatch.setenv('FORGE_DURABLE_AUTONOMY', '1')
    case = prepare(terminal)
    job = prepare_job(terminal, case)
    job.update(state='SUCCEEDED', operations_epoch=control['epoch'])
    job['native_context']['FORGE_OPERATIONS_INTENT'] = str(intent.path)
    C.L.save(store, job)
    monkeypatch.setattr(C.line_recovery, 'valid_job', lambda *a: True)  # independently covered source binder
    C._authorized(store, job, eff)
    if change == 'policy':
        monkeypatch.setattr(C.L, 'authorized_job', lambda *a: False)
    elif change == 'intent':
        intent.set('STOPPED', actor='qualification-fixture', reason='unit-only authenticated stop')
    elif change == 'deadline':
        job['deadline_epoch'] = 1
        C.L.save(store, job)
    elif change == 'source':
        monkeypatch.setattr(workorder, 'factory_revision', lambda: {'commit': 'f' * 40, 'dirty': False})
    elif change == 'case':
        path = Path(job['case'])
        path.chmod(0o600)
        path.write_text(path.read_text() + ' ')
    else:
        from forge_factory.afo import line_recovery_control
        with store.tx() as c:
            registered = json.loads(c.execute('SELECT record FROM afo_missions WHERE mission_id=?',
                                             (job['mission_id'],)).fetchone()[0])
        control = {'operations_intent': str(intent.path), 'profile': job['profile'],
                   'profile_sha256': job['profile_sha256'], 'authorization_ref': registered['authorization_ref'],
                   'source_revision': job['factory_revision']['commit'], 'policy_sha256': job['policy_sha256'],
                   'mission': {k: registered[k] for k in ('mission_id', 'lineage', 'limits')}}
        # Signature/expiry checks have their own real parser controls; exercise the exact job/control binding here.
        monkeypatch.setattr(line_recovery_control, 'configuration', lambda *a, **k: control)
        job['line_role_authority_ref'] = {'path': str(tmp_path / 'signed-fixture.json'), 'sha256': 'a' * 64}
        C.L.save(store, job)
        assert line_recovery_control.require_job_binding(job, control, store=store)
        C._authorized(store, job, eff)
        if change == 'signed_intent':
            control['operations_intent'] = str(tmp_path / 'other-owned-intent.json')
            expected = 'LINE_ROLE_OPERATIONS_CONTEXT_MISMATCH'
        else:
            control['mission']['lineage'] = 'different-finite-lineage'
            expected = 'LINE_ROLE_SIGNED_MISSION_LIMITS_MISMATCH'
        with pytest.raises(Refused, match=expected):
            line_recovery_control.require_job_binding(job, control, store=store)
    with pytest.raises(Refused):
        C._authorized(store, job, eff)


def test_complete_failure_evidence_is_paged_as_untrusted_data_and_tamper_is_refused(tmp_path, monkeypatch):
    from forge_factory.mcp.servers import maintainer as server
    from forge_factory.mcp.sdk import ToolContext, ToolDenied

    monkeypatch.setenv('FORGE_STATE_DIR', str(tmp_path / 'state'))
    monkeypatch.delenv('FORGE_LRTX_PROFILE', raising=False)
    failure = {'order_id': 'afo-x', 'attempt_id': 'afo-x-a1', 'bundle_id': 'afo-fb-x',
               'failure_class': 'FACTORY_CODE_DEFECT', 'redacted_summary': 'observation ' * 1200 + 'LAST_FACT'}
    case = {'proposal_id': 'mnt-x', 'base': 'b' * 40,
            'incident': {k: failure[k] for k in ('order_id', 'attempt_id', 'bundle_id', 'failure_class')},
            'line_failure_bundle': {'sha256': digest(failure), 'record': failure}}
    monkeypatch.setattr(server, '_case', lambda: case)
    workspace = tmp_path / 'workspace'
    workspace.mkdir()
    ctx = ToolContext('forge-maintainer-mcp', 'read_case', C.ROLE, None, workspace, 'unit-m7-evidence')
    response = server.read_case(ctx, server.NoIn())
    body = json.loads(response['metrics']['data'])
    assert body['line_failure_bundle']['record']['redacted_summary'].endswith('LAST_FACT')
    assert body['line_failure_bundle']['sha256'] == digest(failure)
    failure['redacted_summary'] += ' changed'
    with pytest.raises(ToolDenied, match='FAILURE_CHANGED'):
        server.read_case(ctx, server.NoIn())


def test_maintainer_admission_pins_explicit_role_inputs_without_inventing_competence(line_terminal, monkeypatch, tmp_path):
    from forge_factory.afo import authz, line_recovery_control
    from forge_factory.afo.durable import immutable_json
    from forge_factory.lrtx.profile import load
    from forge_factory import workorder
    from forge_factory.afo.operations import Intent

    terminal = line_terminal
    args, eff, _, _, _ = terminal
    store, oid, aid, workspace, origin = args
    case = prepare(terminal)
    profile = load('local-rtx-v2-omniverse2')
    mission = C.MissionLedger(store).snapshot('line-maintenance-fixture')
    eff.policy['authorization_ref'] = 'fixture-maintenance-control'
    revision = terminal[3]['source_revision']
    monkeypatch.setattr(workorder, 'factory_revision', lambda: {'commit': revision, 'dirty': False})
    private = tmp_path / 'private-intent'
    private.mkdir(mode=0o700)
    intent = Intent(private / 'operations.json')
    intent_record = intent.set('RUNNING', actor='qualification-fixture', reason='unit-only admission fixture', initialize=True)
    monkeypatch.setenv('FORGE_OPERATIONS_INTENT', str(intent.path))
    value = {'schema': line_recovery_control.SCHEMA, 'source_revision': revision,
             'policy_sha256': eff.sha256, 'authorization_ref': eff.get('authorization_ref'),
             'profile': profile['id'], 'profile_sha256': profile['_sha256'],
             'operations_intent': str(intent.path),
             'mission': {'mission_id': 'line-maintenance-fixture', 'lineage': 'line-maintenance-fixture',
                         'limits': mission['limits']}, 'role_capabilities': {}, 'product_role_trial': None}
    path = tmp_path / (digest(value) + '.json')
    immutable_json(path, value)
    ref = {'path': str(path), 'sha256': digest(value)}
    monkeypatch.setattr(authz, 'AUTH_DIR', tmp_path)
    allowed = SimpleNamespace(allow=True, code='AUTH_OK')
    monkeypatch.setattr(authz, 'find', lambda *a, **k: allowed)
    (tmp_path / 'fixture-maintenance-control.json').write_text(json.dumps({
        'signed_runbook_ref': 'line-recovery-014:' + digest(value), 'expires_utc': '2099-01-01T00:00:00Z'}))
    monkeypatch.setenv('FORGE_DURABLE_AUTONOMY', '1')
    job = C.L.prepare(store, store.order(oid), aid, C.ROLE, C.M.case_dir(case['proposal_id']) / 'case.json',
                      workspace, eff, line_origin=origin, line_role_authority_ref=ref)
    assert job['line_role_authority_ref'] == ref and job['role_capabilities'] == {}
    assert job['native_context']['FORGE_OPERATIONS_INTENT'] == str(intent.path)
    assert job['native_context']['FORGE_AFO_QUEUE_SCOPE'] == 'line-local'
    assert job['operations_epoch'] == intent_record['epoch']
    assert line_recovery_control.require_job_binding(job, value, store=store)
    assert not job.get('product_role_trial')  # signed controller inputs alone grant no competence
    monkeypatch.setattr(C.line_recovery, 'valid_job', lambda *a: True)  # source binding has separate controls
    allowed.allow, allowed.code = False, 'AUTH_REVOKED'
    assert C.L.authorized_job(store.order(oid), eff, job) is False
