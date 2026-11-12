from pathlib import Path
import json,os,sys,sqlite3,subprocess
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1')
os.environ.update(json.loads((E/'control/runtime-env-v6.json').read_text()));sys.path.insert(0,str(E/'source/factory/python'))
from forge_factory.afo.operations import Intent
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.durable import digest,immutable_json
from forge_factory.lrtx import provider_process as P
from forge_factory.fabro.client import FabroClient,load_token,run_status
from forge_factory.common import utc_now,sha256_file
rec=Intent().read();out={'schema':'forge-c/owner-window-settlement-observation/1','at':utc_now(),'intent':{k:rec.get(k) for k in ('mode','epoch','effective_stop','pending_start','reason','changed_at')},'model_calls':0,'candidate_execution':False}
services=json.loads((E/'run/services.json').read_text());instance=services['serving_instance']
out['serving_instance_sha256']=digest(instance);out['provider_init_pid']=instance['init_pid'];out['provider_quiet_proof']=P.quiet(instance)
end=E/'control/window-end-v4.json'
if end.is_file():
 d=json.loads(end.read_text());out['guard_end']={'path':str(end),'sha256':sha256_file(end),'at':d.get('at'),'settled':d.get('settled'),'renewed':d.get('renewed'),'attempt_count':len(d.get('attempts',[])),'last_attempt':d.get('attempts',[])[-1] if d.get('attempts') else None}
else:out['guard_end']=None
with sqlite3.connect('file:'+str(E/'state/conductor/conductor.sqlite3')+'?mode=ro',uri=True) as db:
 db.row_factory=sqlite3.Row
 out['inference_ownership']=[dict(r) for r in db.execute("SELECT resource,holder,epoch FROM afo_resource_ownership")]
 out['executions']=[]
 for row in db.execute('SELECT record FROM afo_execution_liveness'):
  d=json.loads(row[0]);out['executions'].append({k:d.get(k) for k in ('job_id','authorization_state','task_outcome','terminal_reason','execution_liveness','resource_lease','native_run_ids','quiescence_evidence_ref')})
 out['requests']=[dict(r) for r in db.execute('SELECT job_id,state,COUNT(*) AS n FROM afo_request_ledger GROUP BY job_id,state')]
 out['orders']=[dict(r) for r in db.execute('SELECT order_id,state,terminal_reason FROM afo_work_orders')]
 out['mission']=MissionLedger._snapshot(db,'mission-feature014-delivery-first-20261030')
try:
 with FabroClient(base_url='http://127.0.0.1:32404/api/v1',token=load_token(str(E/'fabro/storage')),timeout=3) as client:
  out['last_native_status']=run_status(client.get_run('01M68CMQAZNN7QGRZSX5DGRMYY'))
except Exception as exc:out['last_native_status']='NOT_OBSERVED:'+type(exc).__name__
out['source_revision']=subprocess.check_output(['git','-C',str(E/'source'),'rev-parse','HEAD'],text=True).strip()
out['settlement_conditions']={'intent_STOPPED':rec['mode']=='STOPPED','effective_stop':rec.get('effective_stop') is True,
 'provider_kernel_quiet':out['provider_quiet_proof'] is not None,
 'no_held_execution':all(x['resource_lease']!='HELD' for x in out['executions']),
 'no_inference_holder':all(not x['holder'] for x in out['inference_ownership'] if x['resource']=='inference'),
 'no_nonquiescent_requests':all(x['state']=='QUIESCENT' for x in out['requests'])}
out['limits']='Physical serving/native/request settlement only, not product/learning/availability qualification; no renewal'
p=E/'control/qualification-observations'/('owner-window-settlement-'+digest(out)+'.json');immutable_json(p,out)
print(json.dumps({'path':str(p),'sha256':sha256_file(p),'intent':out['intent'],'settlement_conditions':out['settlement_conditions'],'native_status':out['last_native_status'],'guard_end':out['guard_end']}))
