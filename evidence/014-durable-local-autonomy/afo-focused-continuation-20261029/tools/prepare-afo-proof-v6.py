"""Prepare exact owner-authorized maintenance activation records; no service/model side effect."""
from pathlib import Path
from datetime import datetime, timezone
import copy, json, os, subprocess, sys, time
import yaml

P=Path('/mnt/data/forge-c/production-local-014'); R=P/'repo'
Q=P/'deployment/qualification-focused-maintenance-c1f1378-v2/repo'
O=P/'deployment/afo-repair-live-20261029-v6'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.afo import authz, contracts, operations, policy
from forge_factory.afo.queue import Store, order_id_for
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import canonical, digest, immutable_json, immutable_bytes
from forge_factory.lrtx.profile import load
from forge_factory.common import sha256_file, utc_now

S=Store(); I=operations.Intent(); L=MissionLedger(S)
assert I.read()['mode']=='RUNNING' and I.read()['epoch']==44 and not I.read()['effective_stop']
assert not Executions(S).pending()
with S.tx() as c:
    assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
    assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
    mids=[r[0] for r in c.execute('SELECT mission_id FROM afo_missions')]
    oldpolicy=yaml.safe_load(Path(os.environ['FORGE_AFO_POLICY']).read_text())
mid='F014-IDR-M1-HIGH-20261028'; before=L.snapshot(mid)
assert (before['attempts'],before['requests'],before['tools'],before['charged_tokens'])==(4,407,596,404131072)
source='c1f1378733af388b50ba1d6e5de37c16f3c0a9ee'; base='9b4c390e1605d11c4865bdeea382df74a0078692'
def git(repo,*args):return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()
assert git(R,'rev-parse','HEAD')=='92c49a6adde181737af19bb32a5efbd2130e9cd4' and not git(R,'status','--porcelain')
assert git(Q,'rev-parse','HEAD')==source and not git(Q,'status','--porcelain')
prof=load('local-rtx-v2-omniverse2-q38-afo-max-mtp',directory=Q/'config/factory/profiles'); model=prof['models']['default']
primary='AUTH-014-AFO-FOCUSED-C1F1378-20261029-V6'
timeauth='AUTH-014-AFO-REPAIR-TIME-20261029-V2'
roles='AUTH-014-AFO-FOCUSED-ROLE-20261029-V6'
request='f014-afo-mcp-root-repair-20261029-v6'; tenant='f014-idr-m1-20261028'; oid=order_id_for(tenant,request)
issued=utc_now(); deadline=int(time.time())+14400
expiry=datetime.fromtimestamp(deadline,timezone.utc).isoformat().replace('+00:00','Z')
proposed=copy.deepcopy(oldpolicy);proposed['authorization_ref']=primary
proposed['budgets'].update(max_recovery_model_calls_per_order=1,max_model_tokens_per_order=1000000,
    max_recovery_wall_seconds=14400,max_order_wall_seconds=14400)
