"""Prepare exact finite owner-delegated scope, without signing, activation, intake or inference."""
from pathlib import Path
from datetime import datetime, timezone
import copy,json,os,subprocess,sys,time
import yaml
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo'
Q=P/'deployment/qualification-mission-capacity-b713e35-v2/repo'
O=P/'deployment/aspice-rcc-pair-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
os.environ['FORGE_REPO_ROOT']=str(Q)
sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.afo import authz,operations,policy
from forge_factory.afo.queue import ReadSnapshot,order_id_for
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.lrtx.profile import load
from forge_factory.common import utc_now
source='b713e354b5c50744c549b1a9cada491c3ca017bd'
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()=='f9e7f54b1838be2560d00117c1725f8d1d74d4c8'
assert subprocess.check_output(['git','-C',str(Q),'rev-parse','HEAD'],text=True).strip()==source
assert not subprocess.check_output(['git','-C',str(Q),'status','--porcelain'])
intent=operations.Intent().read();assert intent['mode']=='RUNNING' and intent['epoch']==48
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as S:
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  mids=[r[0] for r in c.execute('SELECT mission_id FROM afo_missions')]
 histories={mid:MissionLedger(S).snapshot(mid) for mid in mids}
 old=S.order('afo-94956895bdeb7dd7');oldenv=json.loads(old['envelope'])
 workloads=[]
 for row in S.orders():
  launch=R/row['input_manifest_ref']
  try:d=json.loads(launch.read_text())
  except (OSError,ValueError):continue
  workloads.append({'order_id':row['order_id'],'state':row['state'],'example':d.get('example'),
                    'mission_id':MissionLedger(S).for_order(row['order_id'])})
before=histories['F014-NIGHT-20261027-RCC']
assert before['charged_tokens']==86000 and before['attempts']==2 and not before['unbounded_historical_usage']
assert not any(x['example']=='examples/0002b-arm_55_rcc_hal' for x in workloads),'RECONCILE_EXISTING_HAL_LINEAGE_FIRST'
prof=load('local-rtx-v2-omniverse2-q38-aspice-max-mtp');model=prof['models']['default']
primary='AUTH-014-ASPICE-RCC-B713E35-20261030-V1'
request='f014-rcc-ll-aspice-20261030-v1';halrequest='f014-rcc-hal-aspice-20261030-v1'
oid=order_id_for(oldenv['tenant_scope'],request);haloid=order_id_for(oldenv['tenant_scope'],halrequest)
oldpolicy=yaml.safe_load(Path(os.environ['FORGE_AFO_POLICY']).read_text())
proposed=copy.deepcopy(oldpolicy);proposed['authorization_ref']=primary
proposed['budgets'].update(max_order_attempts=1000,max_recovery_model_calls_per_order=1000,
 max_model_tokens_per_order=100000000000,max_inference_requests_per_order=100000,
 max_tool_calls_per_order=1000000,max_order_wall_seconds=28800,max_recovery_wall_seconds=21600)
proposed['maintenance']['max_retained_reworks']=2
proposed['engineering']['allow_scoped_product_draft_rework']=True
assert model in proposed['engineering']['allowed_model_profiles']
assert not policy.schema_errors(proposed),policy.schema_errors(proposed)
assert not policy.floor_violations(proposed),policy.floor_violations(proposed)
issued=utc_now();deadline=int(time.time())+28800;expiry=datetime.fromtimestamp(deadline,timezone.utc).isoformat().replace('+00:00','Z')
caps=dict(max_attempts=1000,max_jobs=1000,max_requests=100000,max_tokens=100000000000,
          max_tools=1000000,max_corrections=before['limits']['max_corrections'])
