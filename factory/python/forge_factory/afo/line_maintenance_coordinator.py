"""M7 adapter: existing line case, durable maintainer and independent offline CRE review.

Called only by the existing bounded recovery worker, never the healthy Conductor loop.
No deployment, publication, new queue, implicit role competence or allowance is created.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from contextlib import nullcontext

from ..common import REPO_ROOT, sha256_file, state_dir
from . import line_maintenance as binding, line_recovery, local_agent as L, maintainer as M
from .durable import Refused, digest
from .execution_lifecycle import Executions
from .mission_ledger import MissionLedger
from .queue import QueueError, Store
from .verification_job import VerificationJobs

ROLE = 'afo-factory-maintainer'


def _code(exc):
    return L.incident_code(exc)


def _saved(store, job_id):
    with store.tx() as c:
        row = c.execute('SELECT record FROM afo_local_agent_jobs WHERE job_id=?', (job_id,)).fetchone()
    if not row:
        raise Refused('LINE_MAINTENANCE_JOB_ABSENT')
    return json.loads(row[0])


def _review_deadline(store, job, *, mission=None):
    mission = mission or MissionLedger(store).snapshot(job['mission_id'])
    deadlines = [job.get('deadline_epoch'), mission['limits'].get('deadline')]
    queued = VerificationJobs(store).get(job['job_id'])
    if queued and queued['record'].get('deadline_epoch') is not None:
        deadlines.append(queued['record']['deadline_epoch'])
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in deadlines):
        raise Refused('LINE_MAINTENANCE_DEADLINE_INVALID')
    return min(deadlines)


def _authorized(store, job, eff):
    from .operations import Intent
    from ..workorder import factory_revision

    order = store.order(job['order_id'])
    saved = _saved(store, job['job_id'])
    revision = factory_revision()
    if (saved != job or job.get('state') != 'SUCCEEDED'
            or job.get('role') != ROLE or job.get('durable_native') != 'maintenance-1'
            or not job.get('line_origin') or not L.enabled(ROLE, eff)
            or eff.sha256 != job.get('policy_sha256') or not L.authorized_job(order, eff, job)
            or not line_recovery.valid_job(job, store)
            or revision.get('dirty') is not False
            or revision.get('commit') != (job.get('factory_revision') or {}).get('commit')
            or Path(job['case']).is_symlink() or sha256_file(Path(job['case'])) != job['case_sha256']):
        raise Refused('LINE_MAINTENANCE_AUTHORITY_CHANGED')
    raw_intent = (job.get('native_context') or {}).get('FORGE_OPERATIONS_INTENT')
    if not raw_intent or not Path(raw_intent).is_absolute():
        raise Refused('LINE_MAINTENANCE_INTENT_UNBOUND')
    intent = Intent(raw_intent).read()
    if intent['mode'] != 'RUNNING' or intent['epoch'] != job.get('operations_epoch'):
        raise Refused('LINE_MAINTENANCE_OPERATIONS_CHANGED')
    mission = MissionLedger(store).snapshot(job['mission_id'])
    if job.get('line_role_authority_ref'):
        from .line_recovery_control import configuration

        control = configuration(job['line_role_authority_ref'], eff, request=L.request_for(order))
        with store.tx() as c:
            raw = c.execute('SELECT record FROM afo_missions WHERE mission_id=?', (job['mission_id'],)).fetchone()
        registered = json.loads(raw[0]) if raw else {}
        if (control['operations_intent'] != raw_intent or control['profile'] != job['profile']
                or control['profile_sha256'] != job['profile_sha256']
                or job['mission_id'] != control['mission']['mission_id']
                or registered.get('lineage') != control['mission']['lineage']
                or registered.get('limits') != control['mission']['limits']
                or registered.get('authorization_ref') != control['authorization_ref']):
            raise Refused('LINE_MAINTENANCE_CONTROL_MISSION_OR_INTENT_CHANGED')
    if time.time() >= _review_deadline(store, job, mission=mission):
        raise Refused('LINE_MAINTENANCE_DEADLINE')
    return order


def _quiet(store, client, job):
    # Verify this role's native/provider ownership, not unrelated eligible jobs.
    # CPU-only CRE review does not own the GPU or stop another product.
    execution = Executions(store).get(job['job_id'])
    if (not execution or execution['execution_liveness'] != 'QUIESCENT'
            or execution['resource_lease'] != 'RELEASED' or not job.get('run_id')
            or set(execution['native_run_ids']) != {job['run_id']}):
        return False
    try:
        from ..fabro.client import run_status

        native = client.get_run(job['run_id'])
        labels = native.get('labels') or {}
        return (native.get('id') == job['run_id'] and labels.get('afo_agent') == job['job_id']
                and labels.get('afo_nonce') == job['nonce']
                and native.get('source_directory') == str(L.directory(job['job_id']) / 'workspace')
                and run_status(native) in ('SUCCEEDED', 'FAILED', 'CANCELLED', 'CANCELED'))
    except Exception:
        return False


def _dispatch_review(store, job):
    queue = VerificationJobs(store)
    queue.ensure(job['job_id'], job['case_sha256'], deadline_epoch=_review_deadline(store, job),
                 cap_deadline=True)

    def spawn(epoch):
        log = L.directory(job['job_id']) / 'line-review.log'
        log.parent.mkdir(parents=True, exist_ok=True)
        env = {**os.environ, **L.execution_context(job), 'PYTHONPATH': str(REPO_ROOT / 'factory/python'),
               'FORGE_AFO_QUEUE_SCOPE': 'line-local'}
        with log.open('ab') as out:
            subprocess.Popen([sys.executable, '-m', __name__, 'review', '--job', job['job_id'],
                              '--epoch', str(epoch)], cwd=REPO_ROOT / 'factory/python', env=env,
                             stdin=subprocess.DEVNULL, stdout=out, stderr=out, start_new_session=True)

    queue.dispatch(job['job_id'], spawn)


def step(store, order, attempt, bundle, workspace, eff, *, line_origin, line_role_authority_ref, client):
    """One existing-worker step. Caller owns the source order/REPLAN transitions."""
    if (any(not isinstance(bundle.get(k), str) or not bundle[k]
            for k in ('order_id', 'attempt_id', 'bundle_id', 'failure_class', 'fingerprint', 'error_code'))
            or bundle.get('failure_class') != 'FACTORY_CODE_DEFECT'
            or bundle.get('order_id') != order.get('order_id')
            or bundle.get('attempt_id') != attempt.get('attempt_id')
            or attempt.get('state') not in ('FAILED', 'SUCCEEDED')):
        return {'status': 'BLOCKED', 'code': 'LINE_MAINTENANCE_FACTORY_SOURCE_REQUIRED'}
    try:
        case = binding.prepare(store, order['order_id'], attempt['attempt_id'], Path(workspace),
                               line_origin, eff=eff)
        if any(case['incident'].get(k) != str(bundle[k])[:400]
               for k in ('order_id', 'attempt_id', 'bundle_id', 'failure_class', 'fingerprint', 'error_code')):
            raise Refused('LINE_MAINTENANCE_BUNDLE_CHANGED')
        failure = case.get('line_failure_bundle') or {}
        if failure.get('sha256') != digest(bundle) or failure.get('record') != bundle:
            raise Refused('LINE_MAINTENANCE_FULL_FAILURE_REQUIRED')
        options = {'line_origin': line_origin}
        if line_role_authority_ref is not None:
            options['line_role_authority_ref'] = line_role_authority_ref
        job = L.prepare(store, order, attempt['attempt_id'], ROLE, M.case_dir(case['proposal_id']) / 'case.json',
                        Path(workspace), eff, **options)
        job = L.poll(store, order, job, eff, client=client)
        if job['state'] != 'SUCCEEDED':
            if job['state'] in ('FAILED', 'TIMED_OUT', 'REVOKED') and not Executions(store).pending():
                return {'status': 'BLOCKED', 'job_id': job['job_id'], 'code': job.get('error', job['state'])}
            return {'status': 'MAINTENANCE_PENDING', 'job_id': job['job_id'], 'state': job['state']}
        _authorized(store, job, eff)
        if not _quiet(store, client, job):
            return {'status': 'MAINTENANCE_PENDING', 'job_id': job['job_id'], 'code': 'QUIESCENCE_UNPROVEN'}
        M.submission(case, require_receipt=True)
        _dispatch_review(store, job)
        review = VerificationJobs(store).get(job['job_id'])
        if review['state'] == 'COMPLETE':
            result = review['record'].get('result') or {}
            if digest(result) != review['record'].get('result_sha256'):
                raise Refused('LINE_MAINTENANCE_REVIEW_CHANGED')
            return {'status': 'WAITING_EXTERNAL_CHANGE', 'job_id': job['job_id'],
                    'review': result, 'source_deployed': False, 'publication': 'OFFLINE_ONLY'}
        if review['state'] == 'BLOCKED':
            return {'status': 'BLOCKED', 'job_id': job['job_id'], 'code': 'LINE_MAINTENANCE_VERIFIER_BLOCKED'}
        return {'status': 'MAINTENANCE_PENDING', 'job_id': job['job_id'], 'state': 'INDEPENDENT_REVIEW_PENDING'}
    except (OSError, ValueError, QueueError, Refused, M.MaintainerDenied) as exc:
        return {'status': 'BLOCKED', 'code': _code(exc)}


def review(store, job, eff, *, fence, client, evaluator=None):
    """Existing CRE process only; no broker publication or automatic source activation."""
    from ..reliability.policy import load as cre_policy
    from ..reliability.store import CREStore
    from ..reliability import promotion
    from .completion_receipt import Context

    _authorized(store, job, eff)
    Context.from_job(store, job['job_id'])
    if not fence() or not _quiet(store, client, job):
        raise Refused('LINE_MAINTENANCE_REVIEW_NOT_QUIESCENT_OR_FENCED')
    case = M.load_case(Path(job['case']).parent.name)
    sub, _ = M.submission(case, require_receipt=True)
    prior = store.proposal(case['proposal_id'])
    if prior:
        record = prior['record']
        if (record['baseline_commit'] != case['base'] or record['candidate_commit'] != sub['candidate']
                or record['tests_ref'] != 'local-agent:' + job['job_id']
                or record.get('auto_deployment_allowed') is not False):
            raise Refused('LINE_MAINTENANCE_REVIEW_REBOUND')
        return {'status': prior['status'], 'proposal_id': case['proposal_id'],
                'cre_promotion_id': record['cre_promotion_id'], 'source_deployed': False}

    def guarded_evaluator(*args, **kwargs):
        from .policy import load

        _authorized(store, job, load())
        if not fence() or not _quiet(store, client, job):
            raise Refused('LINE_MAINTENANCE_EVALUATION_FENCED')
        return (evaluator or promotion.evaluate)(*args, **kwargs)

    def expired(*_):
        if managed_owner:
            from .line_verifier_guard import terminate

            terminate(managed_owner)
        raise TimeoutError('LINE_MAINTENANCE_REVIEW_DEADLINE')

    from .line_verifier_guard import owned_group, watch_intent

    managed_owner = owned_group(VerificationJobs(store), job['job_id'])
    deadline = _review_deadline(store, job)
    previous = signal.signal(signal.SIGALRM, expired)
    try:
        remaining = deadline - time.time()
        if remaining <= 0:
            raise TimeoutError('LINE_MAINTENANCE_REVIEW_DEADLINE')
        # Fractional remaining walls cannot receive an extra second through alarm(1).
        signal.setitimer(signal.ITIMER_REAL, remaining)
        with watch_intent(managed_owner, job) if managed_owner else nullcontext():
            record = M.process(store, case['proposal_id'], CREStore(), cre_policy(),
                               fingerprints=[case['incident']['fingerprint']],
                               tests_ref='local-agent:' + job['job_id'], evaluator=guarded_evaluator)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    from .policy import load

    _authorized(store, job, load())
    if not fence() or record.get('auto_deployment_allowed') is not False:
        raise Refused('LINE_MAINTENANCE_REVIEW_RESULT_FENCED')
    return {'status': record['outcome'], 'proposal_id': case['proposal_id'],
            'cre_promotion_id': record['cre_promotion_id'], 'source_deployed': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['review'])
    parser.add_argument('--job', required=True)
    parser.add_argument('--epoch', required=True, type=int)
    args = parser.parse_args(argv)
    from ..fabro.client import FabroClient, load_token
    from .policy import load

    store = Store(state_dir() / 'supervisor/line-queue.sqlite3', must_exist=True)
    queue = VerificationJobs(store)
    queue.claim(args.job, args.epoch, dedicated_group=True)
    job = _saved(store, args.job)
    try:
        from .line_verifier_guard import owned_group, require_backend

        if not owned_group(queue, args.job):
            raise Refused('LINE_MAINTENANCE_MANAGED_GROUP_UNCONFIRMED')
        require_backend()
        with queue.keepalive(args.job, args.epoch), FabroClient(
                base_url=L.endpoint_for(job), token=load_token(job.get('fabro_storage')), timeout=5) as client:
            result = review(store, job, load(), fence=lambda: queue.current(args.job, args.epoch), client=client)
    except Exception as exc:
        result = {'status': 'BLOCKED', 'code': _code(exc), 'source_deployed': False}
    queue.finish(args.job, args.epoch, result)
    return 0 if result['status'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW' else 2


if __name__ == '__main__':
    raise SystemExit(main())
