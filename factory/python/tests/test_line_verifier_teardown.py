"""Actual bubblewrap namespaces/parallel children, exact queue owner and private intent.

Role/admission/CRE result leaves are fixtures; no model or repair qualification.
The two-worker capacity is controlled input, not a host capacity claim.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

import pytest


def worker(root, epoch, mode):
    from forge_factory.afo import line_maintenance_coordinator as C
    from forge_factory.afo.completion_receipt import Context
    from forge_factory.afo.durable import Refused
    from forge_factory.afo.mission_ledger import MissionLedger
    from forge_factory.afo.queue import Store
    from forge_factory.afo.verification_job import VerificationJobs
    from forge_factory.afo import policy as AP
    from forge_factory.reliability import isolation, parallel, policy as CP, store as CS

    store = Store(root / 'queue.sqlite3')
    queue = VerificationJobs(store)
    queue.claim('fixture-job', epoch, dedicated_group=True)
    deadline = time.time() + (1.2 if mode == 'deadline' else 5)
    limits = {k: 0 for k in ('max_attempts', 'max_jobs', 'max_requests', 'max_tokens', 'max_tools', 'max_corrections')}
    MissionLedger(store).register('fixture-mission', 'fixture-lineage', {**limits, 'deadline': deadline},
                                 'ISOLATED_FIXTURE_ONLY', authorize=lambda *_: True)
    job = {'job_id': 'fixture-job', 'mission_id': 'fixture-mission', 'case': str(root / 'fixture-case/case.json'),
           'case_sha256': 'a' * 64, 'deadline_epoch': deadline,
           'native_context': {'FORGE_OPERATIONS_INTENT': str(root / 'intent.json')}, 'operations_epoch': 1}
    case = {'proposal_id': 'fixture-case', 'base': 'b' * 40, 'incident': {'fingerprint': 'fixture'}}

    def authorized(*_):
        from forge_factory.afo.operations import Intent

        intent = Intent(root / 'intent.json').read()
        if intent.get('mode') != 'RUNNING' or intent.get('epoch') != 1:
            raise Refused('LINE_MAINTENANCE_OPERATIONS_CHANGED')
        if time.time() >= deadline:
            raise Refused('LINE_MAINTENANCE_DEADLINE')

    C._authorized = authorized
    C._quiet = lambda *_: True
    Context.from_job = lambda *_: None
    C.M.load_case = lambda *_: case
    C.M.submission = lambda *_, **kw: ({'candidate': 'c' * 40}, {})
    AP.load = CP.load = lambda: SimpleNamespace()
    CS.CREStore = lambda: object()
    parallel.capacity = lambda *_: 2
    heartbeat = ('import time,sys; from pathlib import Path; p=Path(sys.argv[1]); '
                 '\nfor i in range(60):\n p.write_text(str(time.time())); time.sleep(.05)\n')
    # A child in a distinct session inside the PID namespace must also quiesce;
    # host process-group propagation alone would not establish this.
    script = ('import subprocess,sys; child=subprocess.Popen([sys.executable,"-c",' + repr(heartbeat)
              + ',sys.argv[1]+".detached"],start_new_session=True); exec(' + repr(heartbeat) + '); child.wait()')

    def work(index):
        scratch = root / ('sandbox-' + str(index))
        scratch.mkdir()
        result = isolation.execute('verifier', [sys.executable, '-c', script, str(scratch / 'heartbeat')],
                                   cwd=scratch, env={'PATH': '/usr/bin:/bin'}, writable=[scratch], timeout=8)
        if result.returncode:
            (root / ('sandbox-error-' + str(index))).write_text(result.stderr.decode(errors='replace')[-500:])
            raise RuntimeError('ACTUAL_BUBBLEWRAP_CONTROL_FAILED')
        return index

    def process(*_, **kw):
        (root / 'started.json').write_text(json.dumps({'deadline': deadline, 'pid': os.getpid()}))
        parallel.ordered_map(work, [0, 1], jobs=2)
        return {'outcome': 'ELIGIBLE_FOR_OFFLINE_REVIEW', 'cre_promotion_id': 'FIXTURE_ONLY', 'auto_deployment_allowed': False}

    C.M.process = process
    try:
        C.review(store, job, SimpleNamespace(), fence=lambda: queue.current('fixture-job', epoch), client=object())
        result = {'status': 'UNEXPECTED_ACCEPTANCE'}
    except Exception as exc:
        result = {'status': type(exc).__name__}
    queue.finish('fixture-job', epoch, result)


def descendants(pid):
    from forge_factory.afo.verification_job import identity

    pending, found = [pid], {}
    while pending:
        parent = pending.pop()
        for path in Path(f'/proc/{parent}/task').glob('*/children'):
            try:
                children = [int(value) for value in path.read_text().split()]
            except (OSError, ValueError):
                continue
            for child in children:
                value = identity(child)
                if value and child not in found:
                    found[child] = value
                    pending.append(child)
    return found


def run_case(root, mode):
    from forge_factory.afo.operations import Intent
    from forge_factory.afo.queue import Store
    from forge_factory.afo.verification_job import VerificationJobs, identity

    root.mkdir(mode=0o700)
    os.environ.pop('FORGE_DURABLE_AUTONOMY', None)
    store = Store(root / 'queue.sqlite3')
    queue = VerificationJobs(store)
    queue.ensure('fixture-job', 'a' * 64, deadline_epoch=time.time() + 12)
    intent = Intent(root / 'intent.json')
    intent.set('RUNNING', actor='isolated-test', reason='explicit fixture only', initialize=True)
    processes = []

    def spawn(epoch):
        env = {**os.environ, 'FORGE_CRE_ISOLATION': 'bubblewrap', 'FORGE_CPU_JOBS': '2'}
        processes.append(subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--worker', str(root), str(epoch), mode],
                                          env=env, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE))

    epoch = queue.dispatch('fixture-job', spawn)
    proc = processes[0]
    observed = {}
    try:
        start = time.time()
        heartbeats = [root / f'sandbox-{index}/heartbeat{suffix}' for index in (0, 1) for suffix in ('', '.detached')]
        while time.time() - start < 6:
            if all(path.exists() for path in heartbeats):
                break
            if proc.poll() is not None:
                raise AssertionError('VERIFIER_CONTROL_EXITED:' + proc.stderr.read().decode(errors='replace')[-500:])
            time.sleep(.01)
        assert all(path.exists() for path in heartbeats), 'ACTUAL_SANDBOXES_NOT_REACHED'
        owned = descendants(proc.pid)
        assert len(owned) >= 8, 'ACTUAL_NAMESPACE_CHILDREN_NOT_OBSERVED'
        row = queue.get('fixture-job')
        assert row['record']['owner'] == identity(proc.pid) and row['record']['managed_process_group'] is True
        deadline = json.loads((root / 'started.json').read_text())['deadline']
        if mode == 'intent':
            boundary = time.time()
            intent.set('PAUSED', actor='isolated-test', reason='explicit fixture intent cancellation')
        else:
            boundary = deadline
        # Preserve actual backend children until they exit naturally at <=3s in baseline;
        # candidate must stop them at its finite boundary instead of unwinding threads.
        proc.wait(timeout=7)
        for _ in range(100):
            if all(identity(pid) != value for pid, value in owned.items()):
                break
            time.sleep(.01)
        latest = max(float(path.read_text()) for path in heartbeats)
        actual_quiet = all(identity(pid) != value for pid, value in owned.items())
        observed = {'mode': mode, 'backend': 'bubblewrap', 'controlled_capacity': 2,
                    'owned_descendant_count': len(owned), 'heartbeat_after_boundary_s': round(latest - boundary, 3),
                    'all_observed_owned_children_quiescent': actual_quiet, 'worker_returncode': proc.returncode,
                    'queue_result_accepted': bool((queue.get('fixture-job')['record'].get('result') or {}).get('status') == 'UNEXPECTED_ACCEPTANCE'),
                    'fixture_only': True}
        observed['pass'] = actual_quiet and latest - boundary < .4 and proc.returncode == -9 and not observed['queue_result_accepted']
        return observed
    finally:
        # Fixture lifecycle only: exact Popen PID-start and dedicated SID/PGID,
        # no production name search or foreign process termination.
        if proc.poll() is None:
            import signal
            owner = row['record']['owner'] if 'row' in locals() else identity(proc.pid)
            if owner and identity(proc.pid) == owner and os.getpgid(proc.pid) == proc.pid and os.getsid(proc.pid) == proc.pid:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)


@pytest.mark.parametrize('mode', ['deadline', 'intent'])
def test_actual_isolated_parallel_children_stop(tmp_path, mode):
    observed = run_case(tmp_path / mode, mode)
    assert observed['pass'], observed


def test_unqualified_backend_and_foreign_group_refuse(monkeypatch):
    from forge_factory.afo import line_verifier_guard as guard
    from forge_factory.afo.durable import Refused
    from forge_factory.reliability import isolation

    monkeypatch.setattr(isolation, 'backend', lambda: 'podman')
    with pytest.raises(Refused, match='BACKEND_TEARDOWN_NOT_QUALIFIED'):
        guard.require_backend()
    monkeypatch.setattr(guard.os, 'killpg', lambda *_: pytest.fail('foreign group must not be killed'))
    foreign = {'pid': os.getpid() + 1000000, 'start': '0', 'boot': 'foreign'}
    with pytest.raises(Refused, match='MANAGED_GROUP_UNCONFIRMED'):
        guard.terminate(foreign)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        worker(Path(sys.argv[2]), int(sys.argv[3]), sys.argv[4])
        return 0
    with tempfile.TemporaryDirectory(prefix='rpr155-actual-bwrap-') as temporary:
        observations = [run_case(Path(temporary) / mode, mode) for mode in ('deadline', 'intent')]
        print(json.dumps(observations))
        if not all(item['pass'] for item in observations):
            print('SYMPTOM_PRESENT:threaded line verifier children outlive finite wall or operator intent')
            return 1
    print('SYMPTOM_ABSENT')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('REPRODUCER_ERROR:' + type(exc).__name__ + ':' + str(exc)[:400])
        raise SystemExit(2)
