"""One finite signed LL intake; Conductor remains the sole dispatcher."""
from pathlib import Path
import json,os,sys,subprocess,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/aspice-rcc-context-20261030-v2'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import policy,operations
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.overnight import provision_order
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.common import sha256_file,utc_now
from forge_factory.lrtx import stack
s=json.loads((O/'scope.json').read_text());assert digest(s)=='b114da2cfa24ccf9a4e8e888386491defe9ef0879509cda9ad9285682c3fe237'
activation=json.loads((O/'activation.json').read_text());assert activation['source_revision']==s['source_revision'] and activation['operator_epoch']==106
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==s['source_revision']
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
S=Store();I=operations.Intent();L=MissionLedger(S)
with I.lock():
 now=I.read();assert now['mode']=='RUNNING' and now['epoch']==106 and time.time()<s['deadline_epoch'],'NEWER_OPERATOR_INTENT_PRESERVED'
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
 eff=policy.load(log=False);assert eff.mode=='PILOT' and eff.sha256==s['policy_sha256']
 assert stack.serving_instance(stack.settings(s['profile']))==activation['provider_instance']
 trial=json.loads((O/'trial.json').read_text());ref=json.loads((O/'trial-ref.json').read_text());assert digest(trial)==ref['sha256']
 assert {i['task_class'] for i in trial['roles']['afo-recovery-planner']}=={'two-step-diagnosis'}
 immutable_json(P/'state'/ref['path'],trial)
 entry=json.loads((O/'entry.json').read_text());env=entry['envelope']
 immutable_bytes(R/env['input_manifest_ref'],(O/'launch.json').read_bytes());assert sha256_file(R/env['input_manifest_ref'])==env['manifest_sha256']
 before=L.snapshot(s['mission_id']);assert before['limits']['deadline']==s['deadline_epoch']
 for k in ('attempts','jobs','requests','tools','corrections','charged_tokens','usage_unknown','unique_executions','unbounded_historical_usage'):assert before[k]==s['mission_before'][k]
 provision_order(S,entry,eff,s['deadline_epoch']);assert L.for_order(entry['order_id'])==s['mission_id'] and L.snapshot(s['mission_id'])==before
 immutable_json(O/'intake.json',{'status':'LL_ENROLLED_EXISTING_CONDUCTOR_OWNS_DISPATCH','order_id':entry['order_id'],'mission_id':s['mission_id'],'source_revision':s['source_revision'],'profile':s['profile'],'operator_epoch':106,'deadline_utc':s['deadline_utc'],'blocking_functional_gates':True,'history_counters_preserved_before_dispatch':True,'HAL':'NOT_SUBMITTED_REQUIRES_NEW_VERIFIED_LL','capability':'EXPERIMENT_NOT_QUALIFIED','model_requests_by_intake':0,'at':utc_now()})
print((O/'intake.json').read_text())

