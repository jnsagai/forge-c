"""Exact qualified source/profile transition, fenced against newer operator intent."""
from pathlib import Path
import json,os,signal,subprocess,sys,tempfile,time,xml.etree.ElementTree as ET
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';D=P/'deployment'
N=D/'qualification-mission-capacity-b713e35-v2';Q=N/'repo';O=D/'aspice-rcc-pair-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
os.environ['FORGE_REPO_ROOT']=str(Q);sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.afo import authz,operations,policy
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.common import utc_now
from forge_factory.lrtx import stack,provider_process,pidfd
s=json.loads((O/'scope.json').read_text())
assert digest(s)=='3e60ba7507f085996b6ae838878a37f4bf5ae2d246fe4d4573c8ed137e519b47'
assert json.loads((O/'owner-approval.json').read_text())['scope_sha256']==digest(s)
assert time.time()<s['deadline_epoch']
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
assert git(R,'rev-parse','HEAD')==s['previous_production_revision'] and not git(R,'status','--porcelain')
assert git(Q,'rev-parse','HEAD')==s['source_revision'] and not git(Q,'status','--porcelain')
p=json.loads((N/'provenance.json').read_text())
assert p['source_revision']==s['source_revision'] and p['pytest_exit_code']==0 and p['source_clean_before'] and p['source_clean_after']
suite=next(ET.parse(N/'scratch/pytest.xml').getroot().iter('testsuite'))
assert suite.get('tests')=='51' and all(suite.get(k)=='0' for k in ('failures','errors','skipped'))
prior=D/'qualification-maintenance-rework-8f21511-v2'
assert json.loads((prior/'provenance.json').read_text())['pytest_exit_code']==0
suite=next(ET.parse(prior/'scratch/pytest.xml').getroot().iter('testsuite'))
assert suite.get('tests')=='34' and all(suite.get(k)=='0' for k in ('failures','errors','skipped'))
g=json.loads((O/'primary-authorization.json').read_text())
assert authz.signature_valid(g,O/'primary-authorization-message.bin.sig',authz.ALLOWED_SIGNERS)
assert g['policy_sha256']==s['policy_sha256'] and g['expires_utc']==s['deadline_utc']
proposed=json.loads((O/'policy.json').read_text())
assert digest(proposed)==s['policy_sha256'] and not policy.schema_errors(proposed) and not policy.floor_violations(proposed)
S=Store();I=operations.Intent();L=MissionLedger(S)
def history():
 with S.tx() as c:mids=[row[0] for row in c.execute('SELECT mission_id FROM afo_missions')]
 return {mid:L.snapshot(mid) for mid in mids}
before=json.loads((O/'all-missions-before.json').read_text())
def quiet():
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
assert I.read()['mode']=='RUNNING' and I.read()['epoch']==48
quiet();assert history()==before
services=json.loads((P/'run/services.json').read_text())
provider=stack.serving_instance(stack.settings(s['previous_profile']))
immutable_json(O/'services-before.json',services)
operations.synchronize(S,'pause',str(os.getuid()),'Standing owner approval: qualified exact source and full ASPICE profile; preserve cumulative missions, finite08:11:56UTC scope',expected_epoch=48,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
def fenced(effect):
 with I.lock():
  assert I.read()['mode']=='PAUSED' and I.read()['epoch']==49
  quiet();return effect()
for unit in ('forge-qwen-mission-recorder.service','forge-afo-watchdog-014-omniverse2.timer','forge-afo-watchdog-014-omniverse2.service',operations.UNIT):
 fenced(lambda unit=unit:subprocess.run(['systemctl','--user','stop',unit],check=True,timeout=45))
fenced(lambda:immutable_json(O/'database-backup.json',S.backup(O/'conductor-before.sqlite3')))
proof=provider_process.stop(provider,fenced_effect=fenced);assert proof
immutable_json(O/'previous-provider-quiescence.json',proof)
pr=services['processes']['fabro'];pid=pr['pid'];expected=pr['identity']
def terminate_fabro():
 actual=stack.process_identity(pid)
 if actual is None:return
 assert actual==expected
 fd=pidfd.open_pid(pid)
 try:
  assert stack.process_identity(pid)==expected;pidfd.send_signal(fd,signal.SIGTERM)
 finally:os.close(fd)
fenced(terminate_fabro)
for _ in range(100):
 actual=stack.process_identity(pid)
 if actual is None or actual.get('state')=='Z' or actual.get('start_ticks')!=expected['start_ticks']:break
 time.sleep(.05)
else:raise RuntimeError('OLD_FABRO_NOT_QUIESCENT')
def atomic(path,raw):
 fd,name=tempfile.mkstemp(prefix='.aspice-next-',dir=path.parent)
 with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
 os.chmod(name,0o600);os.replace(name,path)
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def promote():
 assert provider_process.quiet(provider) and history()==before
 subprocess.run(['git','-C',str(R),'fetch',str(Q),'HEAD'],check=True,capture_output=True)
 subprocess.run(['git','-C',str(R),'merge','--ff-only',s['source_revision']],check=True,capture_output=True)
 assert git(R,'rev-parse','HEAD')==s['source_revision'] and not git(R,'status','--porcelain')
 current=json.loads((P/'run/services.json').read_text());assert current['serving_instance']==provider
 for key in ('serving_instance','serving_holder'):current.pop(key,None)
 current['processes']={k:v for k,v in current['processes'].items() if k not in ('ollama','gateway','llama_server','fabro')}
 stack._save_services(P,current)
 assert not authz.AUTH_DIR.is_relative_to(R) and not authz.AUTH_DIR.is_relative_to(Q)
 immutable_json(authz.AUTH_DIR/(g['authorization_id']+'.json'),g)
 immutable_bytes(authz.AUTH_DIR/g['signature_ref'],(O/'primary-authorization-message.bin.sig').read_bytes())
 target=Path(os.environ['FORGE_AFO_POLICY']);immutable_bytes(O/'policy-before.yaml',target.read_bytes())
 atomic(target,(O/'proposed-policy.yaml').read_bytes())
 envfile=P/'state/afo/conductor.env';raw=envfile.read_bytes()
 immutable_bytes(O/'conductor.env.before',raw);(O/'conductor.env.before').chmod(0o600)
 assert s['previous_profile'] in raw.decode()
 atomic(envfile,raw.decode().replace(s['previous_profile'],s['profile']).encode())
 for name in ('forge-conductor-local-omniverse2.service','forge-afo-watchdog-014-omniverse2.service'):
  unit=Path.home()/'.config/systemd/user'/name;raw=unit.read_bytes();immutable_bytes(O/(name+'.before'),raw)
  if s['previous_profile'] in raw.decode():atomic(unit,raw.decode().replace(s['previous_profile'],s['profile']).encode())
 subprocess.run(['systemctl','--user','daemon-reload'],check=True,timeout=20)
 assert history()==before
fenced(promote)
immutable_json(O/'stage1.json',{'status':'QUALIFIED_SOURCE_PROFILE_PREPARED_PAUSED','source_revision':s['source_revision'],
 'operator_epoch':49,'history_preserved':True,'model_requests':0,'at':utc_now()})
print((O/'stage1.json').read_text())
