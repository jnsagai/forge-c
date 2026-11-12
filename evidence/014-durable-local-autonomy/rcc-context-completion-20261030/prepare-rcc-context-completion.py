"""Exact same-mission real factory-defect repair scope; no time/budget renewal or inference."""
from pathlib import Path
import ast,copy,json,os,subprocess,sys,time
import yaml
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo'
OLD=P/'deployment/aspice-rcc-pair-20261030-v1';O=P/'deployment/rcc-context-completion-20261030-v1';PREV=P/'deployment/rcc-inspector-context-repair-20261030-v1';REV='ab46545c1cfb7ffd90fb09715b6715b7d21ad242'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import authz,policy,operations,contracts
from forge_factory.afo.queue import ReadSnapshot,order_id_for
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.lrtx import stack,profile
from forge_factory.lrtx.role_capability import key
from forge_factory.common import utc_now,sha256_file
old=json.loads((OLD/'scope.json').read_text())
assert time.time()<old['deadline_epoch'] and operations.Intent().read()['mode']=='RUNNING' and operations.Intent().read()['epoch']==52
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==old['source_revision']
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as S:
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
  mids=[r[0] for r in c.execute('SELECT mission_id FROM afo_missions')]
 histories={mid:MissionLedger(S).snapshot(mid) for mid in mids}
 assert S.order(old['ll']['order_id'])['state']=='BLOCKED'
before=histories[old['mission_id']];assert before['limits']['deadline']==old['deadline_epoch']
oracle=json.loads((PREV/'oracle-v2.json').read_text());assert oracle['baseline_exit_code']==1 and oracle['candidate_exists'] is False
prof=profile.load(old['profile']);provider=stack.serving_instance(stack.settings(old['profile']))
allocation=json.loads((OLD/'allocation.json').read_text());assert allocation['provider_instance']==provider
request='f014-rcc-context-completion-20261030-v1'
oid=order_id_for(old['ll']['tenant_scope'],request)
primary='AUTH-014-RCC-CONTEXT-COMPLETION-20261030-V1'
roles='AUTH-014-RCC-CONTEXT-COMPLETION-ROLE-20261030-V1'
prior=yaml.safe_load(Path(os.environ['FORGE_AFO_POLICY']).read_text());proposed=copy.deepcopy(prior);proposed['authorization_ref']=primary
parent_job=json.loads((PREV/'enrolment.json').read_text())
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as S:
 with S.tx() as c:
  parent=json.loads(c.execute('SELECT record FROM afo_local_agent_jobs WHERE order_id=?',(parent_job['order_id'],)).fetchone()[0])
  assert parent['state']=='FAILED' and parent['error'].startswith('NO_VALID_MAINTENANCE_RECEIPT')
prepared=time.time();latest=prepared+300
proposed['budgets']['max_recovery_wall_seconds']=int(parent['deadline_epoch']-latest)
assert proposed['budgets']['max_recovery_wall_seconds']>0
assert not policy.schema_errors(proposed) and not policy.floor_violations(proposed)
paths=['factory/python/forge_factory/lrtx/structured.py']
catalog=[]
for rel in paths:
 raw=subprocess.check_output(['git','-C',str(R),'show',old['source_revision']+':'+rel]);tree=ast.parse(raw)
 catalog.append({'path':rel,'bytes':len(raw),'sha256':__import__('hashlib').sha256(raw).hexdigest(),
  'symbols':[{'name':n.name,'line':n.lineno} for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]})
scope={'schema':'forge-c/current-run-maintenance-scope/1','owner_instruction':old['owner_instruction'],
 'standing_signing_delegation':old['standing_signing_delegation'],'source_revision':REV,
 'repair_baseline_revision':REV,'profile':old['profile'],'profile_sha256':old['profile_sha256'],
 'model':old['model'],'model_digest':old['model_digest'],'precision':'Q8_0','reasoning':'xhigh','mtp_draft':3,
 'context_tokens':262144,'inference_slots':1,'verification_workers':1,'role_job_tokens':1000000,'max_retained_reworks':2,
 'deadline_epoch':old['deadline_epoch'],'deadline_utc':old['deadline_utc'],'deadline_changed':False,
 'mission_id':old['mission_id'],'mission_before':before,'continuation_of':old['ll']['order_id'],
 'tenant_scope':old['ll']['tenant_scope'],'request_id':request,'new_order_id':oid,'operator_preparation_epoch':52,
 'policy_before_sha256':digest(prior),'policy_sha256':digest(proposed),'primary_authorization':primary,'role_authorization':roles,
 'allowed_patch_paths':paths+['factory/python/tests/afo_candidate/**'],'candidate_limit_before_feedback':1,
 'failure_origin':'CURRENT_REAL_R008_PIPELINE_FAILURE_NOT_A_SEEDED_OUTAGE',
 'observed_failure':'Retained Qwen patch passes3 frozen context checks, but inherited call/refusal test raises AttributeError for time.monetic; previous native session reached CAPABILITY_LIMIT before reproducer or receipt. Preserve context work, correct measured regression and finish baseline-failing reproducer, pytest and submit.',
 'diagnosis_outcome':'No model generation: explicit temperature0/seedNone configuration absent from signed trial. External role-configuration correction is not a model engineering repair.',
 'oracle_sha256':oracle['oracle_sha256'],'original_freeze_sha256':sha256_file(PREV/'freeze.json'),
 'operator_authored_repair':False,'reference_patch_or_oracle_given_to_model':False,
 'source_activation':'Qualified bounded edit MCP only; pinned model/provider unchanged; Qwen authors engineering correction, no automatic candidate deployment',
 'previous_production_revision':old['source_revision'],'parent_job_id':parent['job_id'],
 'parent_native_run_id':parent['run_id'],'parent_recovery_deadline_epoch':parent['deadline_epoch'],
 'enrolment_latest_epoch':latest,'prepared_epoch':prepared,
 'retained_seed':{'path':str(PREV/'independent-unsubmitted-v1/structured.py'),'sha256':'f543f709245eb9d8458a1ecc9f291afece97816bca6c136a4dbf5e258825b3c9','native_write_seq':137,'completion_receipt':None},
 'independent_seed_context_result':{'path':str(PREV/'independent-unsubmitted-v1/result.json'),'sha256':sha256_file(PREV/'independent-unsubmitted-v1/result.json'),'status':'3PASS_FROZEN_SCOPE_ONLY'},
 'independent_seed_regression_result':{'path':str(PREV/'independent-unsubmitted-regression-v1/result.json'),'sha256':sha256_file(PREV/'independent-unsubmitted-regression-v1/result.json'),'status':'FAIL_INHERITED_REGRESSION'},
 'historical_counters_reset':False,'non_time_limits_changed':False,'original_scope_sha256':digest(old),
 'product_outcome':'BLOCKED','self_healing':'UNPROVEN','model_roles':'EXPERIMENT_NOT_QUALIFIED'}