assert not policy.schema_errors(proposed),policy.schema_errors(proposed)
assert not policy.floor_violations(proposed),policy.floor_violations(proposed)
polsha=digest(proposed)
scope={'schema':'forge-c/afo-maintenance-activation/1','trial_id':'F014-AFO-MCP-ROOT-REPAIR-20261029',
 'owner_instruction':'make afo workable on qwen model and then run again the complete aspice LL and HAL pipeline examples and check if qwen is able to run completely, identify issues, solve them and run again until the run is clean',
 'standing_signing_delegation':'always approve it for now on automatically',
 'window_seconds':int(deadline-time.time()),'deadline_epoch':deadline,'deadline_utc':expiry,'issued_utc':issued,
 'source_revision':source,'repair_baseline_revision':base,'profile':prof['id'],'profile_sha256':prof['_sha256'],
 'model':model,'model_digest':prof['models']['allowed'][model]['digest'],'precision':'Q8_0',
 'reasoning':'xhigh','mtp_draft':3,'context_tokens':262144,'role':'afo-factory-maintainer',
 'role_job_tokens':1000000,'candidate_limit':1,'inference_slots':1,'verification_workers':1,
 'mission_id':mid,'mission_before':before,'mission_snapshot_sha256':digest(before),
 'continuation_of':'afo-f516373e837db572','request_id':request,'new_order_id':oid,
 'operator_preparation_epoch':44,'policy_before_sha256':digest(oldpolicy),'policy_sha256':polsha,
 'allowed_patch_paths':['factory/python/forge_factory/fabro/runconfig.py','factory/python/tests/afo_candidate/**'],
 'source_activation':'External owner-authorized activation of exact previously CPU-qualified controller; not model deployment authority',
 'enrolment':'Existing Store/Conductor neutral role-only maintenance qualification; no product launch outbox',
 'historical_failure_replay':True,'self_healing_result':'NOT_RUN','no_auto_candidate_deployment':True,
 'old_parent_settlement':'V5 is FAILED_PROTOCOL and QUIESCENT/RELEASED after capability refusal and no valid submission; wrapper BLOCKED at expired window; preserve all artifacts, failures and charges',
 'non_time_mission_limits_unchanged':True,'historical_counters_reset':False,
 'primary_authorization':primary,'time_authorization':timeauth,'deadline_changed':True,'previous_production_revision':'92c49a6adde181737af19bb32a5efbd2130e9cd4','previous_profile':prof['id'],'role_authorization':roles,
 'artifact_continuation':{'source_job_id':'afo-agent-97d070852addbf37acf1b7c9','source_native_run_id':'01M64TQWV0QAJ69YGBJSS2STN3','provenance_sha256':sha256_file(P/'deployment/afo-repair-live-20261029-v5/written-artifacts/provenance.json'),'independent_check_sha256':sha256_file(P/'deployment/afo-repair-live-20261029-v5/independent-unsubmitted-check/result.json'),'operator_authored_code':False,'seed_exact_files':True},
 'preparation_manifest_sha256':sha256_file(P/'deployment/afo-repair-trial-20261029-v2/preparation.json')}
scopesha=digest(scope)
time_doc={'schema':'forge-c/mission-deadline-extension/1','mission_id':mid,'snapshot_sha256':digest(before),'deadline_epoch':deadline,'authorization_ref':timeauth,'request':{'order_id':request,'driver_class':'LL','model':model},'reason':'Active owner goal requires Qwen-authored repair and complete ASPICE LL/HAL pipelines; standing signing delegation used for a disclosed fresh finite four-hour repair scope, no non-time refill'}
def grant(aid,runbook,actions):
    g={'schema_version':'1.0','authorization_id':aid,'approver':'jefferson',
      'approval_evidence_ref':'owner-afo-repair-resume-20261029:'+scopesha,'issued_utc':issued,'expires_utc':expiry,
      'policy_sha256':polsha,'mode':'PILOT','allowed_actions':actions,
      'scope':{'order_ids':[request],'driver_classes':['LL'],'models':[model],
               'service_actions':['pause','drain','resume','shutdown']},
      'signature_ref':aid+'.sig','signed_runbook_ref':runbook}
    assert not authz.schema_errors(g),authz.schema_errors(g)
    return g
pgrant=grant(primary,'qualification-014:'+scopesha,
 ['submit_workorder','launch_workorder','reconcile_run','recover_workorder','finalize_blocked','dead_letter','notify'])

tgrant=grant(timeauth,'mission-deadline-extension-014:'+digest(time_doc),['recover_workorder'])
O.mkdir(mode=0o700)
for name,doc in {'scope.json':scope,'policy.json':proposed,'mission-before.json':before,
 'all-missions-before.json':{m:L.snapshot(m) for m in mids},
 'primary-authorization.json':pgrant,'time-authorization.json':tgrant,'deadline-extension.json':time_doc}.items():immutable_json(O/name,doc)
immutable_bytes(O/'proposed-policy.yaml',yaml.safe_dump(proposed,sort_keys=False).encode())
for label,g in (('primary',pgrant),('time',tgrant)):immutable_bytes(O/(label+'-authorization-message.bin'),authz.message(g))
immutable_bytes(O/'allowed-signers',authz.ALLOWED_SIGNERS.read_bytes())
immutable_json(O/'owner-approval.json',{'scope_sha256':scopesha,'owner_answer':scope['owner_instruction'],
 'standing_signing_delegation':scope['standing_signing_delegation'],'recorded_utc':utc_now(),
 'interpretation':'Standing owner delegation used for active broader goal: one focused Qwen-authored repair continuation, exact CPU-qualified source, explicitly disclosed prospective four-hour window and append-only deadline extension; no non-time/history refill; LL/HAL execution remains subsequent work'})
print(json.dumps({'status':'EXACT_UNSIGNED_ACTIVATION_PREPARED','scope_sha256':scopesha,'order_id':oid,
 'deadline_utc':expiry,'source_revision':source,'model_requests':0}),flush=True)
