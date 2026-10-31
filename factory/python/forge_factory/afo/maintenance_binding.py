"""Bound one legacy marker encoding without a new engineering/model attempt or weaker CRE gate."""
from __future__ import annotations

import copy
import json
import re
import time
from pathlib import Path

from ..common import sha256_bytes, sha256_file, state_dir
from .durable import Refused, digest, immutable_bytes, immutable_json, strict_json

PREFIX = "SYMPTOM_PRESENT:"


def _allowed(store, job, eff, fence):
    from . import local_agent as L
    from .completion_receipt import Context
    from .execution_lifecycle import Executions
    from .mission_ledger import MissionLedger
    from .operations import Intent, configured

    context = Context.from_job(store, job['job_id'])
    with store.tx() as c:
        saved = json.loads(c.execute('SELECT record FROM afo_local_agent_jobs WHERE job_id=?',
                                     (job['job_id'],)).fetchone()[0])
    keys = ('case', 'case_sha256', 'nonce', 'mission_id', 'order_id', 'role', 'deadline_epoch', 'policy_sha256', 'model')
    if any(saved.get(k) != job.get(k) for k in keys) or context.case_sha256 != job['case_sha256']:
        raise Refused('MAINTENANCE_BINDING_JOB_REBOUND')
    if (eff.mode not in ('PILOT', 'ACTIVE') or eff.sha256 != job['policy_sha256']
            or not L.authorized(store.order(job['order_id']), eff, job['model'])):
        raise Refused('MAINTENANCE_BINDING_NOT_AUTHORIZED')
    if configured() and Intent().read()['mode'] != 'RUNNING':
        raise Refused('OPERATIONS_ADMISSION_REFUSED')
    if Executions(store).pending() or not fence():
        raise Refused('MAINTENANCE_BINDING_NOT_QUIESCENT_OR_FENCED')
    snapshot = MissionLedger(store).snapshot(job['mission_id'])
    if time.time() >= min(job['deadline_epoch'], snapshot['limits']['deadline']):
        raise Refused('MISSION_DEADLINE_EXHAUSTED')


def prepare(store, job, eff, *, verification_fence):
    from . import maintainer as M
    from . import maintenance_rework as R
    from .mission_ledger import MissionLedger

    case = R._case(job)
    sub, receipt = M.submission(case, require_receipt=True)
    raw_manifest = strict_json(Path(sub['staged']['manifest']).read_bytes(), 65536)
    item = raw_manifest['reproducers'][0]
    registered = item['symptom_signature']
    if (not registered.startswith(PREFIX) or not registered[len(PREFIX):]
            or registered[len(PREFIX):].startswith(PREFIX)):
        raise Refused('MAINTENANCE_SIGNATURE_NOT_SINGLE_PREFIX_ENCODING')
    canonical = registered[len(PREFIX):]
    _allowed(store, job, eff, verification_fence)
    identity = {'nonce': job['nonce'], 'schema': 'forge-c/maintenance-signature-binding/1', 'job_id': job['job_id'],
                'policy_sha256': job['policy_sha256'], 'deadline_epoch': job['deadline_epoch'],
                'mission_id': job['mission_id'], 'case_sha256': job['case_sha256'],
                'original_receipt_sha256': digest(receipt), 'original_manifest_sha256': digest(raw_manifest),
                'candidate': sub['candidate'], 'raw_signature': registered, 'canonical_signature': canonical,
                'transformation': 'REMOVE_ONE_LITERAL_SYMPTOM_PRESENT_PREFIX'}
    bid = digest(identity)
    directory = M.case_dir(case['proposal_id']) / 'administrative-bindings' / bid
    if (directory / 'ready.json').exists():
        ref = strict_json((directory / 'ready.json').read_bytes(), 65536)
        bound_submission(store, case, sub, ref)
        return ref
    case, sub, receipt, projection = R._parent(store, job)
    # A format correction must match the actual independent baseline contract line.
    # An incorrect marker, different defect, unsafe candidate or other failure cannot use this path.
    facts = R._feedback(case, sub, projection)
    runs = [r for r in facts['reproducer_runs'] if r['role'] == 'BASELINE' and r['revision'] == case['base']]
    if not runs:
        raise Refused('MAINTENANCE_BINDING_BASELINE_EVIDENCE_REQUIRED')
    measured = runs[-1]
    if not re.fullmatch(r'rr-[0-9a-f]{20}', measured['run_id']):
        raise Refused('MAINTENANCE_BINDING_BASELINE_ID_INVALID')
    log = state_dir() / 'reliability/reproducers' / (measured['run_id'] + '.log')
    if log.is_symlink() or sha256_file(log) != measured['log_sha256']:
        raise Refused('MAINTENANCE_BINDING_BASELINE_EVIDENCE_CHANGED')
    stdout = log.read_text().split('\n--- stderr ---\n', 1)[0]
    lines = [line for line in stdout.splitlines() if line.strip()]
    if measured['verdict'] != 'ERROR' or measured['exit_code'] != 1 or not lines or lines[-1] != registered:
        raise Refused('MAINTENANCE_BINDING_NOT_ADMINISTRATIVE_ONLY')
    if projection['record']['cre_promotion_id'] != 'NOT_EVALUATED:REPRODUCER_DOES_NOT_FAIL_ON_BASELINE:ERROR':
        raise Refused('MAINTENANCE_BINDING_UNRELATED_REJECTION')
    manifest = copy.deepcopy(raw_manifest)
    manifest['reproducers'][0]['symptom_signature'] = canonical
    source = M.case_dir(case['proposal_id']) / 'reproducer/reproducer.py'
    script = source.read_bytes()
    if item['script'] != 'reproducer.py' or sha256_file(source) != item['sha256']:
        raise Refused('MAINTENANCE_BINDING_REPRODUCER_CHANGED')
    if directory.is_symlink() or directory.parent.is_symlink():
        raise Refused('MAINTENANCE_BINDING_UNSAFE_DIRECTORY')
    directory.mkdir(parents=True, exist_ok=True)
    intent = {**identity, 'source_proposal_record_sha256': projection['record_sha256'],
              'baseline_run': measured['run_id'], 'baseline_log_sha256': measured['log_sha256']}
    immutable_json(directory / 'intent.json', intent)
    _allowed(store, job, eff, verification_fence)
    MissionLedger(store).count(job['mission_id'], job['job_id'], 'CORRECTION', 'maint-signature:' + bid)
    immutable_bytes(directory / 'reproducer.py', script, 0o444)
    manifest_hash = immutable_json(directory / 'manifest.yaml', manifest)
    ref = {'schema': 'forge-c/maintenance-signature-binding-reference/1', 'binding_id': bid,
           'proposal_id': case['proposal_id'], 'job_id': job['job_id'], 'intent_sha256': digest(intent),
           'manifest_sha256': manifest_hash, 'original_receipt_sha256': digest(receipt)}
    _allowed(store, job, eff, verification_fence)
    immutable_json(directory / 'ready.json', ref)
    return ref