scope={'schema':'forge-c/aspice-pair-owner-scope/1','source_revision':source,
 'previous_production_revision':'f9e7f54b1838be2560d00117c1725f8d1d74d4c8',
 'owner_instruction':'make afo workable on qwen model and then run again the complete aspice LL and HAL pipeline examples and check if qwen is able to run completely, identify issues, solve them and run again until the run is clean',
 'standing_signing_delegation':'always approve it for now on automatically',
 'issued_utc':issued,'deadline_epoch':deadline,'deadline_utc':expiry,'finite_window_seconds':28800,
 'operator_preparation_epoch':48,'profile':prof['id'],'profile_sha256':prof['_sha256'],
 'previous_profile':'local-rtx-v2-omniverse2-q38-afo-max-mtp','model':model,
 'model_digest':prof['models']['allowed'][model]['digest'],'precision':'Q8_0',
 'context_tokens':262144,'kv_precision':'f16','mtp_draft':3,'reasoning_effort':'xhigh',
 'inference_slots':1,'verification_workers':1,'purpose':'ASPICE_ONLY',
 'functional_gates_blocking':True,'same_model_independence_claim':False,
 'policy_before_sha256':digest(oldpolicy),'policy_sha256':digest(proposed),'primary_authorization':primary,
 'mission_id':before['mission_id'],'mission_before':before,'new_non_time_limits':caps,
 'time_amendment':'Separate exact signed document after activation; does not renew original grant',
 'capacity_amendment':'Separate exact signed snapshot-bound document; preserves all history and refuses exhausted non-time limits',
 'll':{'example':'examples/0002a-arm_55_rcc_ll','request_id':request,'order_id':oid,
       'tenant_scope':oldenv['tenant_scope'],'continuation_of':old['order_id'],'product_attempt_token_reservation':1000000000},
 'hal':{'example':'examples/0002b-arm_55_rcc_hal','request_id':halrequest,'order_id':haloid,
        'tenant_scope':oldenv['tenant_scope'],'dependency':'New independently verified LL output; no substitution',
        'mission_registration':'Only after qualifying real LL dependency; preserve any discovered historical HAL lineage'},
 'maintenance_max_retained_reworks':2,'engineering_authorship':'Qwen; external controller/bootstrap changes disclosed separately',
 'source_activation':'Exact qualified external source only; no automatic Qwen candidate deploy/merge',
 'runtime_qualification':'PENDING_NATIVE_RESULT','model_role_capability':'EXPERIMENT_ONLY_NOT_QUALIFIED',
 'LL_HAL_product_success':'NOT_RUN','learning_benefit':'NOT_PROVEN','operational_availability':'NOT_QUALIFIED'}
g={'schema_version':'1.0','authorization_id':primary,'approver':'jefferson',
 'approval_evidence_ref':'owner-standing-afo-aspice-20261030:'+digest(scope),'issued_utc':issued,'expires_utc':expiry,
 'policy_sha256':digest(proposed),'mode':'PILOT',
 'allowed_actions':['submit_workorder','launch_workorder','reconcile_run','recover_workorder','finalize_blocked','dead_letter','notify'],
 'scope':{'order_ids':[request,halrequest],'driver_classes':['LL','HAL'],'models':[model],
          'service_actions':['pause','drain','resume','shutdown']},
 'signature_ref':primary+'.sig','signed_runbook_ref':'factory-revision:'+source}
assert not authz.schema_errors(g),authz.schema_errors(g)
O.mkdir(mode=0o700)
for name,d in {'scope.json':scope,'policy.json':proposed,'primary-authorization.json':g,
 'all-missions-before.json':histories,'existing-workload-facts.json':workloads,
 'owner-approval.json':{'scope_sha256':digest(scope),'owner_answer':scope['owner_instruction'],
  'standing_signing_delegation':scope['standing_signing_delegation'],'recorded_utc':utc_now(),
  'interpretation':'Explicit finite prospective ASPICE LL then verified-dependent HAL scope using standing delegated signing; exact source and operator fencing, preserve historical mission charges and original grants; new separate signed non-time and time amendments, no exhausted mission reset'}}.items():immutable_json(O/name,d)
immutable_bytes(O/'proposed-policy.yaml',yaml.safe_dump(proposed,sort_keys=False).encode())
immutable_bytes(O/'primary-authorization-message.bin',authz.message(g))
immutable_bytes(O/'allowed-signers',authz.ALLOWED_SIGNERS.read_bytes())
print(json.dumps({'status':'UNSIGNED_SCOPE_PREPARED_NO_ACTIVATION','scope_sha256':digest(scope),'source_revision':source,
 'deadline_utc':expiry,'ll_order_id':oid,'model_requests':0}))
