"""Seal actual source qualification and private CPU review-cycle evidence only."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

from forge_factory.reliability.capa import CapaRegistry
from forge_factory.reliability.policy import load
from forge_factory.reliability.store import CREStore

B=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c')
OPS=B/'ops/scratch'
WT=B/'repos/forge-c-014-integration20'
OUT=OPS/'codex-integration20-exports'
RUN=OUT/'evidence/v0.4/runs/CODEX-INTEGRATION20-20261105'
CRE=OUT/'evidence/cre'
PRIVATE=OPS/'review-learning-real-cycle-20261105'
C='03da05043307b02439061d3a92b3744d8337b39f'
BASE='18814617abb98491abb5c03adb0802553634f14f'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x') as stream:json.dump(value,stream,indent=2)

def copy(src,dst):
    assert not dst.exists()
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dst)
    assert sha(src)==sha(dst)

assert not OUT.exists()
assert not list(PRIVATE.glob('TEST-review-key-*')), 'TEST_KEY_CLEANUP_REQUIRED'
cycle=json.loads((PRIVATE/'result.json').read_text())
assert cycle['status']=='PASS_PRIVATE_CPU_CONTROL' and cycle['first_prevention']==174 and cycle['next_prevention']==175
assert cycle['model_calls']==0 and cycle['source_or_service_activation'] is False
unit=ET.parse(OPS/'review-learning-final.xml').getroot()
cases=list(unit.iter('testcase'))
assert len(cases)==87 and not list(unit.iter('failure'))+list(unit.iter('error'))+list(unit.iter('skipped'))
assert 'PASS: 14 static design tests' in (OPS/'review-learning-final-design.log').read_text()
assert (OPS/'review-learning-final-ruff-v2.log').read_text().strip()=='All checks passed!'
with subprocess.Popen(['git','show',f'{BASE}:tests/reliability/reproducers/manifest.yaml'],cwd=WT,
                      stdout=subprocess.PIPE) as process:
    old_manifest=process.communicate()[0];assert process.returncode==0
assert (WT/'tests/reliability/reproducers/manifest.yaml').read_bytes().startswith(old_manifest)
decisions=[('source',json.loads((OPS/'capa175-fix-decision-root.json').read_text()),CREStore()),
           ('private-first',json.loads((PRIVATE/'first-real-fix-decision.json').read_text()),
            CREStore(PRIVATE/'state/supervisor/incidents.sqlite3')),
           ('private-next',json.loads((PRIVATE/'next-real-fix-decision.json').read_text()),
            CREStore(PRIVATE/'state/supervisor/incidents.sqlite3'))]
records={};benchmarks={}
for label,decision,store in decisions:
    assert decision['candidate_revision']==C and decision['baseline_revision']==BASE
    assert decision['decision']=='ELIGIBLE_FOR_OFFLINE_REVIEW'
    expected=175 if label=='private-next' else 174
    prevention=next(g['evidence_refs'] for g in decision['hard_gates'] if g['name']=='prevention')
    assert len(prevention)==expected
    assert all(g['result']=='PASS' or label=='private-next' and g['name']=='reproducer'
               and g['result']=='NOT_RUN' and g['reason_code']=='NOT_APPLICABLE_FOR_CHANGE' for g in decision['hard_gates'])
    with store.conn() as connection:
        db=dict(connection.execute('SELECT * FROM cre_promotion_decisions WHERE decision_id=?',
                                   (decision['decision_id'],)).fetchone())
        assert json.loads(db['record'])=={k:v for k,v in decision.items() if k not in ('candidate_revision','baseline_revision')}
        assert db['candidate']==C and db['baseline']==BASE
        write(CRE/'decisions'/(decision['decision_id']+'.json'),decision)
        write(CRE/'decisions'/(decision['decision_id']+'-db-row.json'),db)
        for gate in decision['hard_gates']:
            for ref in gate['evidence_refs']:
                kind,_,rid=ref.partition(':')
                if kind=='reproducer-run':
                    value=dict(connection.execute('SELECT * FROM cre_reproducer_runs WHERE run_id=?',(rid,)).fetchone())
                    log=(B/'state/reliability/reproducers' if label=='source' else PRIVATE/'state/reliability/reproducers')/(rid+'.log')
                    assert sha(log)==value['log_sha256']
                    records[rid]=(value,log)
                elif kind=='benchmark-run':
                    benchmarks[rid]=dict(connection.execute('SELECT * FROM cre_benchmark_runs WHERE run_id=?',(rid,)).fetchone())
        if label=='source':
            for row in connection.execute("SELECT * FROM cre_reproducer_runs WHERE reproducer_id='RPR-175'"):
                value=dict(row);rid=value['run_id']
                log=B/'state/reliability/reproducers'/(rid+'.log')
                assert sha(log)==value['log_sha256']
                records[rid]=(value,log)
    registry=CapaRegistry(store,load())
    cid='CAPA-175' if label=='source' else cycle['capa_id']
    if label!='private-next':
        write(CRE/'capa'/(cid+'.json'),registry.must(cid))
        write(CRE/'capa'/(cid+'-history.json'),registry.history(cid))
        write(CRE/'capa'/(cid+'-links.json'),registry.links(cid))
for rid,(row,log) in records.items():
    copy(log,CRE/'reproducers'/log.name)
    write(CRE/'reproducers'/(rid+'.json'),row)
for rid,row in benchmarks.items():write(CRE/'benchmarks'/(rid+'.json'),row)
for name in ('review-learning-inputs-before-tests.json','capa175-oracle-inputs-before-tests.json',
 'capa175-crewtrees-inputs-before-tests.json','codex-integration20-inputs-before-tests.json',
 'review-learning-red.xml','review-learning-red.log','review-learning-green-v1.xml','review-learning-green-v1.log',
 'review-learning-cycle-v1.xml','review-learning-cycle-v1.log','review-learning-cycle-v2.xml','review-learning-cycle-v2.log',
 'review-learning-cycle-v3.xml','review-learning-cycle-v3.log','review-learning-combined-v1.xml','review-learning-combined-v1.log',
 'review-learning-combined-v2.xml','review-learning-combined-v2.log','review-learning-combined-v3.xml','review-learning-combined-v3.log',
 'review-producer-monitor-v1.xml','review-producer-monitor-v1.log','review-learning-final.xml','review-learning-final.log',
 'review-learning-final-design.log','review-learning-final-ruff-v2.log','capa175-causal-and-fix-root.py',
 'capa175-causal-and-fix-root.log','review-learning-real-cycle.py','review-learning-real-cycle.log',
 'package-review-learning-integration20.py'):
    if (OPS/name).is_file():copy(OPS/name,RUN/name)
for name in ('result.json','first-real-fix-decision.json','next-real-fix-decision.json','worktrees-before-tests.json',
 'TEST-allowed-signers','reviews/DSP-REAL-CPU-CONTROL.json','reviews/DSP-REAL-CPU-CONTROL.sig',
 'staged-reproducer/reproducer.py','staged-reproducer/manifest.yaml','outgoing/report.zip','outgoing/report.zip.sha256',
 'outgoing/report.md','lesson-and-delivery-proof.json'):
    copy(PRIVATE/name,RUN/'private-control'/name)
copy(WT/'tests/reliability/reproducers/manifest.yaml',RUN/'frozen-manifest.yaml')
validation=dict(schema='forge-c/integration20-validation/1',source=C,baseline=BASE,status='ELIGIBLE_FOR_OFFLINE_REVIEW_ONLY',
 decision_ids={label:d['decision_id'] for label,d,_ in decisions},tests_passed=87,failures=0,errors=0,skipped=0,
 design_checks=14,ruff_python_files=13,protected_prevention=174,next_private_prevention=175,
 causal_baseline='SYMPTOM_PRESENT',causal_candidate='SYMPTOM_ABSENT',private_review_cycle=cycle,
 original_synthetic_unit_rows_labelled_not_qualification=True,original_failures_preserved=True,
 native_human_review_learning_benefit='NOT_MEASURED',native_role_qualification='NOT_RUN',
 mission_amendment=False,live_source_activation=False,model_calls=0,
 limitations=['Private CONTROL review uses generated TEST signatures, not owner acceptance. Both independent source/staged decisions and the next CHANGE are genuine normal CRE executions.',
 'Scoped future-author MCP delivery is demonstrated; no model competence or measured product improvement is claimed.',
 'Historical held-out evidence/rates remain unchanged. Only protected source-bound completed-calibration learning transfers are honored.',
 'Current GEN35 signed packet remains unchanged. Revised exact source/authority campaign preparation and other outstanding Feature014 tasks remain.',
 'No main merge, automatic deployment, safety approval or production release.'])
write(RUN/'validation.json',validation)
files=[dict(path=str(p.relative_to(OUT)),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(OUT.rglob('*')) if p.is_file()]
write(OPS/'codex-integration20-qualified-index.json',dict(source=C,baseline=BASE,exports=str(OUT),
 decision_ids=validation['decision_ids'],status=validation['status'],files=files))
print(json.dumps(dict(files=len(files),raw_records=len(records),index_sha256=sha(OPS/'codex-integration20-qualified-index.json'))))
