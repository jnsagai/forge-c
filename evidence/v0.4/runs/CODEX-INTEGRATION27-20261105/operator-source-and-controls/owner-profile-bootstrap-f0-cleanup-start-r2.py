"""External operator sequence for two separately reviewed helpers; default PLAN_ONLY.

The source helpers retain all authority, physical and one-attempt guards.
Run on Omniverse only after fresh ticket and reviewed starter are installed.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

F = Path('/mnt/data/forge-c/swe1-fabro-20261031')
R = F / 'qualification/owner-profile-bootstrap-f0c8fc5c-review-20261105'
OPS = R / 'owner-main-ops'
FAILED = F / 'qualification/owner-profile-bootstrap-88782030-review-20261105'
FAILED214 = F / 'qualification/owner-profile-bootstrap-214c9668-review-20261105'
PYTHON = F / 'lrtx/venv/bin/python'
SOURCE = 'f0c8fc5c8ae83952a05cea578d41e0ff06324afd'
CLEANUP_SHA = 'ed6c1cdb08c1fff6fe75f86763e6aac31fbe11cb55790bcaaf969bc064848c8f'
EXPECT_SHA = '95ad72cc87510751a6f64304cfa809c2872001d2520b63f0abe9faf3ae1b3c6f'
STARTER_SHA = 'fa044e4edcf492940289f2cea98995527839cdcdc097418fc60ea9892155c118'
BINDING_SHA = '576c8af67548e57efb1363c8f80f117600ac4c067ffa9dbe6d60782237ef9733'
META_SHA = 'f5bd26320b909969b0fea194ea5018da57ff69868f1d81c5d65df1289ccde14c'



def need(ok, code):
    if not ok:
        raise RuntimeError(code)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def emit(path, value):
    with path.open('x') as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump(value, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())


def validate_ticket(path):
    """Normal fixed-deadline UTC witness check before cleanup; never mint or re-age."""
    source=R/'newS'
    revision=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True,timeout=10).strip()
    need(revision==SOURCE and not subprocess.check_output(['git','-C',str(source),'status','--porcelain'],timeout=10), 'NEW_SOURCE_CHANGED')
    sys.path.insert(0,str(source/'factory/python'))
    from forge_factory.afo import owner_supervised_development as D
    need(Path(D.__file__).resolve()==source/'factory/python/forge_factory/afo/owner_supervised_development.py','EXPIRY_VALIDATOR_IMPORT_REBOUND')
    D.validate_expiry_ticket(json.loads(path.read_bytes()),1795057626.0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply-reviewed', action='store_true')
    parser.add_argument('--starter', type=Path)
    parser.add_argument('--starter-sha256')
    parser.add_argument('--ticket', type=Path)
    parser.add_argument('--ticket-sha256')
    parser.add_argument('--metadata-receipt-sha256')
    args = parser.parse_args()
    if not args.apply_reviewed:
        print(json.dumps({'status': 'PLAN_ONLY', 'effects': False, 'source': SOURCE}))
        return
    # Preserve refusal facts before constructing a clean child environment.
    forbidden = ('FORGE_AGENT_ROLE', 'FORGE_WORKSPACE', 'FORGE_POLICY_BINDING',
                 'FORGE_OWNER_DEVELOPMENT_RECORD', 'FORGE_OWNER_DEVELOPMENT_SHA256',
                 'FORGE_LINE_STACK_PAYLOAD', 'FORGE_LINE_STACK_PAYLOAD_SHA256', 'FORGE_STACK_LOCK_FD')
    need(not any(os.environ.get(key) for key in forbidden), 'CLEAN_EXTERNAL_OPERATOR_CONTEXT_REQUIRED')
    need(__debug__ and os.getuid() == 1000, 'INITIAL_EXTERNAL_OWNER_REQUIRED')
    need(Path('/proc/self/uid_map').read_text().split() == ['0', '0', '4294967295'], 'INITIAL_NAMESPACE_REQUIRED')
    need(Path(__file__).resolve().parent == OPS, 'EXACT_SEQUENCE_LOCATION_REQUIRED')
    need(args.starter is not None and args.starter.parent == OPS
         and args.starter.name == 'start-main-reviewed.py' and args.starter_sha256 == STARTER_SHA, 'REVIEWED_STARTER_REQUIRED')
    need(args.ticket is not None and args.ticket.parent == OPS, 'EXACT_TICKET_LOCATION_REQUIRED')
    need(args.metadata_receipt_sha256==META_SHA,'EXACT_REVIEWED_METADATA_RECEIPT_REQUIRED')
    for path, expected in ((OPS / 'cleanup-exact-failed642-v3.py', CLEANUP_SHA),
                           (OPS / 'exact-642-expectation-v2.json', EXPECT_SHA),
                           (OPS / 'binding.json', BINDING_SHA),
                           (args.starter, args.starter_sha256), (args.ticket, args.ticket_sha256),
                           (R / 'metadata-f0-reviewed/result.json', args.metadata_receipt_sha256)):
        need(re.fullmatch('[0-9a-f]{64}', expected or '') and not path.is_symlink()
             and path.is_file() and sha(path) == expected, 'REVIEWED_INPUT_CHANGED')
    # This is a separately reviewed continuation; the first failure stays immutable.
    need(sha(FAILED214 / 'partial-reconciliation-r1/intent.json') ==
         '60163c6107266a4e61d88e5bf185b54692e106e2fdb3c61d4bc69bdfab5d1225'
         and sha(FAILED214 / 'partial-reconciliation-r1/unknown-result.json') ==
         'c0f762ac261fc5e1f95738a66f8f606e3c433696d40e17d5a1244623c84a95a0',
         'ORIGINAL_FAILED_CLEANUP_AUDIT_CHANGED')
    meta=json.loads((R/'metadata-f0-reviewed/result.json').read_bytes())
    need(meta.get('state')=='METADATA_APPENDED_NO_RUNTIME_START' and meta.get('source')==SOURCE
         and meta.get('binding_sha256')==BINDING_SHA, 'REVIEWED_METADATA_SCOPE_CHANGED')
    marker = R / 'root-cleanup-start-f0-attempt-r1.json'
    need(not marker.exists() and not (FAILED / 'partial-reconciliation-642-f0-r1').exists(), 'ALREADY_ATTEMPTED_NO_REPLAY')
    need(not (R / 'owner-main-start-attempt-f0.json').exists(), 'MAIN_ALREADY_ATTEMPTED')
    env = {key: value for key, value in os.environ.items() if not key.startswith('FORGE_')}
    env.update(FORGE_REPO_ROOT=str(FAILED / 'newS'), PYTHONPATH=str(FAILED / 'newS/factory/python'),
               FORGE_DATA_ROOT='/mnt/data/forge-c', FORGE_STATE_DIR=str(F / 'lrtx/state'),
               FORGE_OPERATIONS_INTENT='/home/omniverse2/.config/forge-c/line-local/operations-intent.json',
               FORGE_LINE_LAUNCH_DIR=str(F), FORGE_LINE_ID='local', PYTHONDONTWRITEBYTECODE='1')
    validate_ticket(args.ticket)
    emit(marker, {'state': 'REVIEWED_CLEANUP_THEN_EXPLICIT_START_NO_REPLAY', 'source': SOURCE,
                  'cleanup_sha256': CLEANUP_SHA, 'starter_sha256': args.starter_sha256,
                  'ticket_sha256': args.ticket_sha256, 'metadata_sha256': args.metadata_receipt_sha256})
    def run(label, command, timeout):
        with (R / ('root-' + label + '-f0-r1.stdout.log')).open('xb') as output, \
                (R / ('root-' + label + '-f0-r1.stderr.log')).open('xb') as error:
            os.fchmod(output.fileno(), 0o600)
            os.fchmod(error.fileno(), 0o600)
            result = subprocess.run([str(PYTHON), *command], env=env, stdout=output, stderr=error, timeout=timeout)
        need(result.returncode == 0, label.upper() + '_FAILED_INSPECT_ONLY_NO_RETRY')
    try:
        validate_ticket(args.ticket)
        run('cleanup642', [str(OPS / 'cleanup-exact-failed642-v3.py'), '--apply-reviewed',
                           '--next-source-revision', SOURCE], 110)
        result_path = FAILED / 'partial-reconciliation-642-f0-r1/verified-result.json'
        cleanup = json.loads(result_path.read_bytes())
        need(cleanup['status'] == 'EXACT_PARTIAL_LIFETIMES_QUIET_HISTORY_CONSERVED', 'CLEANUP_NOT_PROVEN')
        evidence = cleanup['evidence_ref']
        need(sha(Path(evidence['path'])) == evidence['sha256'], 'CLEANUP_EVIDENCE_CHANGED')
        env.update(FORGE_REPO_ROOT=str(R / 'newS'), PYTHONPATH=str(R / 'newS/factory/python'))
        run('startf0', [str(args.starter), '--start-reviewed', '--ticket', str(args.ticket),
                         '--ticket-sha256', args.ticket_sha256,
                         '--retirement-sha256', '8ba3a82529c419387fa462bc926be07d31dda07f432f951e3d6e6484206c10e6',
                         '--hardening-sha256', 'd71ae1f4bd683eaad6029c0a242185ae08eb8c06a47148c0e792db67cf79b919',
                         '--metadata-receipt-sha256', args.metadata_receipt_sha256,
                         '--cleanup-result-sha256', sha(result_path),
                         '--reconciliation-evidence-sha256', evidence['sha256'], '--readiness-seconds', '660'], 700)
        ready = json.loads((R / 'owner-main-readiness-f0.json').read_bytes())
        need(ready['state'] == 'NEW_MAIN_GUARDIAN_RECONCILED_BOOTSTRAP_READY_PLACING_SCOPE_UNACCEPTED', 'MAIN_NOT_READY')
        receipt = {'status': 'EXPLICIT_SEQUENCE_COMPLETED', 'source': SOURCE, 'readiness': ready,
                   'cleanup_result_sha256': sha(result_path), 'reconciliation_evidence_ref': evidence,
                   'no_product_phase_acceptance_claim': True}
        emit(R / 'root-cleanup-start-f0-result-r1.json', receipt)
        print(json.dumps(receipt))
    except BaseException as exc:
        emit(R / 'root-cleanup-start-f0-unknown-r1.json', {'status': 'UNKNOWN_INSPECT_ONLY_NO_RETRY',
             'error_type': type(exc).__name__, 'no_automatic_stop_or_rollback': True})
        raise


if __name__ == '__main__':
    main()
