"""External owner-delegated activation of qualified source; no autonomous source promotion."""
from pathlib import Path
import argparse,json,os,signal,subprocess,sys,tempfile,time
import yaml
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/aspice-rcc-stepwise-20261030-v1';Q=P/'deployment/qualification-product-stepwise-a32d87a3-epoch99-v1/repo'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations,authz,policy,mission_deadline
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.common import sha256_file,utc_now
from forge_factory.lrtx import stack,provider_process,pidfd
ap=argparse.ArgumentParser();ap.add_argument('--installed',action='store_true');a=ap.parse_args()
s=json.loads((O/'scope.json').read_text());assert digest(s)=='bf55764e2affc33ef45341b29287d62a32fb337a1b72f976d4db3d65a93d61f5'
assert time.time()<s['deadline_epoch'] and json.loads((O/'owner-approval.json').read_text())['scope_sha256']==digest(s)
assert s['functional_gates_blocking'] and not s['advisory_continue'] and not s['historical_counters_reset']
proof=json.loads((Q.parent/'provenance.json').read_text())
assert sha256_file(Q.parent/'provenance.json')==s['native_qualification_ref']['sha256']
assert proof['source_revision']==s['source_revision'] and proof['pytest_exit_code']==0 and proof['summary']=={'tests':333,'failures':0,'errors':0,'skipped':0}
assert proof['source_clean_before'] and proof['source_clean_after'] and proof['model_requests']==0 and not proof['deployment']
assert json.loads((O/'initial-request-preflight.json').read_text())['status']=='PASS_INPUT_AND_INITIAL_SWE1_CONTEXT_ONLY'
for label in ('primary','roles','time'):
 g=json.loads((O/(label+'-authorization.json')).read_text());assert authz.signature_valid(g,O/(label+'-authorization-message.bin.sig'),authz.ALLOWED_SIGNERS)
 assert g['expires_utc']==s['deadline_utc'] and g['policy_sha256']==s['policy_sha256']
 assert g['approval_evidence_ref']=='owner-aspice-stepwise-20261030:'+digest(s)
S=Store();I=operations.Intent();L=MissionLedger(S);before=json.loads((O/'all-missions-before.json').read_text())
def history():return {mid:L.snapshot(mid) for mid in before}
def quiet():
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
def atomic(path,raw):
 fd,name=tempfile.mkstemp(prefix='.aspice-stepwise-',dir=path.parent)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 os.chmod(name,0o600);os.replace(name,path)
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def fenced(effect):
 with I.lock():
  now=I.read();assert now['mode']=='PAUSED' and now['epoch']==101,'NEWER_OPERATOR_INTENT_PRESERVED'
  quiet();return effect()
