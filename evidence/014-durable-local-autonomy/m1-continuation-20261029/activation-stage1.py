"""Owner-approved exact f206e3a promotion; no inference or grant renewal beyond approved records."""
from pathlib import Path
import json,os,signal,subprocess,sys,time,xml.etree.ElementTree as ET
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';D=P/'deployment'
N=D/'qualification-independent-f206e3a';O=D/'idr-m1-f206e3a-20261029'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
os.environ['TMPDIR']=str(N/'tmp');sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import authz,operations
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import digest,immutable_json
from forge_factory.common import utc_now
from forge_factory.lrtx import stack,provider_process,pidfd
scope=json.loads((O/'scope.json').read_text());approval=json.loads((O/'owner-approval.json').read_text())
assert digest(scope)==approval['scope_sha256']=='61749a3c90d281f7f8bd7535d38e88c5e89cd0eb847fcadf7442cc8591d9d59b'
assert approval['owner_answer']=='Approve exact scope, signing and activation'
assert time.time()<scope['limits_after']['deadline']
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
assert git(R,'rev-parse','HEAD')==scope['previous_production_revision'] and not git(R,'status','--porcelain')
assert git(N/'repo','rev-parse','HEAD')==scope['source_revision'] and not git(N/'repo','status','--porcelain')
suite=ET.parse(N/'pytest-corrected.xml').getroot().find('testsuite')
assert suite.get('tests')=='84' and all(suite.get(k)=='0' for k in ('failures','errors','skipped'))
capture=json.loads((N/'role-context-preflight-high-v1/result.json').read_text())
assert capture['source_revision']==scope['source_revision'] and capture['native_nodes']==18 and not capture['halt'] and capture['model_generation_requests']==0
for label in ('primary','roles','time'):
 grant=json.loads((O/(label+'-authorization.json')).read_text())
 assert authz.signature_valid(grant,O/(label+'-authorization-message.bin.sig'),authz.ALLOWED_SIGNERS)
 assert grant['policy_sha256']==scope['policy_sha256'] and grant['expires_utc']==scope['deadline_utc']
S=Store();I=operations.Intent();L=MissionLedger(S)
def history():
 with S.tx() as c: mids=[r[0] for r in c.execute('SELECT mission_id FROM afo_missions')]
 return {mid:L.snapshot(mid) for mid in mids}
def quiet():
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
assert digest(L.snapshot(scope['mission_id']))==scope['mission_snapshot_sha256']
assert I.read()['mode']=='RUNNING' and I.read()['epoch']==24
quiet();immutable_json(O/'history-before.json',history())
services=json.loads((P/'run/services.json').read_text());immutable_json(O/'services-before.json',services)
provider=stack.serving_instance(stack.settings(scope['profile']))
paused=operations.synchronize(S,'pause',str(os.getuid()),'Owner approved exact f206e3a same-M1 Qwen continuation',expected_epoch=24,
 authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
assert paused['epoch']==25
def fenced(effect):
 with I.lock():
  state=I.read();assert state['mode']=='PAUSED' and state['epoch']==25
  quiet();return effect()
for unit in ('forge-afo-watchdog-014-omniverse2.timer','forge-afo-watchdog-014-omniverse2.service',
 'forge-conductor-local-omniverse2.service','forge-idr-m1-20261028.service'):
 fenced(lambda unit=unit:subprocess.run(['systemctl','--user','stop',unit],check=True,timeout=45))
fenced(lambda:immutable_json(O/'database-backup.json',S.backup(O/'conductor-before.sqlite3')))
proof=provider_process.stop(provider,fenced_effect=fenced);assert proof
immutable_json(O/'previous-provider-quiescence.json',proof)
pr=services['processes']['fabro'];pid=pr['pid'];expected=pr['identity']
def terminate():
 actual=stack.process_identity(pid)
 if actual is None:return
 assert actual==expected
 fd=pidfd.open_pid(pid)
 try:
  assert stack.process_identity(pid)==expected;pidfd.send_signal(fd,signal.SIGTERM)
 finally:os.close(fd)
fenced(terminate)
for _ in range(100):
 actual=stack.process_identity(pid)
 if actual is None or actual.get('start_ticks')!=expected['start_ticks']:break
 time.sleep(.05)
else:raise RuntimeError('PREVIOUS_FABRO_NOT_QUIESCENT')
def promote():
 assert provider_process.quiet(provider) and history()==json.loads((O/'history-before.json').read_text())
 subprocess.run(['git','-C',str(R),'fetch',str(N/'repo'),'HEAD'],check=True,capture_output=True)
 subprocess.run(['git','-C',str(R),'merge','--ff-only',scope['source_revision']],check=True,capture_output=True)
 assert not git(R,'status','--porcelain')
 current=json.loads((P/'run/services.json').read_text());assert current['serving_instance']==provider
 for key in ('serving_instance','serving_holder'):current.pop(key,None)
 current['processes']={k:v for k,v in current['processes'].items() if k not in ('ollama','gateway','llama_server','fabro')}
 stack._save_services(P,current)
fenced(promote)
record={'status':'SOURCE_PROMOTED_ADMISSION_PAUSED','source_revision':scope['source_revision'],'operator_epoch':25,
 'history_unchanged':True,'generation_requests':0,'at':utc_now()}
immutable_json(O/'stage1.json',record);print(json.dumps(record),flush=True)
