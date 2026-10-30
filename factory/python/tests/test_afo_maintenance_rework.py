"""Same-order retained rework through the actual store, broker and bounded Conductor path."""
# ruff: noqa: F811
import copy
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from forge_factory.afo import local_agent as L
from forge_factory.afo import maintainer as M
from forge_factory.afo import maintenance_rework as R
from forge_factory.afo import policy
from forge_factory.afo.durable import Refused
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.verification_job import VerificationJobs
from forge_factory.common import sha256_file
from forge_factory.reliability import isolation
from forge_factory.reliability.policy import load as cre_policy
from forge_factory.reliability.store import CREStore
from test_afo_local_autonomy import local, order  # noqa: F401
from test_afo_m5_maintainer import SIG, _good_candidate, factory  # noqa: F401


def setup_parent(local, factory, monkeypatch, *, maximum=2, reject=True, claim=True, reproducer_source=None, signature=SIG):
    store, order, bundle, old_eff, workspace, _ = local
    pol = copy.deepcopy(old_eff.policy)
    pol['maintenance']['max_retained_reworks'] = maximum
    eff = policy.Effective('PILOT', 'PILOT', old_eff.sha256, pol)
    monkeypatch.setattr(policy, 'load', lambda *a, **k: eff)
    monkeypatch.setenv('FORGE_DURABLE_AUTONOMY', '1')
    limits = {'max_attempts': 3, 'max_jobs': 4, 'max_tokens': 120000, 'max_requests': 100,
              'max_tools': 100, 'max_corrections': 1, 'deadline': time.time() + 3600}
    ledger = MissionLedger(store)
    ledger.register('retained-test', 'same-original-workload', limits, 'AUTH-fixture', authorize=lambda *a: True)
    ledger.link('retained-test', order['order_id'])
    pid = f"mnt-{order['order_id'].removeprefix('afo-')[:16]}-a1"
    case = M.prepare(pid, 'HEAD', {'order_id': order['order_id']}, repo=factory)
    _good_candidate(case)
    if reject:
        M.write_source(case, M.CANDIDATE_TESTS + 'rpr_calc.py', reproducer_source or 'print("SYMPTOM_ABSENT")\n')
    sub = M.submit(case, 'repair the actual arithmetic defect', M.CANDIDATE_TESTS + 'rpr_calc.py', signature)
    with monkeypatch.context() as admission:
        admission.setattr(isolation, 'available', lambda: True)
        job = L.prepare(store, order, bundle['attempt_id'], 'afo-factory-maintainer',
                        M.case_dir(pid) / 'case.json', workspace, eff)
    native = SimpleNamespace(get_run=lambda _: {'lifecycle': {'status': {'kind': 'SUCCEEDED'}}}, usage=lambda _: {})
    job = L.poll(store, order, job, eff, client=native, launch_fn=lambda _: 'synthetic-native-parent')
    job = L.poll(store, order, job, eff, client=native)
    assert job['state'] == 'SUCCEEDED'
    queue = VerificationJobs(store)
    queue.ensure(job['job_id'], job['case_sha256'], deadline_epoch=job['deadline_epoch'])
    epochs = []
    queue.dispatch(job['job_id'], epochs.append)
    if claim:
        queue.claim(job['job_id'], epochs[0])
    return SimpleNamespace(store=store, order=order, job=job, case=case, sub=sub, eff=eff,
                           queue=queue, epoch=epochs[0], ledger=ledger, workspace=workspace, native=native)


def reject(p):
    rec = M.process(p.store, p.case['proposal_id'], CREStore(), cre_policy())
    assert rec['outcome'] == 'REJECTED'
    return rec


def complete(p, reference):
    p.queue.finish(p.job['job_id'], p.epoch, {'status': 'REJECTED', 'maintenance_rework': reference})


