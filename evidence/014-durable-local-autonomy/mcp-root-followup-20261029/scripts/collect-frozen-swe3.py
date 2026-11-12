from pathlib import Path
import os,sys,json,io,tarfile,hashlib
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.inspection.engine import Store
from forge_factory.inspection.architecture import check_architecture
from forge_factory.common import utc_now
oid='afo-774900b297bdde37'
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as db:
 with db.tx() as c:
  jobs=[json.loads(r[0]) for r in c.execute('SELECT record FROM afo_product_jobs') if json.loads(r[0]).get('order_id')==oid]
job,=jobs;ws=Path(job['workspace']);store=Store(ws);phase='SWE.3'
baseline=store.latest_baseline(phase);assert baseline
assert baseline['baseline_hash']==store.current_hash(phase)
assert store.stale_reason(phase,baseline) is None
gate=store.gate(phase)
independent={'status':'NOT_RERUN_IN_READONLY_COLLECTION'}
inspections=store.inspections(phase);inspection=inspections[-1] if inspections else None
if inspection:assert inspection['baseline_hash']==baseline['baseline_hash']
selected=dict(baseline['files'])
for d in (ws/'configuration/baselines'/phase,ws/'inspection'/phase):
 for p in d.rglob('*.json'):
  if p.is_file() and not p.is_symlink():selected[p.relative_to(ws).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
for p in (ws/'build/target-cm55-gcc').rglob('*'):
 if p.is_file() and not p.is_symlink():selected[p.relative_to(ws).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
rows=[line for line in (ws/'evidence/tool-results.jsonl').read_text().splitlines() if json.loads(line).get('phase')==phase]
refs=set(ref.removeprefix('artifact:sha256:') for line in rows for ref in json.loads(line).get('result',{}).get('artifact_refs',[]) if ref.startswith('artifact:sha256:'))
for ref in refs:
 for p in (ws/'evidence/raw').glob(ref+'.*'):
  assert not p.is_symlink();selected[p.relative_to(ws).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
members={}
for rel,expected in selected.items():
 path=ws/rel
 assert not path.is_symlink() and ws.resolve() in path.resolve().parents
 raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==expected
 members[rel]=raw
members['captured-SWE.3-tool-results.jsonl']=('\n'.join(rows)+'\n').encode()
assert baseline['baseline_hash']==store.current_hash(phase)
summary={'schema':'forge-c/frozen-phase-snapshot/1','at':utc_now(),'order_id':oid,
 'job_id':job['job_id'],'phase':phase,'factory_revision':job['factory_revision'],
 'baseline':baseline,'actual_inspection':({k:inspection[k] for k in ('inspection_id','recorded_at','verdict','baseline_hash')} if inspection else None), 'phase_completion':('RECORDED_'+inspection['verdict'] if inspection else 'INSPECTION_PENDING'),
 'current_baseline_verified':True,'deterministic_gate':gate,'additional_checks':independent,
 'generation_requests':0,'read_only':True,'product_acceptance':'NOT_ESTABLISHED',
 'files':{rel:{'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)} for rel,raw in members.items()}}
members['transfer-manifest.json']=(json.dumps(summary,indent=2)+'\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as t:
 for rel,raw in members.items():
  item=tarfile.TarInfo(rel);item.size=len(raw);item.mode=0o600
  t.addfile(item,io.BytesIO(raw))