issued=utc_now()
def grant(aid,runbook,actions,requests):
 g={'schema_version':'1.0','authorization_id':aid,'approver':'jefferson',
 'approval_evidence_ref':'owner-standing-rcc-context-repair-20261030:'+digest(scope),'issued_utc':issued,
 'expires_utc':scope['deadline_utc'],'policy_sha256':scope['policy_sha256'],'mode':'PILOT','allowed_actions':actions,
 'scope':{'order_ids':requests,'driver_classes':['LL','HAL'],'models':[scope['model']],
          'service_actions':['pause','drain','resume','shutdown']},
 'signature_ref':aid+'.sig','signed_runbook_ref':runbook}
 assert not authz.schema_errors(g),authz.schema_errors(g)
 return g
primarygrant=grant(primary,'factory-revision:'+scope['source_revision'],
 ['submit_workorder','launch_workorder','reconcile_run','recover_workorder','finalize_blocked','dead_letter','notify'],
 [old['ll']['request_id'],old['hal']['request_id'],request])
ids=[]
for mode in ('tool','unconstrained','json_schema','json_object'):
 identity={'role':'afo-factory-maintainer','model_digest':scope['model_digest'],'precision':'Q8_0','reasoning':'xhigh',
 'schema_mode':mode,'adapter_revision':scope['source_revision'],'context_tokens':262144,
 'sampling':{'seed':None,'temperature':None,'top_p':None},'task_class':'MAINTENANCE_ROLE_EXPERIMENT'}
 key(identity);ids.append(identity)
trial={'schema':'forge-c/product-role-trial/1','qualification_only':True,'source_revision':scope['source_revision'],
 'profile':scope['profile'],'profile_sha256':scope['profile_sha256'],'model':scope['model'],
 'roles':{'afo-factory-maintainer':ids},'order_ids':[oid],'deadline_epoch':scope['deadline_epoch'],
 'authorization_ref':roles,'context_allocation_ref':{'path':str(OLD/'allocation.json'),'sha256':sha256_file(OLD/'allocation.json')}}
ref={'path':f'afo/product-role-trials/{digest(trial)}.json','sha256':digest(trial)}
rolegrant=grant(roles,'qualification-product-014:'+digest(trial),['recover_workorder'],[request])
launch={'schema':'forge-c/afo-maintenance-replay-input/1','qualification_only':True,'no_product_launch':True,
 'source_kind':scope['failure_origin'],'profile':scope['profile'],'model':scope['model'],'purpose':'ASPICE_ONLY',
 'approved_factory_revision':scope['source_revision'],'product_role_trial':ref,
 'scope_sha256':digest(scope),'mission_id':scope['mission_id']}
env=json.loads((OLD/'envelope.json').read_text());env.update(request_id=request,manifest_sha256=digest(launch),
 input_manifest_ref=str(O/'inputs/launch.json'),authorization_ref=primary,submitted_utc=utc_now(),
 target='Factory structured inspector context propagation: actual RCC failure',git_revision=scope['source_revision'])
contracts.require('work-order',env)
for name,doc in {'scope.json':scope,'policy.json':proposed,'primary-authorization.json':primarygrant,
 'roles-authorization.json':rolegrant,'trial.json':trial,'trial-ref.json':ref,'envelope.json':env,'inputs/launch.json':launch,
 'all-missions-before.json':histories,'source-catalog.json':{'source_revision':scope['source_revision'],'entries':catalog},
 'owner-approval.json':{'scope_sha256':digest(scope),'standing_signing_delegation':scope['standing_signing_delegation'],
  'owner_answer':scope['owner_instruction'],'interpretation':'Standing delegated exact source activation and small same-RCC-mission completion of retained Qwen bytes; no fabricated receipt, no counter/deadline refill, parent recovery deadline bounded; Qwen authors correction/reproducer; oracles withheld','recorded_utc':utc_now()}}.items():immutable_json(O/name,doc)
immutable_bytes(O/'proposed-policy.yaml',yaml.safe_dump(proposed,sort_keys=False).encode())
for label,g in [('primary',primarygrant),('roles',rolegrant)]:immutable_bytes(O/(label+'-authorization-message.bin'),authz.message(g))
immutable_bytes(O/'allowed-signers',authz.ALLOWED_SIGNERS.read_bytes())
print(json.dumps({'status':'EXACT_UNSIGNED_MAINTENANCE_SCOPE_PREPARED','scope_sha256':digest(scope),
 'order_id':oid,'deadline_utc':scope['deadline_utc'],'source_unchanged':True,'mission_history_preserved':True,
 'no_model_generation':True}))
