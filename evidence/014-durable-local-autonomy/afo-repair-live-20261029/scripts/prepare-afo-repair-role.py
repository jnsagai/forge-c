"""Bind the measured allocation and one maintenance role to an exact finite experiment."""
from pathlib import Path
import json,os,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/afo-repair-live-20261029-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import authz,contracts,operations,policy
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.afo.queue import Store
from forge_factory.common import sha256_file,utc_now
from forge_factory.lrtx.role_capability import key
scope=json.loads((O/'scope.json').read_text());allocation=json.loads((O/'allocation.json').read_text())
assert operations.Intent().read()['mode']=='RUNNING' and operations.Intent().read()['epoch']==34
assert allocation['status']=='PASS_ALLOCATION_ONLY' and allocation['profile_sha256']==scope['profile_sha256']
assert allocation['provider_context_tokens']==131072 and allocation['provider_slot_count']==1
assert time.time()<scope['deadline_epoch']
identities=[]
for mode in ('tool','unconstrained','json_schema','json_object'):
    identity={'role':'afo-factory-maintainer','model_digest':scope['model_digest'],'precision':'Q8_0',
      'reasoning':'xhigh','schema_mode':mode,'adapter_revision':scope['source_revision'],'context_tokens':131072,
      'sampling':{'seed':None,'temperature':None,'top_p':None},'task_class':'MAINTENANCE_ROLE_EXPERIMENT'}
    key(identity);identities.append(identity)
trial={'schema':'forge-c/product-role-trial/1','qualification_only':True,'source_revision':scope['source_revision'],
 'profile':scope['profile'],'profile_sha256':scope['profile_sha256'],'model':scope['model'],
 'roles':{'afo-factory-maintainer':identities},'order_ids':[scope['new_order_id']],
 'deadline_epoch':scope['deadline_epoch'],'authorization_ref':scope['role_authorization'],
 'context_allocation_ref':{'path':str(O/'allocation.json'),'sha256':sha256_file(O/'allocation.json')}}
sha=digest(trial);ref={'path':f'afo/product-role-trials/{sha}.json','sha256':sha}
grant={'schema_version':'1.0','authorization_id':scope['role_authorization'],'approver':'jefferson',
 'approval_evidence_ref':'owner-afo-repair-resume-20261029:'+digest(scope),'issued_utc':utc_now(),
 'expires_utc':scope['deadline_utc'],'policy_sha256':scope['policy_sha256'],'mode':'PILOT',
 'allowed_actions':['recover_workorder'],'scope':{'order_ids':[scope['request_id']],'driver_classes':['LL'],
 'models':[scope['model']],'service_actions':['pause','drain','resume','shutdown']},
 'signature_ref':scope['role_authorization']+'.sig','signed_runbook_ref':'qualification-product-014:'+sha}
assert not authz.schema_errors(grant),authz.schema_errors(grant)
launch={'schema':'forge-c/afo-maintenance-replay-input/1','qualification_only':True,'evaluation_holdout':True,
 'source_kind':'HISTORICAL_REAL_FAILURE_REPLAY_NOT_A_NEW_OUTAGE','profile':scope['profile'],'model':scope['model'],
 'purpose':'QM','approved_factory_revision':scope['source_revision'],'product_role_trial':ref,
 'scope_sha256':digest(scope),'mission_id':scope['mission_id'],'no_product_launch':True}
old=json.loads(Store().order(scope['continuation_of'])['envelope'])
env={**old,'request_id':scope['request_id'],'git_revision':scope['source_revision'],
 'manifest_sha256':digest(launch),'input_manifest_ref':str(O/'inputs/launch.json'),
 'authorization_ref':scope['primary_authorization'],'submitted_utc':utc_now(),'deadline_utc':scope['deadline_utc'],
 'target':'Forge-C MCP and hook context: historical factory maintenance replay',
 'safety_scope':'QM development qualification; no product, safety, compliance or model capability acceptance'}
contracts.require('work-order',env)
for name,doc in {'trial.json':trial,'trial-ref.json':ref,'roles-authorization.json':grant,'inputs/launch.json':launch,
 'envelope.json':env}.items():immutable_json(O/name,doc)
immutable_bytes(O/'roles-authorization-message.bin',authz.message(grant))
print(json.dumps({'status':'EXACT_ROLE_SIGNING_RECORD_PREPARED','trial_sha256':sha,'order_id':scope['new_order_id'],'model_requests':0}),flush=True)
