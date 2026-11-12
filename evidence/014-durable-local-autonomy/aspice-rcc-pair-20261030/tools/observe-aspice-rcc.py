"""Read-only actual product/native facts, never prompts, reasoning or model calls."""
from pathlib import Path
import collections,json,os,sys
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/aspice-rcc-pair-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.operations import Intent
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.common import utc_now
s=json.loads((O/'scope.json').read_text());out={'at':utc_now(),'operator':{k:Intent().read()[k] for k in ('mode','epoch')},
 'source_revision':s['source_revision'],'order_id':s['ll']['order_id'],'model_requests_by_observer':0}
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as S:
 o=S.order(s['ll']['order_id']);out['order']={k:o.get(k) for k in ('state','terminal_reason','created_epoch')}
 out['attempts']=[{k:a.get(k) for k in ('attempt_id','seq','state','record')} for a in S.attempts(s['ll']['order_id'])]
 with S.tx() as c:
  jobs=[json.loads(row[0]) for row in c.execute('SELECT record FROM afo_product_jobs')]
  selected=[j for j in jobs if j['order_id']==s['ll']['order_id']]
  out['products']=[]
  for j in selected:
   e=Executions(S).get(j['job_id'])
   rows=[json.loads(row[0]) for row in c.execute('SELECT record FROM afo_request_ledger WHERE job_id=?',(j['job_id'],))]
   out['products'].append({k:j.get(k) for k in ('job_id','workspace','model','profile','reserved_tokens','deadline_epoch')})
   result=out['products'][-1]
   result['execution']={k:e.get(k) for k in ('execution_liveness','resource_lease','native_run_ids','task_outcome','terminal_reason')} if e else None
   result['request_states']=dict(collections.Counter(r['state'] for r in rows))
   result['reported_tokens_known']=sum(r.get('reported_tokens') or 0 for r in rows)
   result['requests_with_unknown_usage']=sum(r.get('reported_tokens') is None for r in rows)
   result['last_request_fields']=sorted(rows[-1]) if rows else []
   result['request_measurements']=[{k:r.get(k) for k in ('state','input_tokens_reserved','output_cap','reserved_tokens','reported_tokens','created_at','sent_at')} for r in rows[-3:]]
   inspections=Path(j['workspace'])/'inspection'
   result['inspection_files']=sorted(str(p.relative_to(Path(j['workspace']))) for p in inspections.rglob('*.json')) if inspections.is_dir() else []
  out['resources']=[dict(row) for row in c.execute('SELECT resource,holder,epoch FROM afo_resource_ownership')]
 out['mission']=MissionLedger(S).snapshot(s['mission_id'])
# Attempt records contain transport refs, not model text; only keep state, workspace and native references.
for a in out['attempts']:
 rec=a.get('record') or {}
 a['record']={k:v for k,v in rec.items() if k in ('fabro_run_id','run_id','workspace_ref','factory_revision','error','last_error','native_run_ref')}
if '--native' in sys.argv:
 from forge_factory.lrtx import stack
 os.environ.update(stack.envmap(stack.settings(s['profile'])))
 from forge_factory.fabro.client import FabroClient,load_token,run_status
 with FabroClient(token=load_token(),timeout=5) as client:
  for product in out.get('products',[]):
   execution=product.get('execution') or {}
   product['native_status_now']={}
   for rid in execution.get('native_run_ids',[]):
    native=client.get_run(rid);product['native_status_now'][rid]=run_status(native)
    product['native_metadata_keys']=sorted(native)
print(json.dumps(out,indent=2))
