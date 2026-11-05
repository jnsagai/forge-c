"""Append real monitor qualification and sanitized rollout evidence; no private live payloads."""
import hashlib
import json
import shutil
import sqlite3
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

B = Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c')
OPS = B / 'ops/scratch'
WT = B / 'repos/forge-c-014-integration22'
OUT = OPS / 'codex-integration22-exports-v2'
RUN = OUT / 'evidence/v0.4/runs/CODEX-INTEGRATION22-20261105'
CRE = OUT / 'evidence/cre'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as output:
        json.dump(value, output, indent=2)


def copy(source, target):
    assert not target.exists()
    assert b'-----BEGIN OPENSSH PRIVATE KEY-----' not in source.read_bytes().splitlines()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    assert sha(source) == sha(target)


assert not OUT.exists()
assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=WT, text=True).strip() == '1247d26793b27cf7d4f71385925e3cc191c2d22b'
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=WT)
assert subprocess.check_output(['git', 'diff', '--name-only', '7f55de5c', 'HEAD'], cwd=WT, text=True).splitlines() == [
    'factory/python/forge_factory/dashboard/static/factory-floor.html']
connection = sqlite3.connect(f'file:{B}/state/supervisor/incidents.sqlite3?mode=ro', uri=True)
connection.row_factory = sqlite3.Row
results = []
for label, name, count in (('monitor', 'plant-floor-monitor-qualified-index.json', 49),
                           ('caption', 'floor-last-reported-qualified-index.json', 31)):
    index_path = OPS / name
    index = json.loads(index_path.read_text())
    root = Path(index['exports'])
    decision_id = index['decision_id']
    decision = json.loads((root / 'evidence/cre/decisions' / (decision_id + '.json')).read_text())
    assert decision['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
    assert all(g['result'] == 'PASS' or g['name'] == 'reproducer' and g['result'] == 'NOT_RUN'
               and g['reason_code'] == 'NOT_APPLICABLE_FOR_CHANGE' for g in decision['hard_gates'])
    assert len(next(g['evidence_refs'] for g in decision['hard_gates'] if g['name'] == 'prevention')) == 175
    db = dict(connection.execute('SELECT * FROM cre_promotion_decisions WHERE decision_id=?', (decision_id,)).fetchone())
    assert db['candidate'] == index['candidate'] and db['baseline'] == index['baseline']
    assert json.loads(db['record']) == {k: v for k, v in decision.items() if k not in ('candidate_revision', 'baseline_revision')}
    tests = 0
    for row in index['files']:
        source = root / row['path']
        assert sha(source) == row['sha256']
        path = row['path']
        if path.startswith('evidence/'):
            target = OUT / path
        elif path.startswith('prevention/'):
            target = CRE / 'reproducers' / source.name
        elif path == 'decision-db-row.json':
            target = CRE / 'decisions' / (decision_id + '-db-row.json')
        else:
            target = RUN / label / path
        copy(source, target)
        if source.suffix == '.xml':
            unit = ET.parse(source).getroot()
            assert not list(unit.iter('failure')) + list(unit.iter('error')) + list(unit.iter('skipped'))
            tests += len(list(unit.iter('testcase')))
    assert tests == count, (label, tests)
    for gate in decision['hard_gates']:
        for ref in gate['evidence_refs']:
            kind, _, rid = ref.partition(':')
            if kind == 'benchmark-run':
                row = dict(connection.execute('SELECT * FROM cre_benchmark_runs WHERE run_id=?', (rid,)).fetchone())
                target = CRE / 'benchmarks' / (rid + '.json')
                if not target.exists():
                    write(target, row)
    copy(index_path, RUN / label / 'component-qualified-index.json')
    results.append(dict(component=label, candidate=index['candidate'], baseline=index['baseline'],
                        decision_id=decision_id, tests=tests, prevention=175, causal='NOT_RUN_CHANGE'))
for label, name in (('initial-monitor', 'plant-floor-monitor-deployed-index.json'),
                    ('final-caption', 'floor-last-reported-deployed-index.json')):
    index = json.loads((OPS / name).read_text())
    expected_status = 'DEPLOYED_READ_ONLY_MONITOR_VERIFIED' if label == 'initial-monitor' else 'DEPLOYED_VERIFIED'
    invariant_key = 'service_and_state_invariants' if label == 'initial-monitor' else 'invariants'
    assert index['status'] == expected_status and index['browser']['result'] == 'PASS'
    assert index[invariant_key]['checks'] and all(index[invariant_key]['checks'].values())
    assert index[invariant_key]['native']['count'] == 149 and index[invariant_key]['native']['nonterminal'] == 0
    # Publish the reviewed status/invariant summary, not the full live API, service credentials or screenshots.
    write(RUN / 'deployment' / (label + '.json'), {k: v for k, v in index.items() if k != 'files'})
copy(OPS / 'codex-integration22-inputs-before-tests.json', RUN / 'inputs-before-tests.json')
copy(Path(__file__), RUN / Path(__file__).name)
copy(OPS / 'package-plant-floor-integration22.py', RUN / 'package-plant-floor-integration22.py')
copy(OPS / 'plant-floor-packaging-error.json', RUN / 'packaging-error.json')
validation = dict(schema='forge-c/integration22-validation/1', status='READ_ONLY_MONITOR_DEPLOYED_BROWSER_VERIFIED',
    source='1247d26793b27cf7d4f71385925e3cc191c2d22b', prior='d5024d62842b276c4a81fd51ed399704c7fc43cb',
    components=results, functional_source_python_byte_identical_between_components=True,
    test_denominator='49 main monitor cases and31 frontend/API follow-up cases overlap; do not sum as80 distinct cases.',
    actual_browser_verified=True, actual_monitor_url='http://localhost:8788/?line=local',
    actual_conductor_requested='OBSERVE', actual_conductor_observed='OBSERVE', actual_intent='RUNNING', intent_epoch=1,
    actual_driver_activity='NO_CURRENT_DRIVER_OBSERVED', actual_throughput='UNKNOWN_NOT_ZERO',
    actual_loaded_model='NOT_PROVIDER_VERIFIED_LAST_REPORTED_ONLY',
    role_qualification='NOT_RUN', native_factory_ACT=False, actual_mission_amendment=False, new_model_calls=0,
    no_conductor_or_native_or_mission_or_history_changes=True, source_stage_scope='Two read-only floor units only',
    new_task_checkboxes=0, limitations=['The monitor observes runtime, not product acceptance or native role competence.',
        'The controller remains OBSERVE. No model job or autonomy trial was started by the monitor rollout.',
        'Historical job outcomes, native liveness/leases and operations intent remain separate.',
        'Owner requested no new signatures for now; signature-free supervised development requires its own bounded, qualified accounting/authority implementation. No production signature guard was relaxed.',
        'No main merge, safety signoff or production release.'])
write(RUN / 'validation.json', validation)
files = [dict(path=str(p.relative_to(OUT)), sha256=sha(p), bytes=p.stat().st_size)
         for p in sorted(OUT.rglob('*')) if p.is_file()]
index = OPS / 'codex-integration22-qualified-index.json'
write(index, dict(source=validation['source'], prior=validation['prior'], exports=str(OUT),
                  status=validation['status'], decisions=[r['decision_id'] for r in results], files=files))
print(json.dumps(dict(files=len(files), index_sha256=sha(index), actual_status=validation['status'])))
