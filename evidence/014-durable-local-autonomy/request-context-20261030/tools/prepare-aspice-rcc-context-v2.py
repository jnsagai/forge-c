"""Prepare finite strict-ASPICE LL/HAL continuation; no live mutation or inference."""
from pathlib import Path
import copy,hashlib,json,os,subprocess,sys,time
from datetime import datetime
import yaml
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo'
O=P/'deployment/aspice-rcc-context-20261030-v2'
Q=P/'deployment/qualification-request-context-20dccfcb-epoch105-v1/repo'
REV='20dccfcbd9ecea639d1d0b0a80deb9a8d920af71'
PROFILE='local-rtx-v2-omniverse2-q38-aspice-medium-author-xhigh-inspector'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:k,v=line.split('=',1);os.environ[k]=v
os.environ['FORGE_REPO_ROOT']=str(Q);sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.afo import authz,policy,operations,contracts
from forge_factory.afo.queue import ReadSnapshot,order_id_for
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.common import utc_now,sha256_file
from forge_factory.lrtx import profile,stack
from forge_factory.lrtx.role_capability import key
proof=json.loads((Q.parent/'provenance.json').read_text())
assert proof['source_revision']==REV and proof['pytest_exit_code']==0 and proof['summary']=={'tests':492,'failures':0,'errors':0,'skipped':0}
assert proof['source_clean_before'] and proof['source_clean_after'] and proof['model_requests']==0
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()=='7fbefc40e0912e15aabeb70ca6b85932085b1b27'
for root in (R,Q):assert not subprocess.check_output(['git','-C',str(root),'status','--porcelain'])
assert operations.Intent().read()['mode']=='PAUSED' and operations.Intent().read()['epoch']==105
prof=profile.load(PROFILE);assert not prof.get('development_execution_policy') and not prof.get('safec') and prof['structured']['advisory_continue'] is False
assert prof['work_order_purpose']=='ASPICE_ONLY'
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as S:
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  mids=[r[0] for r in c.execute('SELECT mission_id FROM afo_missions')]
 histories={mid:MissionLedger(S).snapshot(mid) for mid in mids};snap=histories['F014-NIGHT-20261027-RCC']
 assert S.order('afo-c9331219520d5237')
prior=yaml.safe_load(Path(os.environ['FORGE_AFO_POLICY']).read_text());proposed=copy.deepcopy(prior)
primary='AUTH-014-ASPICE-CONTEXT-20261030-V2';roleauth='AUTH-014-ASPICE-CONTEXT-ROLES-20261030-V2';timeauth=snap['authorization_ref']
proposed['authorization_ref']=primary
assert not policy.schema_errors(proposed) and not policy.floor_violations(proposed)
llreq='f014-aspice-rcc-ll-context-20261030-v2';halreq='f014-aspice-rcc-hal-context-20261030-v2';tenant='f014-night-20261027'
oid=order_id_for(tenant,llreq);haloid=order_id_for(tenant,halreq)
expiry='2026-10-30T19:40:00Z';deadline=datetime.fromisoformat(expiry.replace('Z','+00:00')).timestamp()
assert time.time()<snap['limits']['deadline']==deadline<time.time()+28800
allocation=P/'deployment/aspice-rcc-pair-20261030-v1/allocation.json';assert allocation.is_file()
scope={'schema':'forge-c/source-bound-product-continuation/1','source_revision':REV,'previous_production_revision':'7fbefc40e0912e15aabeb70ca6b85932085b1b27',
 'profile':PROFILE,'profile_sha256':prof['_sha256'],'previous_profile':os.environ['FORGE_LRTX_PROFILE'],'model':'qwen3.8:27b-q8_0',
 'model_digest':prof['models']['allowed']['qwen3.8:27b-q8_0']['digest'],'precision':'Q8_0','reasoning':'medium','reasoning_role_overrides':{f'swe{n}-inspector':'xhigh' for n in range(1,7)},'mtp_draft':3,'context_tokens':262144,'inference_slots':1,'verification_workers':1,
 'mission_id':snap['mission_id'],'mission_before':snap,'policy_before_sha256':digest(prior),'policy_sha256':digest(proposed),
 'primary_authorization':primary,'role_authorization':roleauth,'time_authorization':timeauth,
 'deadline_epoch':deadline,'deadline_utc':expiry,'deadline_changed':False,'previous_deadline':snap['limits']['deadline'],
 'non_time_limits_changed':False,'historical_counters_reset':False,'operator_preparation_epoch':105,
 'standing_signing_delegation':'always approve it for now on automatically',
 'owner_instruction':'Continue owner-approved Qwen AFO goal: correct observed1800s watchdog timeout, whole primary evidence loading and native serialized context measurement; medium authors/xhigh inspectors, same19:40UTC deadline and all RCC charges retained','visit_time_s':600,'inspection_max_source_chars':1048576,'native_request_measurement':'native_template_plus_serialized','partial_author_reuse':'NORMAL_RESUME_ONLY_CURRENT_SCHEMA_AND_TASK_VALIDATOR_NOT_PHASE_PASS',
 'll':{'request_id':llreq,'order_id':oid,'tenant_scope':tenant,'continuation_of':'afo-c9331219520d5237','example':'examples/0002a-arm_55_rcc_ll','product_attempt_token_reservation':1000000000},
 'hal':{'request_id':halreq,'order_id':haloid,'tenant_scope':tenant,'depends_on_generated_ll':oid,'example':'examples/0002b-arm_55_rcc_hal','upstream_quality':'INDEPENDENTLY_VERIFIED_LL_REQUIRED'},
 'functional_gates_blocking':True,'advisory_continue':False,'quality_findings_retained':True,'safety_scope':'ASPICE-only engineering; no safety assurance or assessed ASPICE compliance claim','demonstration_only':False,
 'capability':'EXPERIMENT_NOT_QUALIFIED','native_qualification_ref':{'path':str(Q.parent/'provenance.json'),'sha256':sha256_file(Q.parent/'provenance.json')},'at':utc_now()}
