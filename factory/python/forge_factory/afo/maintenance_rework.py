"""Bounded retained Maintainer feedback inside the existing review worker and Conductor.

The verifier seals a child case; the Conductor alone admits/polls its normal local
agent job. There is no new order, scheduler, budget, evaluator or deployment power.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

from ..common import sha256_file
from .durable import Refused, digest, immutable_json, strict_json

MAX_REWORKS = 8
MAX_FEEDBACK_BYTES = 32768


def limit(eff):
    value = eff.get('maintenance.max_retained_reworks', 0)
    if type(value) is not int or not 0 <= value <= MAX_REWORKS:
        raise Refused('MAINTENANCE_REWORK_LIMIT_INVALID')
    return value


def _case(job):
    path = Path(job['case'])
    if path.is_symlink() or sha256_file(path) != job['case_sha256']:
        raise Refused('MAINTENANCE_REWORK_CASE_CHANGED')
    return strict_json(path.read_bytes(), 65536)


def _parent(store, job):
    from . import maintainer as M
    from .execution_lifecycle import Executions

    if not job.get('durable_native') or job['role'] != 'afo-factory-maintainer':
        raise Refused('MAINTENANCE_REWORK_DURABLE_PARENT_REQUIRED')
    execution = Executions(store).get(job['job_id'])
    if not execution or execution['execution_liveness'] != 'QUIESCENT' or execution['resource_lease'] != 'RELEASED':
        raise Refused('MAINTENANCE_REWORK_PARENT_NOT_QUIESCENT')
    case = _case(job)
    sub, receipt = M.submission(case, require_receipt=True)
    projection = store.proposal(case['proposal_id'])
    if not projection or projection['status'] != 'REJECTED':
        raise Refused('MAINTENANCE_REWORK_INDEPENDENT_REJECTION_REQUIRED')
    raw = json.dumps(projection['record'], sort_keys=True).encode()
    if hashlib.sha256(raw).hexdigest() != projection['record_sha256']:
        raise Refused('MAINTENANCE_REWORK_DECISION_CHANGED')
    record = projection['record']
    if (sub['veto'] or record.get('protected_changes_count') != 0
            or record['candidate_commit'] != sub['candidate'] or record['baseline_commit'] != case['base']
            or M.veto(case['base'], sub['candidate'], Path(case['repo']))):
        raise Refused('MAINTENANCE_REWORK_UNSAFE_CANDIDATE')
    return case, sub, receipt, projection


def _allowed(store, job, eff):
    from ..workorder import factory_revision
    from . import local_agent as L
    from .mission_ledger import MissionLedger
    from .operations import Intent, configured

    order = store.order(job['order_id'])
    revision = factory_revision()
    if (eff.mode not in ('PILOT', 'ACTIVE') or eff.sha256 != job['policy_sha256']
            or not L.enabled(job['role'], eff) or not L.authorized(order, eff, job['model'])
            or revision.get('dirty') or revision.get('commit') != job['factory_revision'].get('commit')):
        raise Refused('MAINTENANCE_REWORK_AUTHORITY_CHANGED')
    if configured() and Intent().read()['mode'] != 'RUNNING':
        raise Refused('OPERATIONS_ADMISSION_REFUSED')
    snapshot = MissionLedger(store).snapshot(job['mission_id'])
    caps = snapshot['limits']
    if time.time() >= min(job['deadline_epoch'], caps['deadline']):
        raise Refused('MISSION_DEADLINE_EXHAUSTED')
    jobs = L.records(store, job['order_id'])
    tokens = job['reserved_tokens']
    if (len(jobs) >= int(eff.get('budgets.max_recovery_model_calls_per_order'))
            or sum(j['reserved_tokens'] for j in jobs) + tokens > int(eff.get('budgets.max_model_tokens_per_order'))
            or snapshot['jobs'] >= caps['max_jobs'] or snapshot['charged_tokens'] + tokens > caps['max_tokens']
            or snapshot['requests'] >= caps['max_requests'] or snapshot['tools'] >= caps['max_tools']
            or snapshot['unbounded_historical_usage']):
        raise Refused('MAINTENANCE_REWORK_ALLOWANCE_EXHAUSTED')


def _feedback(case, sub, projection):
    from ..common import state_dir
    from ..reliability import reproduce
    from ..reliability.store import CREStore
    from .bundle import redact

    reproducers, issues = reproduce.load_manifest(Path(sub['staged']['manifest']))
    registered = reproducers.get(sub['staged']['id'])
    if issues or registered is None:
        raise Refused('MAINTENANCE_REWORK_REPRODUCER_MANIFEST_INVALID')
    runs = reproduce.reproducer_runs(CREStore(), sub['staged']['id'])
    if len(runs) > 32:
        raise Refused('MAINTENANCE_REWORK_FEEDBACK_TOO_LARGE')
    facts = []
    for row in runs:
        log = state_dir() / 'reliability/reproducers' / (row['run_id'] + '.log')
        if log.is_symlink() or sha256_file(log) != row['log_sha256']:
            raise Refused('MAINTENANCE_REWORK_REPRODUCER_EVIDENCE_CHANGED')
        raw = log.read_bytes()
        if len(raw) > MAX_FEEDBACK_BYTES:
            raise Refused('MAINTENANCE_REWORK_FEEDBACK_TOO_LARGE')
        facts.append({**row, 'log': redact(raw.decode(errors='replace'))})
    feedback = {'schema': 'forge-c/maintenance-independent-feedback/1', 'untrusted_data': True,
                'proposal': projection['record'], 'proposal_record_sha256': projection['record_sha256'],
                'registered_symptom_signature': registered['symptom_signature'],
                'staged_manifest_sha256': sha256_file(Path(sub['staged']['manifest'])),
                'reproducer_runs': facts, 'instructions_or_permissions': False}
    if len(json.dumps(feedback).encode()) > MAX_FEEDBACK_BYTES:
        raise Refused('MAINTENANCE_REWORK_FEEDBACK_TOO_LARGE')
    return feedback


def prepare_next(store, job, eff, *, verification_fence):
    """Only the existing fenced independent worker calls this after a recorded rejection."""
    from . import maintainer as M

    maximum = limit(eff)
    if not maximum:
        return None
    case, sub, receipt, projection = _parent(store, job)
    old = case.get('retained_rework') or {}
    index = old.get('index', 0) + 1
    root_pid = old.get('root_proposal_id', case['proposal_id'])
    root_attempt = old.get('root_attempt_id', job['attempt_id'])
    if type(index) is not int or index > maximum:
        return {'state': 'EXHAUSTED', 'reason': 'MAINTENANCE_REWORK_LIMIT_REACHED'}
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,160}', root_attempt):
        raise Refused('MAINTENANCE_REWORK_ROOT_INVALID')
    pid = root_pid + f'-r{index}'
    directory = M.case_dir(pid)
    intent_path = directory / 'retained-intent.json'
    reference_path = directory / 'retained-ready.json'
    if not reference_path.exists():
        _allowed(store, job, eff)
        if not verification_fence():
            raise Refused('VERIFICATION_PUBLICATION_FENCED')
    identity = {'schema': 'forge-c/maintenance-retained-intent/1', 'parent_job_id': job['job_id'],
                'parent_case_sha256': job['case_sha256'], 'parent_receipt_sha256': digest(receipt),
                'parent_candidate': sub['candidate'], 'parent_proposal_sha256': projection['record_sha256'],
                'order_id': job['order_id'], 'mission_id': job['mission_id'], 'root_proposal_id': root_pid,
                'root_attempt_id': root_attempt, 'index': index, 'deadline_epoch': job['deadline_epoch']}
    feedback_path = directory / 'independent-feedback.json'
    if intent_path.exists():
        sealed = strict_json(intent_path.read_bytes(), 65536)
        if {k: v for k, v in sealed.items() if k != 'feedback_sha256'} != identity:
            raise Refused('MAINTENANCE_REWORK_INTENT_CHANGED')
        feedback = strict_json(feedback_path.read_bytes(), MAX_FEEDBACK_BYTES)
        if sha256_file(feedback_path) != sealed['feedback_sha256']:
            raise Refused('MAINTENANCE_REWORK_FEEDBACK_CHANGED')
        identity = sealed
    else:
        feedback = _feedback(case, sub, projection)
        # A partial unpublished feedback write is reusable only if its exact facts still match.
        feedback_sha = immutable_json(feedback_path, feedback)
        identity = {**identity, 'feedback_sha256': feedback_sha}
        immutable_json(intent_path, identity)
    feedback_sha = identity['feedback_sha256']
    if reference_path.exists():
        reference = strict_json(reference_path.read_bytes(), 65536)
        _check_reference(job, reference, identity, directory)
        return reference  # historical receipt, no admission or fresh authority
    _allowed(store, job, eff)
    if not verification_fence():
        raise Refused('VERIFICATION_PUBLICATION_FENCED')
    files = {}
    for rel in M.changed_paths(case['base'], sub['candidate'], Path(case['repo'])):
        if not re.fullmatch(r'[A-Za-z0-9_./-]{1,200}', rel) or M.path_issue(rel, M.protected_globs()):
            raise Refused('MAINTENANCE_REWORK_SOURCE_INVALID')
        raw = subprocess.run(['git', '-C', case['repo'], 'show', sub['candidate'] + ':' + rel],
                             capture_output=True, check=True, timeout=120).stdout
        if len(raw) > M.MAX_FILE_BYTES:
            raise Refused('MAINTENANCE_REWORK_SOURCE_TOO_LARGE')
        try:
            raw.decode('utf-8')
        except UnicodeError as exc:
            raise Refused('MAINTENANCE_REWORK_BINARY_SOURCE') from exc
        files[rel] = raw
    if not files or len(files) > M.MAX_PATHS:
        raise Refused('MAINTENANCE_REWORK_SOURCE_INVALID')
    metadata = {**identity, 'feedback_sha256': feedback_sha, 'feedback': feedback,
                'files': [{'path': rel, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
                          for rel, raw in sorted(files.items())]}
    target_path = directory / 'case.json'
    if target_path.exists():
        target = strict_json(target_path.read_bytes(), 65536)
        if target.get('retained_rework') != metadata or target['base'] != case['base']:
            raise Refused('MAINTENANCE_REWORK_CASE_CHANGED')
    else:
        target = M.prepare(pid, case['base'], case['incident'], repo=Path(case['repo']), retained_rework=metadata)
    # No child job exists until the complete reference is sealed by this worker.
    for rel, raw in files.items():
        if M.write_source(target, rel, raw.decode()) != hashlib.sha256(raw).hexdigest():
            raise Refused('MAINTENANCE_REWORK_SEED_CHANGED')
    seed = {'intent_sha256': digest(identity), 'case_sha256': sha256_file(target_path),
            'files': metadata['files'], 'operator_or_controller_authored_repair': False}
    immutable_json(directory / 'retained-seed.json', seed)
    _allowed(store, job, eff)
    if not verification_fence():
        raise Refused('VERIFICATION_PUBLICATION_FENCED')
    reference = {'state': 'READY', 'schema': 'forge-c/maintenance-retained-reference/1',
                 'parent_job_id': job['job_id'], 'proposal_id': pid, 'root_attempt_id': root_attempt,
                 'attempt_id': root_attempt + f'-mr{index}', 'index': index,
                 'case_sha256': sha256_file(target_path), 'seed_sha256': digest(seed)}
    immutable_json(reference_path, reference)
    return reference


def _check_reference(parent, reference, identity, directory):
    path = directory / 'case.json'
    seed = strict_json((directory / 'retained-seed.json').read_bytes(), 65536)
    if (reference.get('schema') != 'forge-c/maintenance-retained-reference/1'
            or reference['parent_job_id'] != parent['job_id'] or identity['parent_job_id'] != parent['job_id']
            or reference['proposal_id'] != directory.name or reference['root_attempt_id'] != identity['root_attempt_id']
            or sha256_file(path) != reference['case_sha256'] or digest(seed) != reference['seed_sha256']
            or seed['case_sha256'] != reference['case_sha256'] or seed['intent_sha256'] != digest(identity)
            or identity['order_id'] != parent['order_id'] or identity['mission_id'] != parent['mission_id']
            or reference['index'] != identity['index'] or not 1 <= reference['index'] <= MAX_REWORKS
            or reference['attempt_id'] != identity['root_attempt_id'] + f"-mr{identity['index']}"):
        raise Refused('MAINTENANCE_REWORK_BINDING_CHANGED')
    return path


def next_binding(store, parent, eff):
    """Use only a completed, hash-checked worker result; no arbitrary filesystem scan or model binding."""
    from . import maintainer as M
    from .verification_job import VerificationJobs

    row = VerificationJobs(store).get(parent['job_id'])
    if not row or row['state'] != 'COMPLETE':
        return None
    result = row['record'].get('result') or {}
    if digest(result) != row['record'].get('result_sha256'):
        raise Refused('MAINTENANCE_REWORK_RESULT_CHANGED')
    reference = result.get('maintenance_rework')
    if not reference or reference.get('state') != 'READY' or result.get('status') != 'REJECTED':
        return None
    directory = M.case_dir(reference['proposal_id'])
    if strict_json((directory / 'retained-ready.json').read_bytes(), 65536) != reference:
        raise Refused('MAINTENANCE_REWORK_REFERENCE_CHANGED')
    case = strict_json((directory / 'case.json').read_bytes(), 65536)
    identity = strict_json((directory / 'retained-intent.json').read_bytes(), 65536)
    if {k: v for k, v in case['retained_rework'].items() if k not in ('feedback', 'files')} != identity:
        raise Refused('MAINTENANCE_REWORK_CASE_CHANGED')
    path = _check_reference(parent, reference, identity, directory)
    if reference['index'] > limit(eff):
        return None
    # Preparing an already recorded child job is idempotent; its budget is already charged.
    from .local_agent import records

    if not any(j['attempt_id'] == reference['attempt_id'] and j['role'] == parent['role']
               for j in records(store, parent['order_id'])):
        _allowed(store, parent, eff)
    return path, reference['attempt_id']
