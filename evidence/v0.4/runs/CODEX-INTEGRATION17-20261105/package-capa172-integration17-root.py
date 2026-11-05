"""Seal qualified source/run/controller evidence; excludes owner grants and OS approvals."""
import hashlib
import json
import shutil
from pathlib import Path

from forge_factory.reliability.capa import CapaRegistry
from forge_factory.reliability.policy import load
from forge_factory.reliability.store import CREStore

B = Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c')
OPS = B / 'ops/scratch'
OUT = OPS / 'codex-integration17-exports'
RUN = OUT / 'evidence/v0.4/runs/CODEX-INTEGRATION17-20261105'
CRE = OUT / 'evidence/cre'
C = '84a35ccb3533488be2ec81a40c6b375c72dccf4d'
BASE = '2035280de096a6f1107aa052db196c0a6c091ffc'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
path_mapping = []

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')

def copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        assert sha(source) == sha(destination)
        return
    shutil.copy2(source, destination)
    assert sha(source) == sha(destination)

def copy_ref(ref):
    source = Path(ref['path'])
    assert source.is_file() and sha(source) == ref['sha256']
    copy(source, RUN / 'component' / source.name)
    path_mapping.append({'original_path': str(source), 'path': 'component/' + source.name,
                         'sha256': ref['sha256']})

assert not OUT.exists(), 'PRESERVE_EXISTING_EXPORT'
decisions = {}
prevention = {}
records = {}
benchmarks = {}
store = CREStore()
specs = [('source', 'capa172-fix-decision-root.json', C, BASE),
         ('native', 'local-gen35-change-decision.json', '38acc88c549e3713665542474385999822cdd3d4', C),
         ('controller', 'local-gen35-controller-change-decision.json', '62fce0a4b2dbcae8dbcd7e5f5952d5ee8acb7fa9', C)]
