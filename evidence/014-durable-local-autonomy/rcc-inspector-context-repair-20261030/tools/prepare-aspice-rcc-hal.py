"""Prepare dependent HAL only from the exact newly accepted Qwen LL execution. No inference/intake."""
from pathlib import Path
import json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/aspice-rcc-pair-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import authz,contracts,operations,policy
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.dispatch import package_verdict
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.inspection.engine import Store as Inspections,PHASES
from forge_factory.release.finalize import verify_archive
from forge_factory.common import sha256_file,utc_now
from forge_factory.lrtx import stack
from forge_factory import workorder as W
s=json.loads((O/'scope.json').read_text())
assert digest(s)=='3e60ba7507f085996b6ae838878a37f4bf5ae2d246fe4d4573c8ed137e519b47'
assert time.time()<s['deadline_epoch'] and operations.Intent().read()['mode']=='RUNNING' and operations.Intent().read()['epoch']==50
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==s['source_revision']
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as S:
 order=S.order(s['ll']['order_id'])
 if not order or order['state']!='READY_FOR_OFFLINE_REVIEW':
  print(json.dumps({'status':'NOT_READY_LL_NOT_INDEPENDENTLY_ACCEPTED','ll_state':(order or {}).get('state'),
                    'HAL_submitted':False,'files_created':0,'model_requests':0}));raise SystemExit(3)
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
 attempts=S.attempts(s['ll']['order_id']);assert attempts
 latest=max(attempts,key=lambda a:a['seq']);assert latest['state']=='SUCCEEDED'
 jobs=[]
 with S.tx() as c:
  for row in c.execute('SELECT record FROM afo_product_jobs'):
   job=json.loads(row[0])
   if job['order_id']==s['ll']['order_id'] and job['attempt_id']==latest['attempt_id']:jobs.append(job)
 selected=[]
 for job in jobs:
  execution=Executions(S).get(job['job_id'])
  if execution and execution['execution_liveness']=='QUIESCENT' and execution['resource_lease']=='RELEASED':
   selected.append((job,execution))
 assert len(selected)==1
 job,execution=selected[0];ws=Path(job['workspace']);man=json.loads((ws/'.forge-run/manifest.json').read_text())
 assert job['factory_revision']['commit']==s['source_revision'] and job['model']==s['model']
 assert man['purpose']=='ASPICE_ONLY' and (man.get('local_profile') or {}).get('id')==s['profile']
 native=(ws/'.forge-run/fabro_run_id').read_text().strip();assert native in execution['native_run_ids']
 verdict=package_verdict(ws/'.forge-run/package.json');assert verdict['verdict']=='READY_FOR_OFFLINE_REVIEW'
 pkg=json.loads((ws/'.forge-run/package.json').read_text())
 assert verify_archive(Path(pkg['archive']))['integrity']=='PASS'
 gates={phase:Inspections(ws).gate(phase) for phase in PHASES}
 assert all(row['decision']=='PASS' for row in gates.values())
 header,provided=W.provided_ll(ws.parent.name,'rcc')
 snapshot=MissionLedger(S).snapshot(s['mission_id'])
 assert snapshot['limits']['deadline']==s['deadline_epoch'] and snapshot['lineage']==s['mission_before']['lineage']
dependency={'source_work_order':ws.parent.name,'source_order_id':s['ll']['order_id'],'source_job_id':job['job_id'],
 'source_native_run_id':native,'source_revision':s['source_revision'],'archive_sha256':verdict['archive_sha256'],
 'provided_ll':provided,'phase_gates':{k:{'decision':v['decision'],'reason':v['reason']} for k,v in gates.items()},
 'source_header_sha256':__import__('hashlib').sha256(header).hexdigest(),'basis':'Existing independent archive verifier, six current gates and provided_ll import'}
