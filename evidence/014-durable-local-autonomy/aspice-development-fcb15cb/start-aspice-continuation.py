from pathlib import Path
import os,sys,json,subprocess
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/aspice-window-20261028'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#'):
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations,policy,authz
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.durable import immutable_json,digest
from forge_factory.common import utc_now
scope=json.loads((O/'scope.json').read_text());p=json.loads((O/'launch-prerequisites.json').read_text())
assert p['status']=='PASS' and p['source_revision']==scope['source_revision']
assert p['profile_sha256']==scope['profile_sha256'] and p['generation_requests']==0
assert p['author_module']=='swe1' and p['inspector_module']=='review' and p['safec_execution'] is False
assert not p['missing_signed_trial_roles']
S=Store();I=operations.Intent()
with I.lock():
 state=I.read();assert state['mode']=='RUNNING' and state['epoch']==16
 assert MissionLedger(S).snapshot(scope['mission_id'])==scope['mission_before']
 eff=policy.load(log=False);assert eff.sha256==scope['policy_sha256']
 check=authz.find('PILOT',eff.sha256,ref=eff.get('authorization_ref'),action='launch_workorder',
 request={'order_id':scope['envelope']['request_id'],'driver_class':'LL','model':scope['envelope']['model_profile']})
 assert check.allow
 assert subprocess.check_output(['systemctl','--user','is-active','forge-aspice-expiry-20261028.timer'],text=True).strip()=='active'
 units=['forge-conductor-local-omniverse2.service','forge-afo-watchdog-014-omniverse2.timer','forge-qwen-golive-20261028.service']
 subprocess.run(['systemctl','--user','--no-block','start',*units],check=True,timeout=20)
 result={'status':'ASPICE_CONTINUATION_ADMISSION_STARTED','at':utc_now(),'source_revision':scope['source_revision'],
 'operator_epoch':16,'order_id':scope['order_id'],'mission_id':scope['mission_id'],'scope_sha256':digest(scope),
 'prior_charged_tokens':scope['mission_before']['charged_tokens'],'deadline_utc':scope['deadline_utc'],
 'native_preflight':'PASS','expiry_cleanup_timer':'active','services_start_requested':units,
 'native_or_product_success':'NOT_ESTABLISHED','safety_approval':None,'assessed_aspice_compliance':None}
 immutable_json(O/'admission-start.json',result);print(json.dumps(result))
