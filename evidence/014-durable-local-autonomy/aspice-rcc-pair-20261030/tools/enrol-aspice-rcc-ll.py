"""Enroll the one exact preapproved same-lineage LL order; Conductor alone launches."""
from pathlib import Path
import json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/aspice-rcc-pair-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import authz,operations,policy
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.overnight import provision_order
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.lrtx import stack
from forge_factory.common import utc_now,sha256_file
s=json.loads((O/'scope.json').read_text());assert digest(s)=='3e60ba7507f085996b6ae838878a37f4bf5ae2d246fe4d4573c8ed137e519b47'
assert time.time()<s['deadline_epoch']
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==s['source_revision']
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
S=Store();I=operations.Intent();L=MissionLedger(S)
with I.lock():
 assert I.read()['mode']=='RUNNING' and I.read()['epoch']==50
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
 settings=stack.settings(s['profile']);assert stack.serving_instance(settings)==json.loads((O/'allocation.json').read_text())['provider_instance']
 eff=policy.load(log=False);assert eff.mode=='PILOT' and eff.sha256==s['policy_sha256']
 initial=json.loads((O/'initial-request-preflight.json').read_text())
 assert initial['status']=='PASS_INITIAL_SWE1_GROUP_CONTEXT_ONLY' and initial['source_revision']==s['source_revision'] and not initial['missing_sections']
 assert initial['maximum_conservative_reservation']<=262144 and initial['groups']==6 and initial['inventory_items']==22
 grant=json.loads((O/'roles-authorization.json').read_text())
 assert authz.signature_valid(grant,O/'roles-authorization-message.bin.sig',authz.ALLOWED_SIGNERS)
 immutable_json(authz.AUTH_DIR/(grant['authorization_id']+'.json'),grant)
 immutable_bytes(authz.AUTH_DIR/grant['signature_ref'],(O/'roles-authorization-message.bin.sig').read_bytes())
 trial=json.loads((O/'trial.json').read_text());ref=json.loads((O/'trial-ref.json').read_text());assert digest(trial)==ref['sha256']
 immutable_json(P/'state'/ref['path'],trial)
 entry=json.loads((O/'entry.json').read_text());envelope=entry['envelope']
 immutable_bytes(R/envelope['input_manifest_ref'],(O/'launch.json').read_bytes())
 assert sha256_file(R/envelope['input_manifest_ref'])==envelope['manifest_sha256']
 before=L.snapshot(s['mission_id']);assert before['limits']=={**s['new_non_time_limits'],'deadline':s['deadline_epoch']}
 provision_order(S,entry,eff,s['deadline_epoch'])
 assert L.for_order(entry['order_id'])==s['mission_id'] and L.snapshot(s['mission_id'])==before
 immutable_json(O/'intake.json',{'status':'ENROLLED_CONDUCTOR_OWNS_EXECUTION','order_id':entry['order_id'],
  'mission_id':s['mission_id'],'source_revision':s['source_revision'],'operator_epoch':50,
  'deadline_utc':s['deadline_utc'],'spent_counters_preserved_before_dispatch':True,
  'initial_groups':6,'inventory_items':22,'HAL':'NOT_SUBMITTED_DEPENDS_ON_VERIFIED_LL',
  'capability':'EXPERIMENT_NOT_QUALIFIED','product_result':'NOT_RUN','model_requests_by_enrolment':0,'at':utc_now()})
print((O/'intake.json').read_text())