def test_rejected_receipted_artifacts_and_independent_facts_survive_quarantine(local, factory, monkeypatch):
    p = setup_parent(local, factory, monkeypatch)
    reject(p)
    assert not Path(p.case['src']).exists()
    before = p.ledger.snapshot('retained-test')
    reference = R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: True)
    assert reference['state'] == 'READY'
    case_path = M.case_dir(reference['proposal_id']) / 'case.json'
    child = json.loads(case_path.read_text())
    assert child['base'] == p.case['base'] and child['retained_rework']['parent_candidate'] == p.sub['candidate']
    assert child['retained_rework']['feedback']['reproducer_runs'][0]['verdict'] == 'SYMPTOM_ABSENT'
    assert child['retained_rework']['feedback']['registered_symptom_signature'] == SIG
    for row in child['retained_rework']['files']:
        assert sha256_file(Path(child['src']) / row['path']) == row['sha256']
    assert p.ledger.snapshot('retained-test') == before  # preparation is not model admission
    assert R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: True) == reference
    complete(p, reference)
    path, attempt = R.next_binding(p.store, p.job, p.eff)
    with monkeypatch.context() as admission:
        admission.setattr(isolation, 'available', lambda: True)
        child_job = L.prepare(p.store, p.order, attempt, 'afo-factory-maintainer', path, p.workspace, p.eff)
    assert child_job['job_id'] != p.job['job_id'] and child_job['order_id'] == p.job['order_id']
    assert child_job['mission_id'] == p.job['mission_id']
    assert child_job['deadline_epoch'] <= p.job['deadline_epoch']
    after = p.ledger.snapshot('retained-test')
    assert after['jobs'] == before['jobs'] + 1
    assert after['charged_tokens'] == before['charged_tokens'] + child_job['reserved_tokens']
    assert after['attempts'] == before['attempts'] and after['limits'] == before['limits']
    assert len(p.store.orders()) == 1
    assert R.next_binding(p.store, p.job, p.eff) == (path, attempt)
    with monkeypatch.context() as admission:
        admission.setattr(isolation, 'available', lambda: True)
        assert L.prepare(p.store, p.order, attempt, 'afo-factory-maintainer', path, p.workspace, p.eff) == child_job


@pytest.mark.parametrize('gate', ['disabled', 'live_parent', 'fence', 'allowance', 'authority', 'deadline', 'unsafe'])
def test_no_new_job_or_rework_when_fences_or_remaining_authority_fail(local, factory, monkeypatch, gate):
    p = setup_parent(local, factory, monkeypatch, maximum=0 if gate == 'disabled' else 2)
    reject(p)
    if gate == 'live_parent':
        monkeypatch.setattr(Executions, 'get', lambda *a: {'execution_liveness': 'LIVE', 'resource_lease': 'HELD'})
    elif gate == 'allowance':
        p.eff.policy['budgets']['max_recovery_model_calls_per_order'] = 1
    elif gate == 'authority':
        monkeypatch.setattr(L, 'authorized', lambda *a: False)
    elif gate == 'deadline':
        p.job['deadline_epoch'] = time.time() - 1
    elif gate == 'unsafe':
        monkeypatch.setattr(M, 'veto', lambda *a: ['PROTECTED_PATH'])
    before = p.ledger.snapshot('retained-test')
    if gate == 'disabled':
        assert R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: True) is None
    else:
        with pytest.raises(Refused):
            R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: gate != 'fence')
    assert p.ledger.snapshot('retained-test') == before
    assert len(L.records(p.store, p.order['order_id'])) == 1
    assert not (M.case_dir(p.case['proposal_id'] + '-r1') / 'retained-ready.json').exists()


def test_preparation_recovers_after_partial_seed_without_reverting_an_active_child(local, factory, monkeypatch):
    p = setup_parent(local, factory, monkeypatch)
    reject(p)
    original = M.write_source
    count = 0

    def crash(case, rel, content):
        nonlocal count
        count += 1
        if count == 2:
            raise OSError('simulated interruption between retained files')
        return original(case, rel, content)

    monkeypatch.setattr(M, 'write_source', crash)
    with pytest.raises(OSError):
        R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: True)
    monkeypatch.setattr(M, 'write_source', original)
    reference = R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: True)
    complete(p, reference)
    path, attempt = R.next_binding(p.store, p.job, p.eff)
    child = json.loads(path.read_text())
    original(child, 'factory/python/forge_factory/calc.py', 'def add(a, b):\n    return a + b + 0\n')
    current = sha256_file(Path(child['src']) / 'factory/python/forge_factory/calc.py')
    assert R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: True) == reference
    assert sha256_file(Path(child['src']) / 'factory/python/forge_factory/calc.py') == current


