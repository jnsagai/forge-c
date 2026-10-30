"""Final delivery checks for OB-T064; SC-007 is a separate, explicitly NOT_RUN task.

Raw failed checks stay failed. This checks their independent dispositions plus the
executed existing-model quickstart, exact tested source, owner records and draft PR.
"""
import hashlib
import json
import subprocess
from pathlib import Path

from forge_factory.common import REPO_ROOT

ROOT = REPO_ROOT
RUNS = ROOT / 'evidence/v0.4/runs'
HERE = Path(__file__).resolve().parent
SOURCE = '4f4442baadd474617ad5acc07ab34442d6ae605c'
CANDIDATE = '4aac5aca561aa4f1d4603fcaa09760bf05282822'


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def passed(name):
    r = read(RUNS / name / 'latest.json')
    assert r['status'] == 'PASS' and r['exit_code'] == 0, name
    assert digest(ROOT / r['log']) == r['log_sha256'], name + ': log bytes'
    return r


full = read(RUNS / 'OB-FULL-SUITE/latest.json')
assert full['git_head'] == SOURCE and full['git_dirty_at_start'] is False
assert full['status'] == 'FAIL' and full['failed'] == 3  # the raw full suite is never relabeled PASS
assert full['passed'] >= 1452 and full['skipped'] == 27
assert digest(Path(full['junit_external'])) == full['junit_sha256']
assert digest(ROOT / full['log']) == full['log_sha256']
for name in ('OB-NO-REGRESSIONS', 'OB-MODEL-CONTROLS', 'OB-MODEL-DATA-SCRATCH', 'OB-DESIGN', 'OB-STATIC',
             'OB-RECORD-CHECKER', 'OB-SIGNED-DERIVATION', 'OB-QUICKSTART-MODEL-CLI', 'OB-OWNER-REVIEW',
             'OB-SC005-RECHECK', 'OB-PROVENANCE-TRIAGE'):
    passed(name)
subprocess.run(['python', str(RUNS / 'OB-FULL-SUITE/check_results.py'), full['junit_external']], check=True)
subprocess.run(['python', str(HERE / 'check_owner_review.py')], check=True)
subprocess.run(['python', str(HERE / 'ob_check.py'), 'sc005', str(HERE / 'record.json')], check=True)
subprocess.run(['python', str(RUNS / 'OB-FINAL-PROVENANCE/triage.py')], check=True)
raw_provenance = read(RUNS / 'OB-FINAL-PROVENANCE/latest.json')
assert raw_provenance['status'] == 'FAIL' and raw_provenance['exit_code'] == 1
not_run = read(RUNS / 'OB-T043/latest.json')
assert not_run['status'] == 'NOT_RUN' and not_run['model_calls'] == 0
assert not_run['command'] is None and not_run['exit_code'] is None
source = read(HERE / 'model-authoring-r2-source-equivalence.json')
assert source['source_revision'] == SOURCE and source['candidate_revision'] == CANDIDATE
assert git('rev-parse', CANDIDATE + ':evidence') == git('rev-parse', source['baseline_revision'] + ':evidence')
assert all(p.startswith('evidence/') for p in git('diff', '--name-only', SOURCE, CANDIDATE).splitlines())
# After testing, only evidence and task-completion bookkeeping may change.
allowed_tasks = 'specs/016-peripheral-onboarding/tasks.md'
assert all(p.startswith('evidence/') or p == allowed_tasks
           for p in git('diff', '--name-only', SOURCE, 'HEAD').splitlines())
decision = read(ROOT / 'evidence/cre/decisions/pd-35e5ddd7ce46a2941d3c.json')
assert decision['candidate_revision'] == CANDIDATE and decision['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
assert all(g['result'] == 'PASS' or g['name'] == 'reproducer' and
           g['reason_code'] == 'NOT_APPLICABLE_FOR_CHANGE' for g in decision['hard_gates'])
pr = json.loads(subprocess.check_output(['gh', 'api', 'repos/jnsagai/forge-c/pulls/44', '--jq',
                                      '{draft:.draft,base:.base.ref,head:.head.ref,state:.state}'], text=True))
assert pr == {'draft': True, 'base': 'main', 'head': 'feat/016-peripheral-onboarding', 'state': 'open'}
for action, expected in (('is-active', 'inactive'), ('is-enabled', 'disabled')):
    p = subprocess.run(['systemctl', '--user', action, 'forge-llm-gateway-cloud'], capture_output=True, text=True)
    assert p.stdout.strip() == expected
runtime = subprocess.check_output(['systemctl', '--user', 'show', 'forge-conductor',
                                  '--property=WorkingDirectory', '--value'], text=True).strip()
assert Path(runtime).name == 'forge-c-afo-conductor-9dd5b71'
print('PASS OB-T064 delivery: exact source and complete suite, existing-model quickstart, owner bindings and draft PR')
print('Raw suite/provenance/history FAIL evidence retained. SC-007 remains NOT_RUN, not qualified or waived.')
print('No deployment, merge, driver acceptance, finding closure or safety approval is implied.')
