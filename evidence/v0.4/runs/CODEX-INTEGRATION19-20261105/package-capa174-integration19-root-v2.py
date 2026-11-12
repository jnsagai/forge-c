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
OUT = OPS / 'codex-integration19-exports-v2'
RUN = OUT / 'evidence/v0.4/runs/CODEX-INTEGRATION19-20261105'
CRE = OUT / 'evidence/cre'
WT = B / 'repos/forge-c-014-integration19'
C = 'd244e2dfbf013090dad9b1b6f813d70fd504e8b2'
BASE = '03f968603369f7934fde478ae8fd107c40ecec8b'
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
decision = json.loads((OPS / 'capa174-fix-decision-root.json').read_text())
assert decision['candidate_revision'] == C and decision['baseline_revision'] == BASE
assert decision['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
assert all(g['result'] == 'PASS' for g in decision['hard_gates'])
prevention = next(g['evidence_refs'] for g in decision['hard_gates'] if g['name'] == 'prevention')
assert len(prevention) == 173
suite = ET.parse(OPS / 'codex-integration19-combined.xml').getroot()
cases = list(suite.iter('testcase'))
assert len(cases) == 92 and not any(list(c) for c in cases)
assert 'PASS: 14 static design tests' in (OPS / 'codex-integration19-design.log').read_text()
assert (OPS / 'codex-integration19-ruff.log').read_text().strip() == 'All checks passed!'
for rel in ('factory/python/forge_factory/afo/line_maintenance_coordinator.py','factory/python/forge_factory/offline/export.py','factory/python/forge_factory/offline/patch.py','scripts/forge-offline-update.py','factory/python/tests/test_line_maintenance_renewal.py','factory/python/tests/test_da014_offline_roundtrip.py','factory/python/tests/fixtures/offline_roundtrip.py'):
    assert subprocess.check_output(['git', 'show', f'{C}:{rel}'], cwd=WT) == (WT / rel).read_bytes()
old_manifest = subprocess.check_output(['git', 'show', f'{BASE}:tests/reliability/reproducers/manifest.yaml'], cwd=WT)
assert (WT / 'tests/reliability/reproducers/manifest.yaml').read_bytes().startswith(old_manifest)
store = CREStore()
records, benchmarks = {}, {}
with store.conn() as conn:
    db = dict(conn.execute('SELECT * FROM cre_promotion_decisions WHERE decision_id=?', (decision['decision_id'],)).fetchone())
    assert json.loads(db['record']) == {k: v for k, v in decision.items() if k not in ('candidate_revision', 'baseline_revision')}
    assert db['candidate'] == C and db['baseline'] == BASE
    for row in conn.execute("SELECT * FROM cre_reproducer_runs WHERE reproducer_id='RPR-174'"):
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
assert registry.must('CAPA-174')['state'] == 'EFFECTIVENESS_OBSERVING'
write(CRE / 'capa/capa-174.json', registry.must('CAPA-174'))
write(CRE / 'capa/capa-174-history.json', registry.history('CAPA-174'))
write(CRE / 'capa/capa-174-links.json', registry.links('CAPA-174'))
for name in ('offline-roundtrip-inputs-before-tests.json','capa174-oracle-inputs-before-tests.json',
 'capa174-oracle-v3-inputs-before-tests.json','capa174-crewtrees-inputs-before-tests.json','capa174-v3-crewtrees-inputs-before-tests.json',
 'codex-integration19-inputs-before-tests.json','offline-reports-runner-red.xml','offline-reports-runner-red.log',
 'offline-reports-runner-green-v1.xml','offline-reports-runner-green-v1.log','offline-reports-runner-ruff-v1.log',
 'offline-kernel-roundtrip-v1.xml','offline-kernel-roundtrip-v1.log','m7-renewal-red.xml','m7-renewal-red.log',
 'm7-renewal-red-v2.xml','m7-renewal-red-v2.log','offline-m7-combined-v1.xml','offline-m7-combined-v1.log',
 'offline-m7-combined-v2.xml','offline-m7-combined-v2.log','offline-m7-design.log','offline-m7-ruff.log',
 'codex-integration19-combined.xml','codex-integration19-combined.log','codex-integration19-design.log','codex-integration19-ruff.log',
 'capa174-causal-and-fix-root.py','capa174-causal-and-fix-root.log','capa174-causal-and-fix-root-v3.py',
 'capa174-causal-and-fix-root-v3.log','package-capa174-integration19-root.py','package-capa174-integration19-root-v2.py','integration19-packaging-first-error.json'):
    source = OPS / name
    if source.is_file():
        copy(source, RUN / name)
copy(WT / 'tests/reliability/reproducers/manifest.yaml', RUN / 'frozen-manifest.yaml')
log = (OPS / 'codex-integration19-combined.log').read_text()
roundtrip = json.JSONDecoder().raw_decode(log[log.index('{"activation"'):])[0]
assert roundtrip['network_errno'] == 101 and len(roundtrip['rejected']) == 7 and roundtrip['receipts'] == 9
validation = dict(schema='forge-c/integration19-validation/1',candidate=C,baseline=BASE,
 status='ELIGIBLE_FOR_OFFLINE_REVIEW_ONLY',decision_id=decision['decision_id'],passed=92,failures=0,errors=0,skipped=0,
 design_checks=14,ruff_python_files=9,prevention_passed=173,causal_baseline='SYMPTOM_PRESENT',causal_candidate='SYMPTOM_ABSENT',
 source_identity_fixture_leaf=True,real_control_crypto=True,private_nss_fixture=True,
 original_oracle_errors_preserved=['rr-a480d4b26c2c7fad407c','rr-e97d1a258d7b13dea15a'],
 original_fixture_setup_errors_preserved=True,original_auto_backend_skip_preserved=True,
 markdown_report='IMPLEMENTED_AND_TESTED',portable_runner='IMPLEMENTED_AND_TESTED',
 kernel_isolated_roundtrip=roundtrip,native_factory_roundtrip='NOT_RUN',human_review_to_CAPA_bridge='NOT_IMPLEMENTED',
 live_patch_import=False,actual_mission_amendment=False,actual_trial_activation=False,model_calls=0,
 owner_clock_direction='Ignore clock synchronization; no NTP retry or synchronization-only hold; preserve existing signature expiry and budgets.',
 limitations=['CPU control roundtrip uses synthetic CRE metadata and generated TEST keys. Actual source separately passed normal independent CRE.',
  'Frozen RPR174 declares generic job/origin and source-identity metadata fixture leaves. CRE import preflight pins actual code; normal real control signatures, profile, intent and effective ledger checks execute.',
  'No actual model competence, human-review learning benefit or endurance acceptance is established.',
  'Existing signed GEN35 packet is unchanged; revised campaign requires exact source/authority binding.',
  'Clean signed release trees keep dependencies, owner inputs and mutable state outside. Missing local dependencies do not trigger online fetch.',
  'No main merge, safety approval, automatic source promotion or production release.'])
write(RUN / 'validation.json', validation)
files = [dict(path=str(f.relative_to(OUT)), sha256=sha(f), bytes=f.stat().st_size)
         for f in sorted(OUT.rglob('*')) if f.is_file()]
write(OPS / 'codex-integration19-qualified-index-v2.json', dict(source=C, baseline=BASE, decision_id=decision['decision_id'],
    status=validation['status'], exports=str(OUT), files=files))
print(json.dumps(dict(files=len(files), raw_records=len(records), decision_id=decision['decision_id'],
    index_sha256=sha(OPS / 'codex-integration19-qualified-index-v2.json'))))