def test_completed_worker_reference_is_required_before_conductor_can_admit(local, factory, monkeypatch):
    p = setup_parent(local, factory, monkeypatch)
    reject(p)
    reference = R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: True)
    assert R.next_binding(p.store, p.job, p.eff) is None
    complete(p, reference)
    assert R.next_binding(p.store, p.job, p.eff)
    path = M.case_dir(reference['proposal_id']) / 'case.json'
    path.chmod(0o600)
    data = json.loads(path.read_text())
    data['retained_rework']['index'] = 7
    path.write_text(json.dumps(data))
    with pytest.raises(Refused):
        R.next_binding(p.store, p.job, p.eff)


def test_changed_feedback_is_never_adopted_after_partial_preparation(local, factory, monkeypatch):
    p = setup_parent(local, factory, monkeypatch)
    reject(p)
    monkeypatch.setattr(M, 'prepare', lambda *a, **k: (_ for _ in ()).throw(OSError('crash before child case')))
    with pytest.raises(OSError):
        R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: True)
    path = M.case_dir(p.case['proposal_id'] + '-r1') / 'independent-feedback.json'
    path.chmod(0o600)
    path.write_text('{}')
    with pytest.raises(Refused, match='FEEDBACK_CHANGED'):
        R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: True)


def test_failure_to_prepare_child_does_not_replace_actual_independent_rejection(local, factory, monkeypatch):
    p = setup_parent(local, factory, monkeypatch)
    reject(p)
    result = L.review_followup(p.store, p.job, p.eff, verification_fence=lambda: False)
    assert result == {'state': 'BLOCKED', 'reason': 'VERIFICATION_PUBLICATION_FENCED'}
    assert p.store.proposal(p.case['proposal_id'])['status'] == 'REJECTED'


def test_optional_policy_bound_is_validated_without_changing_existing_policy():
    from forge_factory.common import REPO_ROOT, load_yaml

    base = load_yaml(REPO_ROOT / 'config/factory/afo-policy.yaml')
    assert not policy.schema_errors(base)
    for value in [0, 1, 8]:
        p = copy.deepcopy(base)
        p['maintenance']['max_retained_reworks'] = value
        assert not policy.schema_errors(p)
    for value in [-1, 9, True, 1.5]:
        p = copy.deepcopy(base)
        p['maintenance']['max_retained_reworks'] = value
        assert policy.schema_errors(p)