if not a.installed:
 assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==s['previous_production_revision']
 assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
 quiet();assert history()==before
 assert I.read()['mode']=='RUNNING' and I.read()['epoch']==100
 pause=operations.synchronize(S,'pause',str(os.getuid()),'Explicit owner-delegated ASPICE LL/HAL continuation: install native333-tested stepwise diagnosis integration, retain all mission history',expected_epoch=100,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
 assert pause['epoch']==101
 for unit in ('forge-qwen-mission-recorder.service','forge-afo-watchdog-014-omniverse2.timer','forge-afo-watchdog-014-omniverse2.service',operations.UNIT):
  fenced(lambda unit=unit:subprocess.run(['systemctl','--user','stop',unit],check=True,timeout=45))
 fenced(lambda:immutable_json(O/'database-backup.json',S.backup(O/'conductor-before.sqlite3')))
 rec=json.loads((P/'run/services.json').read_text());immutable_json(O/'services-before.json',rec);old=rec.get('serving_instance')
 if old and not provider_process.quiet(old):immutable_json(O/'provider-stop.json',provider_process.stop(old,fenced_effect=fenced))
 assert old is None or provider_process.quiet(old)
 fab=rec.get('processes',{}).get('fabro')
 if fab:
  expected=fab['identity'];pid=fab['pid'];actual=stack.process_identity(pid)
  if actual and actual.get('state')!='Z' and all(actual.get(k)==expected.get(k) for k in ('boot_id','start_ticks','uid')):
   def kill():
    fd=pidfd.open_pid(pid)
    try:
     fresh=stack.process_identity(pid);assert all(fresh.get(k)==expected.get(k) for k in ('boot_id','start_ticks','uid'));pidfd.send_signal(fd,signal.SIGTERM)
    finally:os.close(fd)
   fenced(kill)
   for _ in range(100):
    fresh=stack.process_identity(pid)
    if fresh is None or fresh.get('state')=='Z' or fresh.get('start_ticks')!=expected['start_ticks']:break
    time.sleep(.05)
   else:raise RuntimeError('FABRO_NOT_QUIESCENT')
 def install():
  assert history()==before
  subprocess.run(['git','-C',str(R),'fetch',str(Q),'HEAD'],check=True,capture_output=True)
  subprocess.run(['git','-C',str(R),'merge','--ff-only',s['source_revision']],check=True,capture_output=True)
  assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
  saved=json.loads((P/'run/services.json').read_text());saved['processes']={}
  for k in ('serving_instance','serving_holder'):saved.pop(k,None)
  stack._save_services(P,saved)
  for label in ('primary','roles','time'):
   g=json.loads((O/(label+'-authorization.json')).read_text())
   immutable_json(authz.AUTH_DIR/(g['authorization_id']+'.json'),g);immutable_bytes(authz.AUTH_DIR/g['signature_ref'],(O/(label+'-authorization-message.bin.sig')).read_bytes())
  target=Path(os.environ['FORGE_AFO_POLICY']);assert digest(yaml.safe_load(target.read_text()))==s['policy_before_sha256']
  immutable_bytes(O/'policy-before.yaml',target.read_bytes());atomic(target,(O/'proposed-policy.yaml').read_bytes())
  assert policy.load(log=False).mode=='PILOT' and policy.load(log=False).sha256==s['policy_sha256']
  envfile=P/'state/afo/conductor.env';raw=envfile.read_bytes();immutable_bytes(O/'conductor.env.before',raw);(O/'conductor.env.before').chmod(0o600)
  assert s['previous_profile'] in raw.decode();atomic(envfile,raw.replace(s['previous_profile'].encode(),s['profile'].encode()))
  for name in ('forge-conductor-local-omniverse2.service','forge-afo-watchdog-014-omniverse2.service'):
   unit=Path.home()/'.config/systemd/user'/name;raw=unit.read_bytes();immutable_bytes(O/(name+'.before'),raw)
   if s['previous_profile'] in raw.decode():atomic(unit,raw.replace(s['previous_profile'].encode(),s['profile'].encode()))
  assert history()==before
  subprocess.run(['systemctl','--user','daemon-reload'],check=True,timeout=20)
 fenced(install)
 os.execv(sys.executable,[sys.executable,__file__,'--installed'])
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==s['source_revision']
quiet();assert I.read()['mode']=='PAUSED' and I.read()['epoch']==101
with I.lock():
 assert I.read()['mode']=='PAUSED' and I.read()['epoch']==101;quiet()
 receipt=mission_deadline.extend(S,json.loads((O/'time-document.json').read_text()),policy.load(log=False))
 immutable_json(O/'time-extension-receipt.json',receipt)
 after=history()
 for mid,snap in before.items():
  if mid!=s['mission_id']:assert after[mid]==snap
  else:
   for k in ('attempts','jobs','requests','tools','corrections','charged_tokens','usage_unknown','unique_executions','unbounded_historical_usage'):assert after[mid][k]==snap[k]
   assert {k:v for k,v in after[mid]['limits'].items() if k!='deadline'}=={k:v for k,v in snap['limits'].items() if k!='deadline'}
settings=stack.settings(s['profile']);(P/'fabro/settings.toml').write_text(stack.fabro_config(settings))
resumed=operations.synchronize(S,'resume',str(os.getuid()),'Owner-signed ASPICE-only LL/HAL continuation until19:40UTC; medium Q8/MTP3, blocking gates, same RCC mission/history; no product admitted yet',expected_epoch=101,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
assert resumed['epoch']==102
try:
 health=stack.start(settings,recovery=True)
 for _ in range(90):
  assert I.read()['mode']=='RUNNING' and I.read()['epoch']==102
  health=stack.status(settings)
  if all(health['health'].get(k) for k in ('fabro','gateway','ollama','llama_server')):break
  time.sleep(1)
 else:raise RuntimeError('ASPICE_PROVIDER_NOT_HEALTHY')
finally:
 with I.lock():
  if I.read()['mode']=='RUNNING' and I.read()['epoch']==102:subprocess.run(['systemctl','--user','--no-block','start',operations.UNIT,'forge-afo-watchdog-014-omniverse2.timer'],check=True,timeout=20)
with I.lock():
 assert I.read()['mode']=='RUNNING' and I.read()['epoch']==102;quiet()
 immutable_json(O/'activation.json',{'status':'ASPICE_PROFILE_ACTIVE_INTAKE_PENDING','source_revision':s['source_revision'],'profile':s['profile'],'operator_epoch':102,'deadline_utc':s['deadline_utc'],'same_mission':s['mission_id'],'history_counters_preserved':True,'health':health['health'],'provider_instance':stack.serving_instance(settings),'quality_gates_block_workflow':True,'native_qualification':proof['summary'],'model_requests':0,'at':utc_now()})
print((O/'activation.json').read_text())

