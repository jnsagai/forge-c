"""Prepare/apply separately exact signed administrative amendments under existing owner delegation."""
from pathlib import Path
import json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/aspice-rcc-pair-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import authz,policy,operations,cli
from forge_factory.afo import mission_capacity as C,mission_deadline as D
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.common import utc_now
s=json.loads((O/'scope.json').read_text());assert digest(s)=='3e60ba7507f085996b6ae838878a37f4bf5ae2d246fe4d4573c8ed137e519b47'
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==s['source_revision']
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
assert time.time()<s['deadline_epoch'] and cli.operator_ok()
I=operations.Intent();assert I.read()['mode']=='RUNNING' and I.read()['epoch']==50
S=Store();assert not Executions(S).pending()
eff=policy.load(log=False);assert eff.mode=='PILOT' and eff.sha256==s['policy_sha256']
action,label=sys.argv[1:];assert action in ('prepare','apply') and label in ('capacity','time')
ledger=MissionLedger(S);snapshot=ledger.snapshot(s['mission_id'])
for k in ('attempts','jobs','requests','tools','corrections','charged_tokens','usage_unknown','unique_executions','unbounded_historical_usage'):
 assert snapshot[k]==s['mission_before'][k]
if action=='prepare':
 if label=='capacity':
  assert snapshot==s['mission_before']
  doc={'schema':C.SCHEMA,'mission_id':s['mission_id'],'snapshot_sha256':digest(snapshot),
       'limits':s['new_non_time_limits'],'operator_epoch':50,
       'authorization_ref':'AUTH-014-RCC-CAPACITY-20261030-V1',
       'request':{'order_id':s['ll']['request_id'],'driver_class':'LL','model':s['model']},
       'reason':'Owner explicitly requested extraordinary high finite limits; same RCC lineage, old charges and uncertainty, no exhausted mission reset'}
  runbook='mission-capacity-amendment-014:'+digest(doc)
 else:
  assert snapshot['capacity_amendments'] and all(snapshot['limits'][k]==v for k,v in s['new_non_time_limits'].items())
  doc={'schema':D.SCHEMA,'mission_id':s['mission_id'],'snapshot_sha256':digest(snapshot),
       'deadline_epoch':s['deadline_epoch'],'authorization_ref':'AUTH-014-RCC-TIME-20261030-V1',
       'request':{'order_id':s['ll']['request_id'],'driver_class':'LL','model':s['model']},
       'reason':'Disclosed finite prospective ASPICE RCC continuation through08:11:56UTC under standing owner delegation; original expired grants/deadlines and expenditure retained'}
  runbook='mission-deadline-extension-014:'+digest(doc)
 g={'schema_version':'1.0','authorization_id':doc['authorization_ref'],'approver':'jefferson',
    'approval_evidence_ref':'owner-standing-afo-aspice-20261030:'+digest(s),'issued_utc':utc_now(),
    'expires_utc':s['deadline_utc'],'policy_sha256':s['policy_sha256'],'mode':'PILOT',
    'allowed_actions':['recover_workorder'],
    'scope':{'order_ids':[s['ll']['request_id']],'driver_classes':['LL'],'models':[s['model']]},
    'signature_ref':doc['authorization_ref']+'.sig','signed_runbook_ref':runbook}
 assert not authz.schema_errors(g),authz.schema_errors(g)
 immutable_json(O/(label+'-document.json'),doc);immutable_json(O/(label+'-authorization.json'),g)
 immutable_bytes(O/(label+'-authorization-message.bin'),authz.message(g))
 print(json.dumps({'status':'EXACT_UNSIGNED_DOCUMENT_PREPARED','label':label,'document_sha256':digest(doc),'model_requests':0}))
else:
 doc=json.loads((O/(label+'-document.json')).read_text());g=json.loads((O/(label+'-authorization.json')).read_text())
 assert authz.signature_valid(g,O/(label+'-authorization-message.bin.sig'),authz.ALLOWED_SIGNERS)
 assert doc['mission_id']==s['mission_id'] and g['policy_sha256']==s['policy_sha256'] and g['expires_utc']==s['deadline_utc']
 immutable_json(authz.AUTH_DIR/(g['authorization_id']+'.json'),g)
 immutable_bytes(authz.AUTH_DIR/g['signature_ref'],(O/(label+'-authorization-message.bin.sig')).read_bytes())
 result=(C.amend if label=='capacity' else D.extend)(S,doc,eff)
 immutable_json(O/(label+'-receipt.json'),result)
 after=ledger.snapshot(s['mission_id']);immutable_json(O/('mission-after-'+label+'.json'),after)
 for k in ('attempts','jobs','requests','tools','corrections','charged_tokens','usage_unknown','unique_executions','unbounded_historical_usage'):
  assert after[k]==s['mission_before'][k]
 assert S.order(s['ll']['continuation_of'])['state']=='BLOCKED'
 print(json.dumps({'status':'EXACT_SIGNED_AMENDMENT_APPLIED','label':label,'receipt_sha256':digest(result),
  'spent_counters_preserved':True,'old_order_remains_blocked':True,'model_requests':0,'deadline':after['limits']['deadline']}))
