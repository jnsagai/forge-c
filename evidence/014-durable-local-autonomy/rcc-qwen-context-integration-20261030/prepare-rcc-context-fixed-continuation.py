"""Prepare exact source-bound LL/HAL continuation; no new mission, cap, deadline or inference."""
from pathlib import Path
import copy,json,os,subprocess,sys,time
import yaml
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';Q=P/'deployment/qualification-integrated-qwen-e21aa74-v1/repo';OLD=P/'deployment/aspice-rcc-pair-20261030-v1';O=P/'deployment/aspice-rcc-context-fixed-20261030-v1';V=P/'deployment/rcc-signature-binding-20261030-v1'
REV='e21aa74411d01458bab45fee8af6d59f710fad03'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
os.environ['FORGE_REPO_ROOT']=str(Q);sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.afo import authz,policy,operations,contracts
from forge_factory.afo.queue import ReadSnapshot,order_id_for
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.common import utc_now,sha256_file
from forge_factory.lrtx import profile,stack
from forge_factory.lrtx.role_capability import key
s0=json.loads((OLD/'scope.json').read_text());assert time.time()<s0['deadline_epoch']
assert operations.Intent().read()['mode']=='RUNNING' and operations.Intent().read()['epoch']==56
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
assert git(R,'rev-parse','HEAD')=='ab46545c1cfb7ffd90fb09715b6715b7d21ad242' and not git(R,'status','--porcelain')
assert git(Q,'rev-parse','HEAD')==REV and not git(Q,'status','--porcelain')
d=json.loads((V/'environment-requalification-decision.json').read_text());assert d['decision']=='ELIGIBLE_FOR_OFFLINE_REVIEW' and all(g['result']=='PASS' for g in d['hard_gates'])
f=json.loads((P/'deployment/rcc-bound-candidate-bc931bd-independent-v1/verification/result.json').read_text());assert f['pytest_exit_code']==0 and f['source_sha256']==sha256_file(Q/'factory/python/forge_factory/lrtx/structured.py')
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as S:
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
  mids=[r[0] for r in c.execute('SELECT mission_id FROM afo_missions')]
 histories={mid:MissionLedger(S).snapshot(mid) for mid in mids};snap=histories[s0['mission_id']]
 assert snap['limits']['deadline']==s0['deadline_epoch'] and snap['corrections']==1 and snap['limits']['max_corrections']==1
 assert S.order(s0['ll']['order_id'])['state']=='BLOCKED'
 prior=yaml.safe_load(Path(os.environ['FORGE_AFO_POLICY']).read_text());proposed=copy.deepcopy(prior)
 primary='AUTH-014-ASPICE-RCC-CONTEXT-FIXED-20261030-V1';roleauth='AUTH-014-ASPICE-RCC-FIXED-ROLES-20261030-V1'
 proposed['authorization_ref']=primary;assert not policy.schema_errors(proposed) and not policy.floor_violations(proposed)
 llreq='f014-aspice-rcc-ll-context-fixed-20261030-v1';halreq='f014-aspice-rcc-hal-context-fixed-20261030-v1'
 tenant=s0['ll']['tenant_scope'];oid=order_id_for(tenant,llreq);haloid=order_id_for(tenant,halreq)
 prof=profile.load(s0['profile']);provider=stack.serving_instance(stack.settings(s0['profile']))
 allocation=json.loads((OLD/'allocation.json').read_text());assert allocation['provider_instance']==provider
 scope={'schema':'forge-c/source-bound-product-continuation/1','source_revision':REV,'previous_production_revision':git(R,'rev-parse','HEAD'),'profile':s0['profile'],'profile_sha256':prof['_sha256'],'model':s0['model'],'model_digest':s0['model_digest'],'precision':'Q8_0','reasoning':'xhigh','mtp_draft':3,'context_tokens':262144,'inference_slots':1,'verification_workers':1,'mission_id':s0['mission_id'],'mission_before':snap,'policy_before_sha256':digest(prior),'policy_sha256':digest(proposed),'primary_authorization':primary,'role_authorization':roleauth,'deadline_epoch':s0['deadline_epoch'],'deadline_utc':s0['deadline_utc'],'deadline_changed':False,'non_time_limits_changed':False,'historical_counters_reset':False,'operator_preparation_epoch':56,'standing_signing_delegation':'always approve it for now on automatically','owner_instruction':s0['owner_instruction'],'qwen_candidate':d['candidate_sha256'],'qwen_candidate_commit':f['candidate_commit'],'cre_decision':d['decision_id'],'frozen_context_sha256':sha256_file(P/'deployment/rcc-bound-candidate-bc931bd-independent-v1/verification/result.json'),'qualification_revision':REV,'ll':{'request_id':llreq,'order_id':oid,'tenant_scope':tenant,'continuation_of':s0['ll']['order_id'],'example':s0['ll']['example'],'product_attempt_token_reservation':s0['ll']['product_attempt_token_reservation']},'hal':{'request_id':halreq,'order_id':haloid,'tenant_scope':tenant,'depends_on_verified_ll':oid,'example':s0['hal']['example']},'functional_gates_blocking':True,'advisory_continue':False,'safety_scope':'ASPICE_ONLY; safety NOT_ASSESSED','capability':'EXPERIMENT_NOT_QUALIFIED','at':utc_now()}
 roles={}
 for role in [f'swe{i}-{r}' for i in range(1,7) for r in ('author','inspector')]+['release-manager','afo-recovery-planner','afo-factory-maintainer']:
  roles[role]=[]
  for mode in ('tool','unconstrained','json_schema','json_object'):
   for sampling in ({'seed':None,'temperature':None,'top_p':None},{'seed':1,'temperature':0.2,'top_p':None},{'seed':1,'temperature':0,'top_p':None},{'seed':None,'temperature':0,'top_p':None}):
    identity={'role':role,'model_digest':s0['model_digest'],'precision':'Q8_0','reasoning':'xhigh','schema_mode':mode,'adapter_revision':REV,'context_tokens':262144,'sampling':sampling,'task_class':'PRODUCT_ROLE_EXPERIMENT' if role.startswith('swe') or role=='release-manager' else 'MAINTENANCE_ROLE_EXPERIMENT' if role=='afo-factory-maintainer' else 'PRODUCT_DIAGNOSIS_EXPERIMENT'}
    key(identity);roles[role].append(identity)
 trial={'schema':'forge-c/product-role-trial/1','qualification_only':True,'source_revision':REV,'profile':scope['profile'],'profile_sha256':scope['profile_sha256'],'model':scope['model'],'roles':roles,'order_ids':[oid,haloid],'deadline_epoch':scope['deadline_epoch'],'authorization_ref':roleauth,'context_allocation_ref':{'path':str(OLD/'allocation.json'),'sha256':sha256_file(OLD/'allocation.json')}}
 ref={'path':f'afo/product-role-trials/{digest(trial)}.json','sha256':digest(trial)}
 def grant(aid,runbook,actions):
  g={'schema_version':'1.0','authorization_id':aid,'approver':'jefferson','approval_evidence_ref':'owner-standing-verified-qwen-continuation:'+digest(scope),'issued_utc':utc_now(),'expires_utc':scope['deadline_utc'],'policy_sha256':scope['policy_sha256'],'mode':'PILOT','allowed_actions':actions,'scope':{'order_ids':[llreq,halreq],'driver_classes':['LL','HAL'],'models':[scope['model']],'service_actions':['pause','drain','resume','shutdown']},'signature_ref':aid+'.sig','signed_runbook_ref':runbook};assert not authz.schema_errors(g);return g
 grants={'primary':grant(primary,'factory-revision:'+REV,['submit_workorder','launch_workorder','reconcile_run','recover_workorder','finalize_blocked','dead_letter','notify']),'roles':grant(roleauth,'qualification-product-014:'+digest(trial),['recover_workorder'])}
 launch=json.loads((OLD/'launch.json').read_text());launch.update(approved_factory_revision=REV,product_role_trial=ref,scope_sha256=digest(scope))
 raw=json.dumps(launch,sort_keys=True,separators=(',',':')).encode();launchref='.evidence-tmp/aspice-rcc-context-fixed-20261030-v1/ll-launch.json'
 env=json.loads((OLD/'envelope.json').read_text());env.update(request_id=llreq,git_revision=REV,manifest_sha256=__import__('hashlib').sha256(raw).hexdigest(),input_manifest_ref=launchref,authorization_ref=primary,submitted_utc=utc_now(),target='Full RCC LL SWE.1-SWE.6 with independently verified Qwen context repair')
 contracts.require('work-order',env)
 entry={'order_id':oid,'continuation_of':scope['ll']['continuation_of'],'envelope':env,'mission':{'mission_id':scope['mission_id'],'lineage':snap['lineage'],'limits':snap['limits'],'authorization_ref':snap['authorization_ref'],'request':{'order_id':llreq,'driver_class':'LL','model':scope['model']}}}
 O.mkdir(mode=0o700)
 for name,doc in {'scope.json':scope,'all-missions-before.json':histories,'proposed-policy.json':proposed,'trial.json':trial,'trial-ref.json':ref,'envelope.json':env,'entry.json':entry,'owner-approval.json':{'scope_sha256':digest(scope),'standing_signing_delegation':scope['standing_signing_delegation'],'source_activation_requires_exact_local_native_tests':True,'no_new_deadline_or_mission_limits':True,'at':utc_now()}}.items():immutable_json(O/name,doc)
 immutable_bytes(O/'proposed-policy.yaml',yaml.safe_dump(proposed,sort_keys=False).encode());immutable_bytes(O/'launch.json',raw);immutable_bytes(O/'allowed-signers',authz.ALLOWED_SIGNERS.read_bytes())
 for label,g in grants.items():immutable_json(O/(label+'-authorization.json'),g);immutable_bytes(O/(label+'-authorization-message.bin'),authz.message(g))
 print(json.dumps({'status':'EXACT_UNSIGNED_PRODUCT_CONTINUATION_PREPARED','scope_sha256':digest(scope),'source_revision':REV,'ll_order':oid,'hal_order':haloid,'configurations_per_role':16,'expires_utc':scope['deadline_utc'],'mission_limits_unchanged':True,'model_requests':0}))