roles={}
for role in [f'swe{i}-{r}' for i in range(1,7) for r in ('author','inspector')]+['release-manager','afo-recovery-planner','afo-factory-maintainer']:
 roles[role]=[]
 for mode in ('tool','unconstrained','json_schema','json_object'):
  for sampling in ({'seed':None,'temperature':None,'top_p':None},{'seed':1,'temperature':0.2,'top_p':None},{'seed':1,'temperature':0,'top_p':None},{'seed':None,'temperature':0,'top_p':None}):
   identity={'role':role,'model_digest':scope['model_digest'],'precision':'Q8_0','reasoning':('xhigh' if role.endswith('-inspector') else 'medium'),'schema_mode':mode,'adapter_revision':REV,'context_tokens':262144,'sampling':sampling,'task_class':'PRODUCT_ROLE_EXPERIMENT' if role.startswith('swe') or role=='release-manager' else 'MAINTENANCE_ROLE_EXPERIMENT' if role=='afo-factory-maintainer' else 'two-step-diagnosis'}
   key(identity);roles[role].append(identity)
trial={'schema':'forge-c/product-role-trial/1','qualification_only':True,'source_revision':REV,'profile':PROFILE,'profile_sha256':prof['_sha256'],'model':scope['model'],'roles':roles,'order_ids':[oid,haloid],'deadline_epoch':deadline,'authorization_ref':roleauth,'context_allocation_ref':{'path':str(allocation),'sha256':sha256_file(allocation)}}
ref={'path':f'afo/product-role-trials/{digest(trial)}.json','sha256':digest(trial)}
def grant(aid,runbook,actions):
 g={'schema_version':'1.0','authorization_id':aid,'approver':'jefferson','approval_evidence_ref':'owner-aspice-stepwise-20261030:'+digest(scope),'issued_utc':utc_now(),'expires_utc':expiry,'policy_sha256':scope['policy_sha256'],'mode':'PILOT','allowed_actions':actions,
 'scope':{'order_ids':[llreq,halreq],'driver_classes':['LL','HAL'],'models':[scope['model']],'service_actions':['pause','drain','resume','shutdown']},'signature_ref':aid+'.sig','signed_runbook_ref':runbook}
 assert not authz.schema_errors(g);return g
grants={'primary':grant(primary,'factory-revision:'+REV,['submit_workorder','launch_workorder','reconcile_run','recover_workorder','finalize_blocked','dead_letter','notify']),
 'roles':grant(roleauth,'qualification-product-014:'+digest(trial),['recover_workorder'])}
launch=json.loads((P/'deployment/qm-rcc-launch-ready-20261030-v1/launch.json').read_text())
launch.update(resume_from='WO-AFO-c9331219520d5237-a1',profile=PROFILE,purpose='ASPICE_ONLY',advisory_continue=False,functional_gates_blocking=True,approved_factory_revision=REV,product_role_trial=ref,scope_sha256=digest(scope))
raw=json.dumps(launch,sort_keys=True,separators=(',',':')).encode()
env=json.loads((P/'deployment/qm-rcc-launch-ready-20261030-v1/envelope.json').read_text())
env.update(deadline_utc=expiry,request_id=llreq,git_revision=REV,manifest_sha256=hashlib.sha256(raw).hexdigest(),input_manifest_ref='.evidence-tmp/aspice-rcc-context-20261030-v2/ll-launch.json',authorization_ref=primary,submitted_utc=utc_now(),target='Complete RCC LL SWE.1-SWE.6 with blocking functional gates and existing AFO stepwise recovery; HAL depends on verified generated LL')
contracts.require('work-order',env)
entry={'order_id':oid,'continuation_of':scope['ll']['continuation_of'],'envelope':env,'mission':{'mission_id':snap['mission_id'],'lineage':snap['lineage'],'limits':{**snap['limits'],'deadline':deadline},'authorization_ref':timeauth,'admission_authorization_ref':primary,'request':{'order_id':llreq,'driver_class':'LL','model':scope['model']}}}
O.mkdir(mode=0o700)
for name,doc in {'scope.json':scope,'all-missions-before.json':histories,'proposed-policy.json':proposed,'trial.json':trial,'trial-ref.json':ref,'envelope.json':env,'entry.json':entry,'owner-approval.json':{'scope_sha256':digest(scope),'standing_signing_delegation':scope['standing_signing_delegation'],'existing_time_window_unchanged':True,'all_non_time_caps_and_charges_preserved':True,'activation_requires_native492_proof':True,'at':utc_now()}}.items():immutable_json(O/name,doc)
immutable_bytes(O/'proposed-policy.yaml',yaml.safe_dump(proposed,sort_keys=False).encode());immutable_bytes(O/'launch.json',raw);immutable_bytes(O/'allowed-signers',authz.ALLOWED_SIGNERS.read_bytes())
for label,g in grants.items():immutable_json(O/(label+'-authorization.json'),g);immutable_bytes(O/(label+'-authorization-message.bin'),authz.message(g))
print(json.dumps({'status':'ROLE_SPLIT_ASPICE_PAIR_PREPARED_UNSIGNED','scope_sha256':digest(scope),'ll_order':oid,'hal_order':haloid,'deadline_utc':expiry,'source_revision':REV,'historical_reset':False,'model_requests':0}))