def test_actual_worker_seals_feedback_and_existing_conductor_admits_only_one_child(local, factory, monkeypatch):
    from forge_factory.afo import queue as queue_module
    from forge_factory.afo import runtime

    p = setup_parent(local, factory, monkeypatch, claim=False)
    p.store.transition(p.order['order_id'], 'WAITING_EXTERNAL_CHANGE', 'synthetic factory defect fixture')
    monkeypatch.setattr(queue_module, 'Store', lambda *a: p.store)
    assert L.main(['review', '--job', p.job['job_id'], '--epoch', str(p.epoch)]) == 2
    verification = p.queue.get(p.job['job_id'])
    assert verification['state'] == 'COMPLETE'
    assert verification['record']['result']['status'] == 'REJECTED'
    assert verification['record']['result']['maintenance_rework']['state'] == 'READY'
    monkeypatch.setattr(runtime, 'workspace_of', lambda *a: p.workspace)
    original_prepare, original_poll = L.prepare, L.poll

    def admitted(*args, **kwargs):
        with monkeypatch.context() as admission:
            admission.setattr(isolation, 'available', lambda: True)
            return original_prepare(*args, **kwargs)

    monkeypatch.setattr(L, 'prepare', admitted)
    monkeypatch.setattr(L, 'poll', lambda store, order, job, eff: original_poll(
        store, order, job, eff, client=p.native, launch_fn=lambda j: 'synthetic-' + j['job_id']))
    first = L.sweep_maintenance(p.store, p.eff)
    assert len(first) == 2 and first[-1]['state'] == 'RUNNING'
    jobs = L.records(p.store, p.order['order_id'])
    assert len(jobs) == 2 and jobs[0]['job_id'] != jobs[1]['job_id']
    child = next(j for j in jobs if j['job_id'] != p.job['job_id'])
    case = json.loads(Path(child['case']).read_text())
    # A synthetic test author corrects the child; no Qwen capability is claimed by this fixture.
    _good_candidate(case)
    M.submit(case, 'repair the arithmetic with a causal reproducer', M.CANDIDATE_TESTS + 'rpr_calc.py', SIG)
    spawned = []
    def dispatch_review(store, job):
        queue = VerificationJobs(store)
        queue.ensure(job['job_id'], job['case_sha256'], deadline_epoch=job['deadline_epoch'])
        queue.dispatch(job['job_id'], lambda epoch: spawned.append((job['job_id'], epoch)))

    monkeypatch.setattr(L, 'launch_review', dispatch_review)
    second = L.sweep_maintenance(p.store, p.eff)
    assert second[-1]['state'] == 'SUCCEEDED' and len(spawned) == 1
    monkeypatch.setattr(M, 'evaluate', lambda *a, **k: {
        'decision': 'ELIGIBLE_FOR_OFFLINE_REVIEW', 'decision_id': 'fixture-eligibility',
        'allowed_auto_deployment': False})
    row = p.queue.get(child['job_id'])
    assert L.main(['review', '--job', child['job_id'], '--epoch', str(row['epoch'])]) == 0
    assert p.queue.get(child['job_id'])['record']['result']['status'] == 'PUBLISHED'
    assert len(L.records(p.store, p.order['order_id'])) == 2
    assert len(p.store.orders()) == 1
    assert p.ledger.snapshot('retained-test')['jobs'] == 2
    assert p.store.proposal(p.case['proposal_id'])['status'] == 'REJECTED'
    assert p.store.proposal(case['proposal_id'])['record']['auto_deployment_allowed'] is False


def test_rework_limit_ends_only_this_job_chain_without_refilling_its_allowance(local, factory, monkeypatch):
    p = setup_parent(local, factory, monkeypatch, maximum=1)
    reject(p)
    reference = R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: True)
    complete(p, reference)
    path, attempt = R.next_binding(p.store, p.job, p.eff)
    with monkeypatch.context() as admission:
        admission.setattr(isolation, 'available', lambda: True)
        child = L.prepare(p.store, p.order, attempt, 'afo-factory-maintainer', path, p.workspace, p.eff)
    case = json.loads(path.read_text())
    M.submit(case, 'second synthetic proposal retaining its unresolved reproducer', M.CANDIDATE_TESTS + 'rpr_calc.py', SIG)
    child = L.poll(p.store, p.order, child, p.eff, client=p.native, launch_fn=lambda _: 'synthetic-second')
    child = L.poll(p.store, p.order, child, p.eff, client=p.native)
    assert child['state'] == 'SUCCEEDED'
    M.process(p.store, case['proposal_id'], CREStore(), cre_policy())
    before = p.ledger.snapshot('retained-test')
    assert R.prepare_next(p.store, child, p.eff, verification_fence=lambda: True) == {
        'state': 'EXHAUSTED', 'reason': 'MAINTENANCE_REWORK_LIMIT_REACHED'}
    assert p.ledger.snapshot('retained-test') == before
    assert len(p.store.orders()) == 1 and before['jobs'] == 2


def test_complete_oversized_independent_feedback_blocks_without_silent_truncation(local, factory, monkeypatch):
    p = setup_parent(local, factory, monkeypatch, reproducer_source='print("x" * 40000)\nprint("SYMPTOM_ABSENT")\n')
    reject(p)
    with pytest.raises(Refused, match='FEEDBACK_TOO_LARGE'):
        R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: True)
    assert not (M.case_dir(p.case['proposal_id'] + '-r1') / 'case.json').exists()
    assert len(L.records(p.store, p.order['order_id'])) == 1


