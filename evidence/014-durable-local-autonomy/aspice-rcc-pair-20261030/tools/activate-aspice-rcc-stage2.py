"""Resume model-free supervision and the single provider; intake waits for separate signed amendments."""
from pathlib import Path
import json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/aspice-rcc-pair-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations,policy
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import digest,immutable_json
from forge_factory.lrtx import stack
from forge_factory.common import utc_now
s=json.loads((O/'scope.json').read_text());assert digest(s)=='3e60ba7507f085996b6ae838878a37f4bf5ae2d246fe4d4573c8ed137e519b47'
assert time.time()<s['deadline_epoch']
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==s['source_revision']
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
S=Store();I=operations.Intent();L=MissionLedger(S);settings=stack.settings(s['profile'])
assert os.environ['FORGE_OPERATIONS_PROFILE']==s['profile'] and settings['profile']['_sha256']==s['profile_sha256']
before=json.loads((O/'all-missions-before.json').read_text())
with I.lock():
 assert I.read()['mode']=='PAUSED' and I.read()['epoch']==49
 assert not Executions(S).pending()
 for mid,snap in before.items():assert L.snapshot(mid)==snap
 eff=policy.load(log=False);assert eff.mode=='PILOT' and eff.sha256==s['policy_sha256'],eff.issues
 (P/'fabro/settings.toml').write_text(stack.fabro_config(settings))
resumed=operations.synchronize(S,'resume',str(os.getuid()),'Delegated exact ASPICE scope to08:11:56UTC; supervision active, signed RCC capacity/time and role admission still pending',expected_epoch=49,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
assert resumed['epoch']==50
health=stack.start(settings,recovery=True)
for _ in range(6):
 if all(health['health'].get(k) is True for k in ('fabro','gateway','ollama','llama_server')):break
 time.sleep(5);health=stack.start(settings,recovery=True)
assert all(health['health'].get(k) is True for k in ('fabro','gateway','ollama','llama_server')),health['health']
with I.lock():
 assert I.read()['mode']=='RUNNING' and I.read()['epoch']==50
 assert not Executions(S).pending()
 for mid,snap in before.items():assert L.snapshot(mid)==snap
 subprocess.run(['systemctl','--user','--no-block','start',operations.UNIT,'forge-afo-watchdog-014-omniverse2.timer'],check=True,timeout=20)
 immutable_json(O/'activation.json',{'status':'SUPERVISION_AND_PROFILE_ACTIVE_INTAKE_NOT_STARTED','source_revision':s['source_revision'],
  'operator_epoch':50,'deadline_utc':s['deadline_utc'],'history_preserved':True,
  'health':health['health'],'provider_instance':health['serving_instance'],'model_requests':0,'at':utc_now()})
print((O/'activation.json').read_text())
