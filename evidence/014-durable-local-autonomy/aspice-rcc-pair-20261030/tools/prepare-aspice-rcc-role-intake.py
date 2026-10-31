"""Fresh provider allocation, bounded experimental roles and real initial LL context; zero inference."""
from pathlib import Path
import copy,json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/aspice-rcc-pair-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
os.environ['FORGE_LRTX_CONTEXT_TOKENS']='262144'
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import authz,contracts,operations,policy
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.lrtx import stack,profile,structured,swe1
from forge_factory.lrtx.role_capability import key
from forge_factory.llm_gateway import sanitize_request
from forge_factory.afo.diagnosis_packet import measure_request
from forge_factory.common import sha256_file,utc_now
from forge_factory import workorder as W
s=json.loads((O/'scope.json').read_text());assert digest(s)=='3e60ba7507f085996b6ae838878a37f4bf5ae2d246fe4d4573c8ed137e519b47'
assert time.time()<s['deadline_epoch'] and operations.Intent().read()['mode']=='RUNNING' and operations.Intent().read()['epoch']==50
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==s['source_revision']
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
S=Store();assert not Executions(S).pending();snapshot=MissionLedger(S).snapshot(s['mission_id'])
assert snapshot['limits']=={**s['new_non_time_limits'],'deadline':s['deadline_epoch']}
prof=profile.load(s['profile']);settings=stack.settings(s['profile']);provider=stack.serving_instance(settings)
health=stack.status(settings)['health'];assert all(health.get(k) for k in ('fabro','gateway','ollama','llama_server'))
code="import json,urllib.request;x=json.load(urllib.request.urlopen('http://127.0.0.1:11457/props',timeout=5));print(json.dumps({'context':x.get('default_generation_settings',{}).get('n_ctx'),'slots':x.get('total_slots')}))"
r=subprocess.run(stack._nsenter(stack._holder(settings))+[str(P/'venv/bin/python'),'-c',code],capture_output=True,text=True,check=True,timeout=15)
assert json.loads(r.stdout)=={'context':262144,'slots':1}
allocation={'schema':'forge-c/context-allocation-probe/1','status':'PASS_ALLOCATION_ONLY',
 'provider_context_tokens':262144,'provider_slot_count':1,'model_digest':s['model_digest'],'precision':'Q8_0',
 'kv_precision':'f16','mtp_draft':3,'reasoning_effort':'xhigh','profile_sha256':s['profile_sha256'],
 'generation_requests':0,'provider_instance':provider,'at':utc_now()}
immutable_json(O/'allocation.json',allocation)
roles={}
for role in [f'swe{i}-{r}' for i in range(1,7) for r in ('author','inspector')]+['release-manager','afo-recovery-planner','afo-factory-maintainer']:
 roles[role]=[]
 for mode in ('tool','unconstrained','json_schema','json_object'):
  for sampling in ({'seed':None,'temperature':None,'top_p':None},{'seed':1,'temperature':0.2,'top_p':None},{'seed':1,'temperature':0,'top_p':None}):
   identity={'role':role,'model_digest':s['model_digest'],'precision':'Q8_0','reasoning':'xhigh',
    'schema_mode':mode,'adapter_revision':s['source_revision'],'context_tokens':262144,
    'sampling':sampling,'task_class':'PRODUCT_ROLE_EXPERIMENT' if role.startswith('swe') or role=='release-manager' else 'MAINTENANCE_ROLE_EXPERIMENT' if role=='afo-factory-maintainer' else 'PRODUCT_DIAGNOSIS_EXPERIMENT'}
   key(identity);roles[role].append(identity)
trial={'schema':'forge-c/product-role-trial/1','qualification_only':True,'source_revision':s['source_revision'],
 'profile':s['profile'],'profile_sha256':s['profile_sha256'],'model':s['model'],'roles':roles,
 'order_ids':[s['ll']['order_id']],'deadline_epoch':s['deadline_epoch'],
 'authorization_ref':'AUTH-014-ASPICE-RCC-ROLES-20261030-V1',
 'context_allocation_ref':{'path':str(O/'allocation.json'),'sha256':sha256_file(O/'allocation.json')}}
trialsha=digest(trial);ref={'path':f'afo/product-role-trials/{trialsha}.json','sha256':trialsha}
g={'schema_version':'1.0','authorization_id':trial['authorization_ref'],'approver':'jefferson',
 'approval_evidence_ref':'owner-standing-afo-aspice-20261030:'+digest(s),'issued_utc':utc_now(),
 'expires_utc':s['deadline_utc'],'policy_sha256':s['policy_sha256'],'mode':'PILOT','allowed_actions':['recover_workorder'],
 'scope':{'order_ids':[s['ll']['request_id']],'driver_classes':['LL'],'models':[s['model']]},
 'signature_ref':trial['authorization_ref']+'.sig','signed_runbook_ref':'qualification-product-014:'+trialsha}
