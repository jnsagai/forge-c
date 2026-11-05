"""Seal actual qualification records; never manufacture native task completion."""
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from forge_factory.reliability.capa import CapaRegistry
from forge_factory.reliability.policy import load
from forge_factory.reliability.store import CREStore

B = Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c')
OPS = B / 'ops/scratch'
WT = B / 'repos/forge-c-014-integration21'
OUT = OPS / 'codex-integration21-exports-v2'
RUN = OUT / 'evidence/v0.4/runs/CODEX-INTEGRATION21-20261105'
CRE = OUT / 'evidence/cre'
BASE = '3e8936a27f847b32bb76eef4a24bc83cc2daad20'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)


def copy(src, dst):
    assert not dst.exists()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    assert sha(src) == sha(dst)
    assert b'-----BEGIN OPENSSH PRIVATE KEY-----' not in dst.read_bytes().splitlines()


assert not OUT.exists()
d = json.loads((OPS / 'capa176-fix-decision-root.json').read_text())
source = d['candidate_revision']
assert d['baseline_revision'] == BASE and d['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
assert all(g['result'] == 'PASS' for g in d['hard_gates'])
prevention = next(g['evidence_refs'] for g in d['hard_gates'] if g['name'] == 'prevention')
assert len(prevention) == 175
tests = []
for name in ('diagnosis-dependencies-combined-v2', 'diagnosis-dependencies-adjacent-v1'):
    unit = ET.parse(OPS / (name + '.xml')).getroot()
    cases = list(unit.iter('testcase'))
    assert cases and not list(unit.iter('failure')) + list(unit.iter('error'))
    tests.append(dict(name=name, tests=len(cases), skipped=len(list(unit.iter('skipped')))))
assert 'PASS: 14 static design tests' in (OPS / 'diagnosis-dependencies-design-final.log').read_text()
assert (OPS / 'diagnosis-dependencies-ruff-v2.log').read_text().strip() == 'All checks passed!'
old = subprocess.check_output(['git', 'show', BASE + ':tests/reliability/reproducers/manifest.yaml'], cwd=WT)
assert (WT / 'tests/reliability/reproducers/manifest.yaml').read_bytes().startswith(old)
changed = subprocess.check_output(['git', 'diff', '--name-only', source, 'HEAD'], cwd=WT, text=True).splitlines()
assert set(changed) == {'tests/reliability/reproducers/manifest.yaml',
                        'tests/reliability/reproducers/rpr176_dependent_objective_first.py',
                        'tests/reliability/reproducers/rpr176v2_dependent_objective_first.py'}
s = CREStore()
with s.conn() as connection:
    db = dict(connection.execute('SELECT * FROM cre_promotion_decisions WHERE decision_id=?',
                                 (d['decision_id'],)).fetchone())
    assert db['candidate'] == source and db['baseline'] == BASE
    assert json.loads(db['record']) == {k: v for k, v in d.items() if k not in ('candidate_revision', 'baseline_revision')}
    write(CRE / 'decisions' / (d['decision_id'] + '.json'), d)
    write(CRE / 'decisions' / (d['decision_id'] + '-db-row.json'), db)
    records, benchmarks = {}, {}
    for gate in d['hard_gates']:
        for ref in gate['evidence_refs']:
            kind, _, rid = ref.partition(':')
            if kind == 'reproducer-run':
                records[rid] = dict(connection.execute('SELECT * FROM cre_reproducer_runs WHERE run_id=?', (rid,)).fetchone())
            elif kind == 'benchmark-run':
                benchmarks[rid] = dict(connection.execute('SELECT * FROM cre_benchmark_runs WHERE run_id=?', (rid,)).fetchone())
    for row in connection.execute("SELECT * FROM cre_reproducer_runs WHERE reproducer_id='RPR-176'"):
        records[row['run_id']] = dict(row)
for rid, row in records.items():
    log = B / 'state/reliability/reproducers' / (rid + '.log')
    assert sha(log) == row['log_sha256']
    copy(log, CRE / 'reproducers' / log.name)
    write(CRE / 'reproducers' / (rid + '.json'), row)
for rid, row in benchmarks.items():
    write(CRE / 'benchmarks' / (rid + '.json'), row)
r = CapaRegistry(s, load())
write(CRE / 'capa/CAPA-176.json', r.must('CAPA-176'))
write(CRE / 'capa/CAPA-176-history.json', r.history('CAPA-176'))
write(CRE / 'capa/CAPA-176-links.json', r.links('CAPA-176'))
for pattern in ('diagnosis-dependencies-*.json', 'diagnosis-dependencies-*.xml', 'diagnosis-dependencies-*.log',
                'diagnosis-dependencies-collected.txt', 'capa176-*.json', 'capa176-*.py', 'capa176-*.log',
                'package-diagnosis-dependencies-integration21*.py', 'codex-integration21-inputs-before-tests.json'):
    for path in sorted(OPS.glob(pattern)):
        if not (RUN / path.name).exists():
            copy(path, RUN / path.name)
copy(WT / 'tests/reliability/reproducers/manifest.yaml', RUN / 'frozen-manifest.yaml')
validation = dict(schema='forge-c/integration21-validation/1', source=source, baseline=BASE,
    status='ELIGIBLE_FOR_OFFLINE_REVIEW_ONLY', decision_id=d['decision_id'], all7_hard_gates_pass=True,
    tests=tests, passed=sum(t['tests'] - t['skipped'] for t in tests),
    failures=0, errors=0, skipped=sum(t['skipped'] for t in tests), design_checks=14, ruff_python_files=6,
    frozen_prevention=175, original_manifest_prefix_unchanged=True, source_equivalence_checked=True,
    causal_baseline='SYMPTOM_PRESENT', causal_candidate='SYMPTOM_ABSENT',
    actual_prepare_request_and_pending_broker_controls=True, original_allowance_and_duplicate_reservation_preserved=True,
    fixture_correction='Signed reservation controls now include their declared blocked gate rather than an empty diagnosis inventory. Negative grant/expiry/reservation controls remain; empty request/prepare refusal is tested separately.',
    original_failures_preserved=True, original_witness_v1_format_ERROR_preserved=True, packaging_v1_marker_literal_false_positive_preserved=True, native_DA_AT_032='NOT_RUN', new_task_checkboxes=0,
    mission_amendment=False, model_calls=0, live_source_activation=False,
    limitations=['No model competence, native sequential task execution, global integration-fault campaign or larger-task comparison established.',
                 'Independent re-verification and new sealed packets must remove resolved dependencies. Planning or model claims do not complete prerequisites.',
                 'Existing approved receipt history and mission history are not rewritten.',
                 'GEN35 authority/source/runbooks remain unchanged; native campaign adoption requires its applicable reviewed binding.',
                 'No main merge, safety signoff, certification or production release.'])
write(RUN / 'validation.json', validation)
files = [dict(path=str(p.relative_to(OUT)), sha256=sha(p), bytes=p.stat().st_size)
         for p in sorted(OUT.rglob('*')) if p.is_file()]
index = OPS / 'codex-integration21-qualified-index.json'
write(index, dict(source=source, baseline=BASE, exports=str(OUT), decision_id=d['decision_id'],
                  status=validation['status'], files=files))
print(json.dumps(dict(files=len(files), raw_records=len(records), index_sha256=sha(index),
                      tests=tests)))
