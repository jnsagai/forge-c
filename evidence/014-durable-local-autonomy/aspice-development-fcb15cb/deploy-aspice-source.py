from pathlib import Path
import os,sys,json,subprocess,xml.etree.ElementTree as X
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';D=P/'deployment';O=D/'aspice-window-20261028'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#'):
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations
from forge_factory.afo.queue import Store
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.durable import immutable_json
from forge_factory.lrtx import stack,provider_process
S=Store();I=operations.Intent();scope=json.loads((O/'scope.json').read_text());candidate=scope['source_revision']
Q=D/'qualification-aspice-fcb15cb';inv=json.loads((Q/'invocation.json').read_text());suite=X.parse(Q/'tests.xml').getroot()[0]
assert inv['revision']==candidate and inv['exit_code']==0 and not inv['start_dirty'] and not inv['end_dirty']
assert int(suite.get('tests'))==100 and all(int(suite.get(x))==0 for x in ['errors','failures','skipped'])
def git(*args):return subprocess.check_output(['git','-C',str(R),*args],text=True).strip()
def histories():
 with S.tx() as c:mids=[r[0] for r in c.execute('SELECT mission_id FROM afo_missions')]
 return {m:MissionLedger(S).snapshot(m) for m in mids}
def quiet():
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
with I.lock():
 state=I.read();assert state['mode']=='DRAINING' and state['epoch']==14;quiet()
 assert git('rev-parse','HEAD')=='d7fa97e41f6e265e55737478379052db8d6bd859'
 assert not git('status','--porcelain')
 before=histories();immutable_json(O/'history-before-deployment.json',before)
paused=operations.synchronize(S,'pause',str(os.getuid()),'Deploy tested owner ASPICE-only engineering lane; original mission costs and quality checks retained',
 expected_epoch=14,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
assert paused['epoch']==15
units=['forge-afo-watchdog-014-omniverse2.timer','forge-afo-watchdog-014-omniverse2.service','forge-conductor-local-omniverse2.service','forge-qwen-golive-20261028.service']
for u in units:subprocess.run(['systemctl','--user','stop',u],check=True,timeout=45)
with I.lock():
 state=I.read();assert state['mode']=='PAUSED' and state['epoch']==15;quiet()
 immutable_json(O/'database-backup.json',S.backup(O/'conductor-before.sqlite3'))
 immutable_json(O/'services-before.json',json.loads((P/'run/services.json').read_text()))
 old=stack.settings('local-rtx-v2-omniverse2-q38-quality')
 proof=provider_process.stop(stack.serving_instance(old),fenced_effect=lambda effect:effect())
 assert proof;immutable_json(O/'old-provider-retirement.json',proof)
 immutable_json(O/'owned-services-stop.json',stack._stop(old,managed=True))
 projection=json.loads((P/'run/services.json').read_text())
 projection.pop('serving_instance',None);projection.pop('serving_holder',None)
 projection['engineering_source_revision']=candidate;stack._save_services(P,projection)
 subprocess.run(['git','-C',str(R),'fetch',str(D/'fcb15cb.bundle'),'HEAD'],check=True)
 subprocess.run(['git','-C',str(R),'merge','--ff-only',candidate],check=True)
 assert not git('status','--porcelain')
 # Units and host-side environment select the same prospective serving lifetime.
 files=[P/'state/afo/conductor.env']+[Path.home()/'.config/systemd/user'/u for u in [
  'forge-conductor-local-omniverse2.service','forge-afo-watchdog-014-omniverse2.service']]
 for index,path in enumerate(files):
  raw=path.read_bytes();(O/('environment-before-'+str(index))).write_bytes(raw)
  changed=raw.replace(b'local-rtx-v2-omniverse2-q38-quality',b'local-rtx-v2-omniverse2-q38-aspice');assert changed!=raw
  temp=path.with_name(path.name+'.aspice-next')
  fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb') as stream:stream.write(changed);stream.flush();os.fsync(stream.fileno())
  os.replace(temp,path)
 subprocess.run(['systemctl','--user','daemon-reload'],check=True,timeout=20)
 assert histories()==before
 result={'status':'TESTED_ASPICE_SOURCE_DEPLOYED_PAUSED','source_revision':candidate,'epoch':15,
 'native_tests':100,'native_failures':0,'model_calls_in_qualification':0,'historical_missions_unchanged':True}
 immutable_json(O/'source-deployment.json',result);print(json.dumps(result))