def bound_submission(store, case, sub, ref):
    """Hash-checked view for the existing triage/evaluator; never rewrite historical submission evidence."""
    from . import maintainer as M

    if (ref.get('schema') != 'forge-c/maintenance-signature-binding-reference/1'
            or ref['proposal_id'] != case['proposal_id'] or len(ref['binding_id']) != 64
            or any(c not in '0123456789abcdef' for c in ref['binding_id'])):
        raise Refused('MAINTENANCE_BINDING_REFERENCE_INVALID')
    directory = M.case_dir(case['proposal_id']) / 'administrative-bindings' / ref['binding_id']
    if ((directory / 'ready.json').is_symlink() or (directory / 'intent.json').is_symlink()
            or not (directory / 'ready.json').is_file()
            or strict_json((directory / 'ready.json').read_bytes(), 65536) != ref):
        raise Refused('MAINTENANCE_BINDING_REFERENCE_NOT_PUBLISHED')
    intent = strict_json((directory / 'intent.json').read_bytes(), 65536)
    manifest_path = directory / 'manifest.yaml'
    manifest = strict_json(manifest_path.read_bytes(), 65536)
    original, receipt = M.submission(case, require_receipt=True)
    raw = strict_json(Path(original['staged']['manifest']).read_bytes(), 65536)
    expected = copy.deepcopy(raw)
    value = raw['reproducers'][0]['symptom_signature']
    if not value.startswith(PREFIX):
        raise Refused('MAINTENANCE_BINDING_SOURCE_CHANGED')
    expected['reproducers'][0]['symptom_signature'] = value[len(PREFIX):]
    with store.tx() as c:
        counter = c.execute('SELECT * FROM afo_mission_counters WHERE event_id=?',
                            ('maint-signature:' + ref['binding_id'],)).fetchone()
        source_decision = c.execute('SELECT record,record_sha256 FROM afo_maintainer_proposals WHERE proposal_id=? '
                                    'AND record_sha256=?',
                                    (case['proposal_id'], intent['source_proposal_record_sha256'])).fetchone()
    from .completion_receipt import Context

    context = Context.from_job(store, ref['job_id'])
    identity = {k: v for k, v in intent.items()
                if k not in ('source_proposal_record_sha256', 'baseline_run', 'baseline_log_sha256')}
    if (digest(identity) != ref['binding_id'] or identity['job_id'] != ref['job_id']
            or identity['nonce'] != context.launch_nonce or identity['case_sha256'] != context.case_sha256
            or identity['mission_id'] != context.mission_id
            or directory.is_symlink() or directory.parent.is_symlink()
            or digest(intent) != ref['intent_sha256'] or digest(receipt) != ref['original_receipt_sha256']
            or digest(receipt) != intent['original_receipt_sha256']
            or intent['raw_signature'] != value or intent['canonical_signature'] != value[len(PREFIX):]
            or digest(raw) != intent['original_manifest_sha256'] or original != sub or not source_decision
            or sha256_bytes(json.dumps(json.loads(source_decision['record']), sort_keys=True).encode())
                != source_decision['record_sha256']
            or intent['candidate'] != sub['candidate'] or sha256_file(manifest_path) != ref['manifest_sha256']
            or manifest != expected or sha256_file(directory / 'reproducer.py') != raw['reproducers'][0]['sha256']
            or manifest_path.is_symlink() or (directory / 'reproducer.py').is_symlink()
            or not counter or (counter['mission_id'], counter['job_id'], counter['kind']) != (
                intent['mission_id'], ref['job_id'], 'CORRECTION')):
        raise Refused('MAINTENANCE_BINDING_CHANGED_OR_UNCHARGED')
    result = copy.deepcopy(sub)
    result['staged']['manifest'] = str(manifest_path)
    return result