with store.conn() as conn:
    for label, name, candidate, baseline in specs:
        d = json.loads((OPS / name).read_text())
        assert d['candidate_revision'] == candidate and d['baseline_revision'] == baseline
        assert d['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
        assert all(g['result'] == 'PASS' or label != 'source' and g['name'] == 'reproducer'
                   and g['result'] == 'NOT_RUN' and g['reason_code'] == 'NOT_APPLICABLE_FOR_CHANGE'
                   for g in d['hard_gates'])
        db = dict(conn.execute('SELECT * FROM cre_promotion_decisions WHERE decision_id=?', (d['decision_id'],)).fetchone())
        assert json.loads(db['record']) == {k: v for k, v in d.items() if k not in ('candidate_revision', 'baseline_revision')}
        assert db['candidate'] == candidate and db['baseline'] == baseline
        pre = next(g['evidence_refs'] for g in d['hard_gates'] if g['name'] == 'prevention')
        assert len(pre) == 171
        for gate in d['hard_gates']:
            for ref in gate['evidence_refs']:
                kind, _, rid = ref.partition(':')
                if kind == 'reproducer-run':
                    row = dict(conn.execute('SELECT * FROM cre_reproducer_runs WHERE run_id=?', (rid,)).fetchone())
                    records[rid] = row
                    if ref in pre:
                        assert row['revision'] == candidate and row['verdict'] == 'SYMPTOM_ABSENT'
                elif kind == 'benchmark-run':
                    benchmarks[rid] = dict(conn.execute('SELECT * FROM cre_benchmark_runs WHERE run_id=?', (rid,)).fetchone())
        decisions[label] = d
        prevention[label] = pre
        write(CRE / 'decisions' / (d['decision_id'] + '.json'), d)
        write(CRE / 'decisions' / (d['decision_id'] + '-db-row.json'), db)
    # Registry causal verification preceded promotion's own independent causal pair.
    for row in conn.execute("SELECT * FROM cre_reproducer_runs WHERE reproducer_id='RPR-172'"):
        value = dict(row)
        if value['revision'] in (BASE, C):
            records[value['run_id']] = value
for rid, row in records.items():
    log = B / 'state/reliability/reproducers' / (rid + '.log')
    assert sha(log) == row['log_sha256']
    copy(log, CRE / 'reproducers' / log.name)
    write(CRE / 'reproducers' / (rid + '.json'), row)
for rid, row in benchmarks.items():
    assert json.loads(row['record'])['run_id'] == rid
    write(CRE / 'benchmarks' / (rid + '.json'), row)
registry = CapaRegistry(store, load())
source_pre = [records[r.split(':', 1)[1]] for r in prevention['source']]
if registry.must('CAPA-172')['state'] == 'FIX_CANDIDATE':
    registry.register_prevention('CAPA-172', next(r for r in source_pre if r['reproducer_id'] == 'RPR-172'))
registry.link('CAPA-172', 'PROMOTION_DECISION', decisions['source']['decision_id'])
write(CRE / 'capa/capa-172.json', registry.must('CAPA-172'))
write(CRE / 'capa/capa-172-history.json', registry.history('CAPA-172'))
write(CRE / 'capa/capa-172-links.json', registry.links('CAPA-172'))
caller = B / 'repos/forge-c-014-capa172-oracle/tests/reliability/reproducers'
assert sha(caller / 'manifest.yaml') == 'a38af4f2cc017b35ac6303e20dbb763ad2e3a6f3a78eda027e3508f625e92da6'
copy(caller / 'rpr172_mission_deadline_continuation.py', OUT / 'tests/reliability/reproducers/rpr172_mission_deadline_continuation.py')
copy(caller / 'manifest.yaml', RUN / 'frozen-manifest.yaml')

names = ['codex-integration17-independent.xml', 'codex-integration17-independent.log',
         'codex-integration17-independent-validation.json', 'codex-integration17-source-prepared.json',
         'codex-integration17-before-tests-inputs.json', 'codex-integration17-design.log', 'codex-integration17-ruff.log',
         'capa172-root-oracle-freeze.json', 'capa172-oracle-before-tests-inputs.json',
         'capa172-causal-and-fix-root.py', 'capa172-causal-and-fix-root.log',
         'local-gen35-change-root.py', 'local-gen35-change-root.log',
         'local-gen35-controller-change-root.py', 'local-gen35-controller-change-root.log',
         'local-gen35-prepared.json', 'local-gen35-prepared-index.json', 'local-gen35-prepared-inputs.json',
         'local-gen35-plan-inputs-cpu.json', 'local-gen35-input-integrity.xml', 'local-gen35-input-integrity.log',
         'local-gen35-design.log', 'local-gen35-source.bundle', 'local-gen35-controller-prepared-index.json',
         'local-gen35-controller-before-tests-inputs.json', 'local-gen35-controller-payload-validation.json',
         'local-gen35-controller-design.log', 'local-gen35-controller-source.bundle',
         'capa172-joint-component-index.json', 'capa172-m9-component-index.json',
         'package-capa172-integration17-root.py']
for name in names:
    copy(OPS / name, RUN / name)
component = json.loads((OPS / 'capa172-joint-component-index.json').read_text())
for ref in component['evidence']:
    copy_ref(ref)
child = json.loads((OPS / 'capa172-m9-component-index.json').read_text())
copy_ref(child['source']['bundle'])
for test in child['validation']['tests']:
    copy_ref(test['xml'])
    copy_ref(test['log'])
for key in ('design14', 'ruff3', 'all8_and_explicit10_before_tests'):
    copy_ref(child['validation'][key])
write(RUN / 'component/artifact-path-map.json', path_mapping)
for name in ('source172-review-index.json', 'source172-review.json'):
    source = OPS / 'mission-renewal-audit-20261105' / name
    if source.exists():
        copy(source, RUN / 'independent-review' / name)
validation = json.loads((OPS / 'codex-integration17-independent-validation.json').read_text())
validation.update({'status': 'ELIGIBLE_FOR_OFFLINE_REVIEW_ONLY', 'decisions': {k: d['decision_id'] for k, d in decisions.items()},
                   'prevention_per_candidate': 171, 'all_raw_reproducer_logs_hash_verified': True,
                   'causal_baseline': 'SYMPTOM_PRESENT', 'causal_candidate': 'SYMPTOM_ABSENT',
                   'native_candidate': specs[1][2], 'controller_candidate': specs[2][2],
                   'model_calls': 0, 'actual_mission_extension': False, 'actual_trial_activation': False,
                   'limits': ['Current human signatures and credible host UTC are independently required for live work.',
                              'Normal runtime policy keeps its 86400-second order wall; operator-only extension policy requires its own signature.',
                              'Role competence, repair/learning benefit and real 24/72/168-hour endurance are not established.',
                              'No main merge, safety approval, certification or production release.']})
write(RUN / 'validation.json', validation)
write(CRE / 'receipts/CODEX-INTEGRATION17-20261105.json', {
    'source': C, 'baseline': BASE, 'decisions': validation['decisions'], 'prevention_refs': prevention,
    'raw_reproducer_records': len(records), 'benchmark_records': len(benchmarks), 'no_deployment': True})
files = [{'path': str(f.relative_to(OUT)), 'sha256': sha(f), 'bytes': f.stat().st_size}
         for f in sorted(OUT.rglob('*')) if f.is_file()]
write(OPS / 'codex-integration17-qualified-index.json', {
    'source': C, 'baseline': BASE, 'status': validation['status'], 'exports': str(OUT),
    'decisions': validation['decisions'], 'files': files})
print(json.dumps({'files': len(files), 'raw_records': len(records), 'benchmark_records': len(benchmarks),
                  'index_sha256': sha(OPS / 'codex-integration17-qualified-index.json')}))