def test_newer_operator_pause_and_changed_receipt_prevent_retained_dispatch(local, factory, monkeypatch):
    from forge_factory.afo.operations import Intent

    p = setup_parent(local, factory, monkeypatch)
    reject(p)
    intent_dir = Path(p.job['case']).parent / 'private-operator'
    intent_dir.mkdir(mode=0o700)
    intent_path = intent_dir / 'synthetic-operator-intent.json'
    monkeypatch.setenv('FORGE_OPERATIONS_INTENT', str(intent_path))
    Intent().set('PAUSED', actor='test-owner', reason='newer operator intent', initialize=True)
    with pytest.raises(Refused, match='OPERATIONS_ADMISSION_REFUSED'):
        R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: True)
    monkeypatch.delenv('FORGE_OPERATIONS_INTENT')
    receipt = Path(p.job['case']).parent / 'submission-receipt.json'
    receipt.chmod(0o600)
    changed = json.loads(receipt.read_text())
    changed['candidate'] = '0' * 40
    receipt.write_text(json.dumps(changed))
    with pytest.raises(M.MaintainerDenied, match='SUBMISSION_RECEIPT_MISMATCH'):
        R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: True)


def test_real_marker_binding_error_is_supplied_as_complete_independent_feedback(local, factory, monkeypatch):
    p = setup_parent(local, factory, monkeypatch, reject=False, signature='SYMPTOM_PRESENT:' + SIG)
    reject(p)
    reference = R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: True)
    child = json.loads((M.case_dir(reference['proposal_id']) / 'case.json').read_text())
    facts = child['retained_rework']['feedback']
    assert facts['registered_symptom_signature'] == 'SYMPTOM_PRESENT:' + SIG
    assert facts['reproducer_runs'][0]['verdict'] == 'ERROR'
    assert facts['reproducer_runs'][0]['exit_code'] == 1
    assert facts['reproducer_runs'][0]['log'].splitlines()[0] == 'SYMPTOM_PRESENT:' + SIG
    assert facts['untrusted_data'] and facts['instructions_or_permissions'] is False


def test_retained_bytes_preserve_git_blob_line_endings(local, factory, monkeypatch):
    import subprocess

    p = setup_parent(local, factory, monkeypatch, reproducer_source='print("SYMPTOM_ABSENT")\r\n')
    reject(p)
    reference = R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: True)
    child = json.loads((M.case_dir(reference['proposal_id']) / 'case.json').read_text())
    rel = M.CANDIDATE_TESTS + 'rpr_calc.py'
    original = subprocess.check_output(['git', '-C', str(factory), 'show', p.sub['candidate'] + ':' + rel])
    assert original.endswith(b'\r\n')
    assert (Path(child['src']) / rel).read_bytes() == original


def test_retained_independent_feedback_reaches_the_actual_paged_maintainer_tool(local, factory, monkeypatch):
    from forge_factory.mcp.sdk import ToolContext
    from forge_factory.mcp.servers import maintainer as server

    p = setup_parent(local, factory, monkeypatch)
    reject(p)
    reference = R.prepare_next(p.store, p.job, p.eff, verification_fence=lambda: True)
    path = M.case_dir(reference['proposal_id']) / 'case.json'
    child = json.loads(path.read_text())
    monkeypatch.setenv('FORGE_AFO_MAINT_CASE', str(path))
    monkeypatch.delenv('FORGE_LRTX_PROFILE', raising=False)
    ctx = ToolContext('forge-maintainer-mcp', 'read_case', 'afo-factory-maintainer', None, Path(child['src']), 'fixture')
    offset, parts = 0, []
    while offset is not None:
        output = server.read_case(ctx, server.NoIn(offset=offset))
        assert output['status'] == 'PASS'
        parts.append(output['metrics']['data'])
        offset = output['metrics']['next_offset']
        assert len(parts) <= 20
    delivered = json.loads(''.join(parts))['retained_rework']
    assert delivered == child['retained_rework']
    assert delivered['feedback']['registered_symptom_signature'] == SIG
    assert delivered['feedback']['reproducer_runs'][0]['verdict'] == 'SYMPTOM_ABSENT'
    assert delivered['feedback']['untrusted_data'] is True
    assert delivered['feedback']['instructions_or_permissions'] is False
