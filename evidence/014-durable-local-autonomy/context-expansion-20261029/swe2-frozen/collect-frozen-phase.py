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
job,=jobs;ws=Path(job['workspace']);store=Store(ws);phase='SWE.2'
baseline=store.latest_baseline(phase);assert baseline
assert baseline['baseline_hash']==store.current_hash(phase)
assert store.stale_reason(phase,baseline) is None
gate=store.gate(phase);assert gate['decision']=='PASS',gate
independent=check_architecture(ws);assert independent['verdict']=='PASS',independent
inspection=store.inspections(phase)[-1];assert inspection['baseline_hash']==baseline['baseline_hash'] and inspection['verdict']=='PASS'
selected=dict(baseline['files'])
for d in (ws/'configuration/baselines'/phase,ws/'inspection'/phase):
 for p in d.rglob('*.json'):
  if p.is_file() and not p.is_symlink():selected[p.relative_to(ws).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
members={}
for rel,expected in selected.items():
 path=ws/rel
 assert not path.is_symlink() and ws.resolve() in path.resolve().parents
 raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==expected
 members[rel]=raw
assert baseline['baseline_hash']==store.current_hash(phase)
summary={'schema':'forge-c/frozen-phase-snapshot/1','at':utc_now(),'order_id':oid,
 'job_id':job['job_id'],'phase':phase,'factory_revision':job['factory_revision'],
 'baseline':baseline,'actual_inspection':{'inspection_id':inspection['inspection_id'],'recorded_at':inspection['recorded_at'],'verdict':inspection['verdict'],'baseline_hash':inspection['baseline_hash']},
 'current_baseline_verified':True,'deterministic_gate':gate,'model_free_architecture_check':independent,
 'generation_requests':0,'read_only':True,'product_acceptance':'NOT_ESTABLISHED',
 'files':{rel:{'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)} for rel,raw in members.items()}}
members['transfer-manifest.json']=(json.dumps(summary,indent=2)+'\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as t:
 for rel,raw in members.items():
  item=tarfile.TarInfo(rel);item.size=len(raw);item.mode=0o600
  t.addfile(item,io.BytesIO(raw))
