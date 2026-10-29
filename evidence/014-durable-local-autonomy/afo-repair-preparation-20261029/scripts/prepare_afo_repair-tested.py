"""Prepare a historical AFO maintenance trial. No intake, grant, deployment or model request."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from datetime import datetime, timezone


BASE = '9b4c390e1605d11c4865bdeea382df74a0078692'
CONTROLLER = '3015e47f93de7bfd1e81c8dd7bf4426d8c13ddc6'
TARGET = 'factory/python/forge_factory/fabro/runconfig.py'
PROFILE = 'local-rtx-v2-omniverse2-q38-qm-mtp'
MODEL = 'qwen3.8:27b-q8_0'
MISSION = 'F014-IDR-M1-HIGH-20261028'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(root, name, value):
    p = root / name
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    raw = value if isinstance(value, bytes) else (json.dumps(value, indent=2) + '\n').encode()
    with p.open('xb') as f:
        f.write(raw)
    p.chmod(0o600)
    return {'path': name, 'sha256': sha(raw), 'bytes': len(raw)}


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], timeout=60)


def export_source(repo, revision, target):
    target.mkdir(mode=0o700)
    raw = git(repo, 'archive', revision, 'factory/python', 'config/factory', '.fabro')
    with tarfile.open(fileobj=io.BytesIO(raw)) as archive:
        for member in archive.getmembers():
            rel = Path(member.name)
            if rel.is_absolute() or '..' in rel.parts or not (member.isdir() or member.isfile()):
                raise ValueError('UNSAFE_CONTROL_ARCHIVE')
        archive.extractall(target, filter='data')
    return target


def prepare(repo, root, snapshot, prerequisites, grader, python):
    import yaml

    repo, root = Path(repo).resolve(), Path(root).resolve()
    if root.exists():
        raise ValueError('PREPARATION_ROOT_ALREADY_EXISTS')
    profile_path = repo / f'config/factory/profiles/{PROFILE}.yaml'
    profile = yaml.safe_load(profile_path.read_bytes())
    if profile.get('development_execution_policy') or profile['models']['default'] != MODEL:
        raise ValueError('NONDEFERRED_QWEN_PROFILE_REQUIRED')
    if snapshot['mission']['mission_id'] != MISSION:
        raise ValueError('PRIOR_MISSION_REQUIRED')
    if snapshot['production_revision'] != BASE:
        raise ValueError('HISTORICAL_BASELINE_MUST_MATCH_REVIEWED_FAILURE')
    if snapshot['operator'] != {'mode': 'STOPPED', 'epoch': 33, 'effective_stop': True}:
        raise ValueError('PREPARATION_EXPECTS_CURRENT_STOP_ONLY')
    if snapshot['outstanding_requests'] or not snapshot['provider_quiet']:
        raise ValueError('NATIVE_QUIESCENCE_REQUIRED')
    root.mkdir(parents=True, mode=0o700)
    historical_evidence = []
    prefix = 'evidence/014-durable-local-autonomy/mcp-root-followup-20261029/'
    for name in ('actual-mcp-environment.json', 'frozen-swe3-transfer.json'):
        raw = git(repo, 'show', CONTROLLER + ':' + prefix + name)
        historical_evidence.append(write(root, 'model-input/source-evidence/' + name, raw))
    neutral = {
        'schema': 'forge-c/maintenance-replay-evidence/1',
        'origin': 'HISTORICAL_REAL_FAILURE_REPLAY_NOT_A_NEW_OUTAGE',
        'source_order_id': 'afo-774900b297bdde37',
        'source_job_id': 'afo-product-b715f920180f440b708e55a0',
        'source_native_run_id': '01M63ZTJ5QM1R96484Y2KN97H6',
        'source_revision': BASE,
        'phase': 'SWE.3',
        'inspections': ['INS-SWE.3-001', 'INS-SWE.3-002'],
        'observed_finding': 'SWE3-10: PLANTUML_NOT_AVAILABLE for both declared unit diagrams',
        'environment_facts': {'java_installed': True, 'plantuml_jar_installed': True,
                              'isolated_mcp_children_observed': 9, 'children_with_data_root': 0},
        'engineering_obligation': 'Diagnose and repair consistent tool-context resolution in generated isolated MCP '
                                  'and hook execution. Preserve declared overrides and source/policy boundaries.',
        'candidate_file': TARGET,
        'historical_evidence': historical_evidence,
        'instruction_boundary': 'Observed failure data; no reference patch or verifier answers are provided.',
    }
    write(root, 'model-input/incident.json', neutral)
    write(root, 'operator/host-snapshot.json', snapshot)
    write(root, 'operator/prerequisites.json', prerequisites)
    grader_raw = Path(grader).read_bytes()
    write(root, 'verifier/test_tool_context.py', grader_raw)
    controls = {}
    for label, revision in (('baseline', BASE), ('positive-control', CONTROLLER)):
        src = export_source(repo, revision, root / 'operator' / label)
        assert sha((src / TARGET).read_bytes()) == sha(git(repo, 'show', revision + ':' + TARGET))
        temp = root / 'operator' / (label + '-tmp')
        temp.mkdir(mode=0o700)
        env = {'PATH': os.environ.get('PATH', '/usr/bin:/bin'), 'LANG': 'C.UTF-8',
               'PYTHONDONTWRITEBYTECODE': '1', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
               'PYTHONPATH': str(src / 'factory/python'), 'FORGE_REPO_ROOT': str(src),
               'FORGE_STATE_DIR': str(temp / 'state'), 'FORGE_DATA_ROOT': str(temp),
               'TMPDIR': str(temp), 'FORGE_FABRO_LIVE': '0'}
        command = [str(python), '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                   '--rootdir', str(root / 'verifier'), str(root / 'verifier/test_tool_context.py'),
                   '--junitxml=' + str(root / f'operator/{label}.xml')]
        result = subprocess.run(command, cwd=src, env=env, capture_output=True, timeout=90)
        write(root, f'operator/{label}.log', result.stdout + result.stderr)
        import xml.etree.ElementTree as ET

        suite = next(ET.parse(root / f'operator/{label}.xml').getroot().iter('testsuite'))
        expected = '2' if label == 'baseline' else '0'
        if (suite.get('tests') != '2' or suite.get('failures') != expected
                or suite.get('errors') != '0' or suite.get('skipped') != '0'
                or result.returncode != (1 if label == 'baseline' else 0)):
            raise ValueError('CONTROL_RESULT_UNEXPECTED:' + label)
        controls[label] = {'revision': revision, 'command': command, 'exit_code': result.returncode,
                           'tests': dict(suite.attrib), 'target_sha256': sha((src / TARGET).read_bytes())}
    blocks = ['OWNER_STOPPED_EPOCH33', 'NO_CURRENT_FOUR_HOUR_WINDOW_AUTHORIZED',
              'SIGNED_EXACT_ROLE_TRIAL_AND_PRIMARY_SCOPE_NOT_CREATED',
              'GPU_ALLOCATION_AND_NATIVE_MAINTENANCE_ROLE_PREFLIGHT_REQUIRED',
              'ORIGINAL_STOPPED_ORDER_REQUIRES_FACTUAL_SETTLEMENT_BEFORE_SINGLE_SLOT_INTAKE']
    if prerequisites['gpu_query_exit'] == 0:
        free = int(prerequisites['gpu'].split(',')[-1].strip())
        if free < 29 * 1024:
            blocks.append('OBSERVED_GPU_FREE_BELOW_Q8_WEIGHT_FOOTPRINT')
    manifest = {
        'schema': 'forge-c/afo-repair-preparation/1',
        'status': 'PREPARED_CONTROLS_VERIFIED_NOT_ENROLLED_NOT_RUN',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'trial_id': 'F014-AFO-MCP-ROOT-REPAIR-20261029',
        'controller_revision': CONTROLLER, 'repair_baseline_revision': BASE,
        'profile': PROFILE, 'profile_version': profile['version'],
        'profile_sha256': sha(profile_path.read_bytes()), 'model': MODEL,
        'model_identity': profile['models']['allowed'][MODEL],
        'reasoning': 'xhigh', 'mtp_draft': 3, 'inference_slots': 1,
        'role': 'afo-factory-maintainer',
        'role_job_tokens': profile['afo']['role_job_tokens']['afo-factory-maintainer'],
        'requested_window_seconds': 14400, 'approved_new_window': None,
        'existing_deadline_epoch': snapshot['mission']['limits']['deadline'],
        'mission_id': MISSION, 'prior_mission_sha256': sha(json.dumps(snapshot['mission'], sort_keys=True,
                                                                   separators=(',', ':')).encode()),
        'prior_charges_preserved': snapshot['mission']['charged_tokens'],
        'job_limit': 1, 'candidate_limit': 1, 'verification_workers': 1,
        'allowed_patch_paths': [TARGET, 'factory/python/tests/afo_candidate/**'],
        'workflow': ['AFO neutral role-only admission, no product launch', 'existing local_agent durable maintenance',
                     'existing maintainer submission receipt', 'existing VerificationJobs and CAPA/CRE review',
                     'sealed independent tool-context and inherited regression checks'],
        'success_requires': ['real Qwen-created patch and own baseline-failing reproducer',
                             'candidate receipt and independently quiescent inference',
                             'independent frozen checker fails baseline and passes candidate',
                             'existing veto/CAPA/CRE regression and holdout acceptance',
                             'all changes within declared scope; original mission retained'],
        'success_claim': 'INDEPENDENTLY_VERIFIED_FACTORY_REPAIR_CANDIDATE_ONLY',
        'not_proven': ['automatic production deployment', 'original driver recovery', 'M1 acceptance',
                       'general diagnosis qualification', 'learning benefit', '24/7 availability'],
        'model_exposure': ['model-input/incident.json', 'model-input/source-evidence/**',
                           'isolated candidate baseline files via scoped MCP'],
        'withheld': ['verifier/**', 'operator/**', 'positive-control revision and patch'],
        'controls': controls, 'blockers': blocks, 'model_requests': 0, 'orders_created': 0,
        'operator_intent_changed': False, 'deployment_activated': False,
    }
    write(root, 'preparation.json', manifest)
    inventory = {p.relative_to(root).as_posix(): {'sha256': sha(p.read_bytes()), 'bytes': p.stat().st_size}
                 for p in sorted(root.rglob('*')) if p.is_file()}
    write(root, 'inventory.json', inventory)
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', required=True, type=Path)
    p.add_argument('--root', required=True, type=Path)
    p.add_argument('--snapshot', required=True, type=Path)
    p.add_argument('--prerequisites', required=True, type=Path)
    p.add_argument('--grader', required=True, type=Path)
    a = p.parse_args()
    result = prepare(a.repo, a.root, json.loads(a.snapshot.read_text()),
                     json.loads(a.prerequisites.read_text()), a.grader, Path(sys.executable))
    print(json.dumps({k: result[k] for k in ('status', 'trial_id', 'blockers', 'model_requests')}, indent=2))


if __name__ == '__main__':
    main()