assert not authz.schema_errors(g),authz.schema_errors(g)
launch={'schema':'forge-c/product-launch/1','example':s['ll']['example'],'purpose':'ASPICE_ONLY',
 'model':s['model'],'provider':'ollama','model_profile':s['model'],'profile':s['profile'],
 'approved_factory_revision':s['source_revision'],'product_role_trial':ref,
 'product_attempt_token_reservations':[s['ll']['product_attempt_token_reservation']]*1000,
 'resume_max_attempts':1000,'resume_max_wall_seconds':28800,'mission_id':s['mission_id'],
 'scope_sha256':digest(s),'functional_gates_blocking':True,'advisory_continue':False}
launchraw=json.dumps(launch,sort_keys=True,separators=(',',':')).encode()
launchref='.evidence-tmp/aspice-rcc-pair-20261030-v1/ll-launch.json'
old=json.loads(S.order(s['ll']['continuation_of'])['envelope'])
env={**old,'request_id':s['ll']['request_id'],'tenant_scope':s['ll']['tenant_scope'],'git_revision':s['source_revision'],
 'manifest_sha256':__import__('hashlib').sha256(launchraw).hexdigest(),'input_manifest_ref':launchref,
 'authorization_ref':s['primary_authorization'],'submitted_utc':utc_now(),'deadline_utc':s['deadline_utc'],
 'target':'Full RCC LL SWE.1-SWE.6 ASPICE development experiment',
 'model_profile':s['model'],'safety_scope':'ASPICE_ONLY; safety NOT_ASSESSED; offline review only, no certification',
 'approved_by':'jefferson (standing delegated signing)'}
contracts.require('work-order',env)
entry={'order_id':s['ll']['order_id'],'continuation_of':s['ll']['continuation_of'],'envelope':env,
 'mission':{'mission_id':s['mission_id'],'lineage':snapshot['lineage'],'limits':snapshot['limits'],
            'authorization_ref':snapshot['authorization_ref'],
            'request':{'order_id':s['ll']['request_id'],'driver_class':'LL','model':s['model']}}}
for name,doc in {'trial.json':trial,'trial-ref.json':ref,'roles-authorization.json':g,'envelope.json':env,'entry.json':entry}.items():immutable_json(O/name,doc)
immutable_bytes(O/'roles-authorization-message.bin',authz.message(g));immutable_bytes(O/'launch.json',launchraw)
# Separate real input-only preparation: future phase requests cannot exist before Qwen authors their inputs.
os.environ['FORGE_STATE_DIR']=str(O/'input-preflight-state');os.environ['FORGE_EVENTS_DIR']=str(O/'input-preflight-events')
ws,man=W.prepare(R/s['ll']['example'],'WO-F014-RCC-LL-ASPICE-INITIAL-PREFLIGHT',purpose='ASPICE_ONLY')
man['local_profile']={'id':s['profile'],'version':prof['version'],'config_sha256':prof['_sha256']}
(ws/'.forge-run/manifest.json').write_text(json.dumps(man))
token=structured.RECOVERY_WORKSPACE.set(ws)
inv=swe1.inventory(ws);groups=swe1.groups(inv);assert groups and not inv['missing_sections']
rows=[]
for group in groups:
 packet=swe1.group_packet(ws,group,s['model'])
 body={'model':s['model'],'messages':packet['_messages'],'stream':True,'max_tokens':packet['output_reserve'],
       'stream_options':{'include_usage':True},'response_format':{'type':'json_schema','json_schema':{'name':'packet_output','strict':True,'schema':packet['output_schema']}}}
 effective=sanitize_request(body,policy=prof['gateway']['reasoning']);measure=measure_request(effective)
 total=measure['input_tokens']+effective['max_tokens'];assert total<=262144
 rows.append({'task':packet['task'],'fields':len(group['fields']),'request_sha256':digest(effective),
              'measurement':measure,'effective_output_cap':effective['max_tokens'],'conservative_reservation':total})
structured.RECOVERY_WORKSPACE.reset(token)
immutable_json(O/'initial-request-preflight.json',{'status':'PASS_INITIAL_SWE1_GROUP_CONTEXT_ONLY','source_revision':s['source_revision'],
 'workspace':str(ws),'global_inventory_sha256':digest(inv),'inventory_items':len(inv['items']),'groups':len(groups),
 'missing_sections':inv['missing_sections'],'rows':rows,'maximum_conservative_reservation':max(r['conservative_reservation'] for r in rows),
 'complete_pipeline_roles':[f'swe{i}-{r}' for i in range(1,7) for r in ('author','inspector')],
 'later_phase_context':'NOT_YET_AUTHORED; each actual complete serialized request independently admitted at runtime',
 'model_requests':0,'capability_qualification':'NOT_RUN','product_acceptance':'NOT_RUN','generation_performed':False})
print(json.dumps({'status':'UNSIGNED_ROLE_AND_INTAKE_PREPARED_INITIAL_CONTEXT_PASS','roles':len(roles),'configurations_per_role':12,
 'groups':len(groups),'inventory_items':len(inv['items']),'maximum_conservative_reservation':max(r['conservative_reservation'] for r in rows),
 'deadline_utc':s['deadline_utc'],'model_requests':0}))
