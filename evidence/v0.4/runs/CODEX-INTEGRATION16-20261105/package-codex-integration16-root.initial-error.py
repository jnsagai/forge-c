"""Seal verified I16 source qualification evidence without changing prior archives."""
import hashlib
import json
import shutil
from pathlib import Path

from forge_factory.reliability.store import CREStore

B = Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c')
OPS = B / 'ops/scratch'
OUT = OPS / 'codex-integration16-exports'
RUN = OUT / 'evidence/v0.4/runs/CODEX-INTEGRATION16-20261105'
CRE = OUT / 'evidence/cre'
C = 'a856b521fccab43309ee4bfe1cded42c2eb37938'
BASE = 'c121ea79813bcd06f51b2468a067e7584ef15cdf'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')

def copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    assert not destination.exists()
    shutil.copy2(source, destination)
    assert sha(source) == sha(destination)

assert not OUT.exists()
d = json.loads((OPS / 'codex-integration16-change-decision.json').read_text())
assert d['candidate_revision'] == C and d['baseline_revision'] == BASE
assert d['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
assert all(g['result'] == 'PASS' or g['name'] == 'reproducer' and g['result'] == 'NOT_RUN'
           and g['reason_code'] == 'NOT_APPLICABLE_FOR_CHANGE' for g in d['hard_gates'])
refs = next(g['evidence_refs'] for g in d['hard_gates'] if g['name'] == 'prevention')
assert len(refs) == 170
records = []
store = CREStore()
with store.conn() as conn:
    db_decision = dict(conn.execute('SELECT * FROM cre_promotion_decisions WHERE decision_id=?', (d['decision_id'],)).fetchone())
    assert json.loads(db_decision['record']) == d
    for ref in refs:
        rid = ref.split(':', 1)[1]
        row = dict(conn.execute('SELECT * FROM cre_reproducer_runs WHERE run_id=?', (rid,)).fetchone())
        assert row['revision'] == C and row['verdict'] == 'SYMPTOM_ABSENT'
        log = B / 'state/reliability/reproducers' / (rid + '.log')
        assert sha(log) == row['log_sha256']
        copy(log, CRE / 'reproducers' / log.name)
        write(CRE / 'reproducers' / (rid + '.json'), row)
        records.append(row)
write(CRE / 'decisions' / (d['decision_id'] + '.json'), d)
write(CRE / 'decisions' / (d['decision_id'] + '-db-row.json'), db_decision)

for name in ('codex-integration16-independent.xml', 'codex-integration16-independent.log',
             'codex-integration16-design.log', 'codex-integration16-ruff.log',
             'codex-integration16-independent-validation.json', 'codex-integration16-source-prepared.json',
             'codex-integration16-before-any-tests-inputs.json', 'codex-integration16-change-root.py',
             'codex-integration16-change-root.log', 'line-soak-oracle-preparation.json',
             'line-soak-oracle-ten-dependencies.json'):
    copy(OPS / name, RUN / name)

component = json.loads((OPS / 'line-soak-prerequisite-candidate-index.json').read_text())
assert sha(OPS / 'line-soak-prerequisite-candidate-index.json') == '3183ce5d5950f32abd7e895cbb9ab896b9c950bfff96764b4126dd8faea6f441'
copy(OPS / 'line-soak-prerequisite-candidate-index.json', RUN / 'component/original-candidate-index.json')
mapping = []
def copy_ref(ref):
    source = Path(ref['path'])
    assert sha(source) == ref['sha256'] and source.stat().st_size == ref['bytes']
    relative = 'component/' + source.name
    destination = RUN / relative
    if not destination.exists():
        copy(source, destination)
    else:
        assert sha(destination) == ref['sha256']
    mapping.append({'original_path': str(source), 'path': relative, 'sha256': ref['sha256']})

for run in component['validation']['test_runs']:
    copy_ref(run['xml'])
    copy_ref(run['log'])
for key in ('design14_log', 'ruff15_python_files_log', 'input_final_recheck',
            'original_before_tests_receipt', 'explicit10_dependency_recheck', 'normal_queue_extraction_static_review'):
    copy_ref(component['validation'][key])
copy_ref(component['source']['bundle'])
write(RUN / 'component/artifact-path-map.json', mapping)
write(CRE / 'receipts' / 'CODEX-INTEGRATION16-20261105.json', {
    'candidate': C, 'baseline': BASE, 'decision_id': d['decision_id'],
    'frozen_manifest_sha256': 'e12fd44033ec0d945ea900bfa6d5e57a8edc5c3c5837263d49534da71bee820d',
    'prevention_receipts_in_order': records, 'all_log_hashes_verified': True,
    'causal_reproducer': 'NOT_RUN_CHANGE', 'allowed_auto_deployment': False})
validation = json.loads((OPS / 'codex-integration16-independent-validation.json').read_text())
validation.update({'status': 'ELIGIBLE_SOURCE_FOR_OFFLINE_REVIEW_ONLY', 'decision_id': d['decision_id'],
                   'hard_gates': {g['name']: g['result'] for g in d['hard_gates']},
                   'prevention_receipts': 170, 'actual_model_calls': 0, 'actual_soak_starts': 0,
                   'M9_live_acceptance_complete': False,
                   'limits': ['The optional historical M3 replay is NOT_RUN; original snapshot was not provided.',
                              'Finite qualification experiments are not role competence or deployment permission.',
                              'Actual job/fault authority, host readiness and role evidence remain live admission prerequisites.',
                              'Real 24/72/168-hour duration, 16 fault/continuity categories, actual work and later intake remain NOT_RUN.',
                              'Generic paths and legacy observations retain their behavior; planned unsubmitted intake supports independent first SWE.1 START only.',
                              'No main merge, certification, safety approval or production release.']})
write(RUN / 'validation.json', validation)
files = [{'path': str(p.relative_to(OUT)), 'sha256': sha(p), 'bytes': p.stat().st_size}
         for p in sorted(OUT.rglob('*')) if p.is_file()]
write(RUN / 'protected-files-index.json', {'source': C, 'baseline': BASE, 'decision_id': d['decision_id'], 'files': files})
write(OPS / 'codex-integration16-qualified-index.json', {
    'source': C, 'baseline': BASE, 'decision_id': d['decision_id'], 'status': validation['status'],
    'exports': str(OUT), 'files': [*files, {'path': str((RUN / 'protected-files-index.json').relative_to(OUT)),
                                         'sha256': sha(RUN / 'protected-files-index.json'),
                                         'bytes': (RUN / 'protected-files-index.json').stat().st_size}]})
print(json.dumps({'source': C, 'decision_id': d['decision_id'], 'files': len(files) + 1, 'prevention': len(records)}))
