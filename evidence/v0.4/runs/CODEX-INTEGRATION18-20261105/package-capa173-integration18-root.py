"""Export genuine source qualification and preserved failures; no owner material or activation."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

from forge_factory.reliability.capa import CapaRegistry
from forge_factory.reliability.policy import load
from forge_factory.reliability.store import CREStore

B = Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c')
OPS = B / 'ops/scratch'
OUT = OPS / 'codex-integration18-exports'
RUN = OUT / 'evidence/v0.4/runs/CODEX-INTEGRATION18-20261105'
CRE = OUT / 'evidence/cre'
WT = B / 'repos/forge-c-014-integration18'
C = '63a3a91d10932d8693b2f144b5d425424e0311a3'
BASE = 'afa651a717f391f4c1e689516c626141d0f205b1'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')

def copy(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    assert not dst.exists()
    shutil.copy2(src, dst)
    assert sha(src) == sha(dst)

assert not OUT.exists()
decision = json.loads((OPS / 'capa173-fix-decision-root.json').read_text())
assert decision['candidate_revision'] == C and decision['baseline_revision'] == BASE
assert decision['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
assert all(g['result'] == 'PASS' for g in decision['hard_gates'])
prevention = next(g['evidence_refs'] for g in decision['hard_gates'] if g['name'] == 'prevention')
assert len(prevention) == 172
suite = ET.parse(OPS / 'codex-integration18-offline.xml').getroot()
cases = list(suite.iter('testcase'))
assert len(cases) == 25 and not any(list(c) for c in cases)
assert 'PASS: 14 static design tests' in (OPS / 'codex-integration18-design.log').read_text()
assert (OPS / 'codex-integration18-ruff.log').read_text().strip() == 'All checks passed!'
for rel in ('factory/python/forge_factory/offline/patch.py', 'factory/python/tests/test_da014_offline_patch.py'):
    assert subprocess.check_output(['git', 'show', f'{C}:{rel}'], cwd=WT) == (WT / rel).read_bytes()
old_manifest = subprocess.check_output(['git', 'show', f'{BASE}:tests/reliability/reproducers/manifest.yaml'], cwd=WT)
assert (WT / 'tests/reliability/reproducers/manifest.yaml').read_bytes().startswith(old_manifest)
store = CREStore()
records, benchmarks = {}, {}
with store.conn() as conn:
    db = dict(conn.execute('SELECT * FROM cre_promotion_decisions WHERE decision_id=?', (decision['decision_id'],)).fetchone())
    assert json.loads(db['record']) == {k: v for k, v in decision.items() if k not in ('candidate_revision', 'baseline_revision')}
    assert db['candidate'] == C and db['baseline'] == BASE
    for row in conn.execute("SELECT * FROM cre_reproducer_runs WHERE reproducer_id='RPR-173'"):
        row = dict(row)
        if row['revision'] in (C, BASE):
            records[row['run_id']] = row
    for gate in decision['hard_gates']:
        for ref in gate['evidence_refs']:
            kind, _, rid = ref.partition(':')
            if kind == 'reproducer-run':
                records[rid] = dict(conn.execute('SELECT * FROM cre_reproducer_runs WHERE run_id=?', (rid,)).fetchone())
            elif kind == 'benchmark-run':
                benchmarks[rid] = dict(conn.execute('SELECT * FROM cre_benchmark_runs WHERE run_id=?', (rid,)).fetchone())
for ref in prevention:
    row = records[ref.partition(':')[2]]
    assert row['revision'] == C and row['verdict'] == 'SYMPTOM_ABSENT'
for rid, row in records.items():
    log = B / 'state/reliability/reproducers' / (rid + '.log')
    assert sha(log) == row['log_sha256']
    copy(log, CRE / 'reproducers' / log.name)
    write(CRE / 'reproducers' / (rid + '.json'), row)
for rid, row in benchmarks.items():
    write(CRE / 'benchmarks' / (rid + '.json'), row)
write(CRE / 'decisions' / (decision['decision_id'] + '.json'), decision)
write(CRE / 'decisions' / (decision['decision_id'] + '-db-row.json'), db)
registry = CapaRegistry(store, load())
assert registry.must('CAPA-173')['state'] == 'EFFECTIVENESS_OBSERVING'
write(CRE / 'capa/capa-173.json', registry.must('CAPA-173'))
write(CRE / 'capa/capa-173-history.json', registry.history('CAPA-173'))
write(CRE / 'capa/capa-173-links.json', registry.links('CAPA-173'))
for name in ('014-goal-audit-inputs-before-tests-20261105.json', 'da058-oracle-inputs-before-tests.json',
             'da058-oracle-v2-inputs-before-tests.json', 'capa173-crewtrees-inputs-before-tests.json',
             'capa173-v2-crewtrees-inputs-before-tests.json', 'codex-integration18-inputs-before-tests.json',
             'da058-whole-release-red.xml', 'da058-whole-release-red.log',
             'da058-whole-release-green-v1.xml', 'da058-whole-release-green-v1.log',
             'da058-whole-release-green-v2.xml', 'da058-whole-release-green-v2.log',
             'da058-whole-release-green-v3.xml', 'da058-whole-release-green-v3.log',
             'codex-integration18-offline.xml', 'codex-integration18-offline.log',
             'codex-integration18-design.log', 'codex-integration18-ruff.log',
             'capa173-causal-and-fix-root.py', 'capa173-causal-and-fix-root.log',
             'capa173-causal-and-fix-root-v2.py', 'capa173-causal-and-fix-root-v2.log',
             'package-capa173-integration18-root.py'):
    source = OPS / name
    if source.is_file():
        copy(source, RUN / name)
copy(WT / 'tests/reliability/reproducers/manifest.yaml', RUN / 'frozen-manifest.yaml')
validation = dict(schema='forge-c/integration18-validation/1', candidate=C, baseline=BASE,
    status='ELIGIBLE_FOR_OFFLINE_REVIEW_ONLY', decision_id=decision['decision_id'], passed=25, failures=0,
    errors=0, skipped=0, design_checks=14, ruff_python_files=2, prevention_passed=172,
    causal_baseline='SYMPTOM_PRESENT', causal_candidate='SYMPTOM_ABSENT',
    original_oracle_version_preserved=True, private_nss_fixture_only=True,
    original_oracle_errors_preserved=['rr-6274a0a846ad9ce772d7', 'rr-c12db63f40628e659343'],
    test_collection_typo_preserved='green-v2 exit4: nonexistent filename; corrected v3 passes unchanged tests',
    release_layout='CLEAN_CODE_ONLY_ARCHIVE_WITH_EXTERNAL_STATE_AND_DEPENDENCIES',
    full_offline_round_trip='NOT_RUN', markdown_report='NOT_IMPLEMENTED', transfer_runner='NOT_IMPLEMENTED',
    live_patch_import=False, model_calls=0, mission_amendment=False, grant_changes=False,
    limitations=['Exact tree identity excludes untracked dependency/input/cache files. Regression scopes needing ignored owner inputs require external-input routing.',
        'No actual offline factory run, native model competence or endurance acceptance is established.',
        'Current local GEN35 signatures and packet are unchanged; live activation remains held on credible host UTC.',
        'No main merge, automatic source promotion, safety approval or production release.'])
write(RUN / 'validation.json', validation)
files = [dict(path=str(f.relative_to(OUT)), sha256=sha(f), bytes=f.stat().st_size)
         for f in sorted(OUT.rglob('*')) if f.is_file()]
write(OPS / 'codex-integration18-qualified-index.json', dict(source=C, baseline=BASE, decision_id=decision['decision_id'],
    status=validation['status'], exports=str(OUT), files=files))
print(json.dumps(dict(files=len(files), raw_records=len(records), decision_id=decision['decision_id'],
    index_sha256=sha(OPS / 'codex-integration18-qualified-index.json'))))