settings=stack.settings(s['profile']);provider=stack.serving_instance(settings)
code="import json,urllib.request;x=json.load(urllib.request.urlopen('http://127.0.0.1:11457/props',timeout=5));print(json.dumps({'context':x.get('default_generation_settings',{}).get('n_ctx'),'slots':x.get('total_slots')}))"
r=subprocess.run(stack._nsenter(stack._holder(settings))+[str(P/'venv/bin/python'),'-c',code],capture_output=True,text=True,check=True,timeout=15)
assert json.loads(r.stdout)=={'context':262144,'slots':1}
allocation={'schema':'forge-c/context-allocation-probe/1','status':'PASS_ALLOCATION_ONLY',
 'provider_context_tokens':262144,'provider_slot_count':1,'model_digest':s['model_digest'],'precision':'Q8_0',
 'kv_precision':'f16','mtp_draft':3,'reasoning_effort':'xhigh','profile_sha256':s['profile_sha256'],
 'generation_requests':0,'provider_instance':provider,'at':utc_now()}
immutable_json(O/'hal-allocation.json',allocation)
prior=json.loads((O/'trial.json').read_text())
trial={**prior,'order_ids':[s['hal']['order_id']],'authorization_ref':'AUTH-014-ASPICE-RCC-HAL-ROLES-20261030-V1',
       'verified_ll_dependency_sha256':digest(dependency),
       'context_allocation_ref':{'path':str(O/'hal-allocation.json'),'sha256':sha256_file(O/'hal-allocation.json')}}
sha=digest(trial);ref={'path':f'afo/product-role-trials/{sha}.json','sha256':sha}
g={'schema_version':'1.0','authorization_id':trial['authorization_ref'],'approver':'jefferson',
 'approval_evidence_ref':'owner-standing-afo-aspice-20261030:'+digest(s),'issued_utc':utc_now(),'expires_utc':s['deadline_utc'],
 'policy_sha256':s['policy_sha256'],'mode':'PILOT','allowed_actions':['recover_workorder'],
 'scope':{'order_ids':[s['hal']['request_id']],'driver_classes':['HAL'],'models':[s['model']]},
 'signature_ref':trial['authorization_ref']+'.sig','signed_runbook_ref':'qualification-product-014:'+sha}
assert not authz.schema_errors(g),authz.schema_errors(g)
launch={'schema':'forge-c/product-launch/1','example':s['hal']['example'],'purpose':'ASPICE_ONLY','model':s['model'],
 'provider':'ollama','model_profile':s['model'],'profile':s['profile'],'approved_factory_revision':s['source_revision'],
 'provided_from':ws.parent.name,'verified_ll_dependency':dependency,'product_role_trial':ref,
 'product_attempt_token_reservations':[s['ll']['product_attempt_token_reservation']]*1000,
 'resume_max_attempts':1000,'resume_max_wall_seconds':28800,'mission_id':s['mission_id'],'scope_sha256':digest(s),
 'functional_gates_blocking':True,'advisory_continue':False}
raw=json.dumps(launch,sort_keys=True,separators=(',',':')).encode()
old=json.loads((O/'envelope.json').read_text())
env={**old,'request_id':s['hal']['request_id'],'driver_class':'HAL','target':'Full RCC HAL SWE.1-SWE.6 ASPICE development experiment',
 'manifest_sha256':__import__('hashlib').sha256(raw).hexdigest(),
 'input_manifest_ref':'.evidence-tmp/aspice-rcc-pair-20261030-v1/hal-launch.json','submitted_utc':utc_now()}
contracts.require('work-order',env)
entry={'order_id':s['hal']['order_id'],'continuation_of':s['ll']['order_id'],'envelope':env,
 'mission':{'mission_id':s['mission_id'],'lineage':snapshot['lineage'],'limits':snapshot['limits'],
            'authorization_ref':snapshot['authorization_ref'],'admission_authorization_ref':s['primary_authorization'],
            'request':{'order_id':s['hal']['request_id'],'driver_class':'HAL','model':s['model']}}}
for name,doc in {'hal-dependency.json':dependency,'hal-trial.json':trial,'hal-trial-ref.json':ref,
 'hal-roles-authorization.json':g,'hal-envelope.json':env,'hal-entry.json':entry}.items():immutable_json(O/name,doc)
immutable_bytes(O/'hal-launch.json',raw);immutable_bytes(O/'hal-roles-authorization-message.bin',authz.message(g))
print(json.dumps({'status':'DEPENDENT_HAL_UNSIGNED_SCOPE_PREPARED','source_ll_native':native,
 'dependency_sha256':digest(dependency),'mission_id':s['mission_id'],'new_mission_created':False,
 'HAL_submitted':False,'model_requests':0}))
