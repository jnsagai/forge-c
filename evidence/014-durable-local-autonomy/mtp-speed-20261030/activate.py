"""Owner-delegated finite benchmark activation. Not an autonomous source promoter."""
from pathlib import Path
import argparse,json,os,signal,subprocess,sys,tempfile,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/q38-mtp-speed-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations,authz,policy
from forge_factory.afo.queue import Store
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.lrtx import stack,provider_process,pidfd
import yaml
p=argparse.ArgumentParser();p.add_argument('--variant',choices=('draft3','draft2','draft4','draft6'),required=True);p.add_argument('--epoch',required=True,type=int);p.add_argument('--installed',action='store_true');a=p.parse_args()
s=json.loads((O/'scope.json').read_text());assert s['source_revision']=='a9b2ddfccc326bdcf8287c95a4310c0408429ccb' and s['purpose']=='MTP_SPEED_PILOT_ONLY'
ginfo=s['grants'][a.variant];E=O/a.variant;profile=ginfo['profile'];I=operations.Intent();S=Store();L=MissionLedger(S)
assert time.time()<ginfo['mission']['limits']['deadline']
assert json.loads((O/'owner-approval.json').read_text())['scope_sha256']==digest(s)
def quiet():
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
def atomic(path,raw):
 fd,name=tempfile.mkstemp(prefix='.reasoning-benchmark-',dir=path.parent)
 with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 os.chmod(name,0o600);os.replace(name,path)
 fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
def history():
 with S.tx() as c:mids=[r[0] for r in c.execute('SELECT mission_id FROM afo_missions')]
 return {mid:L.snapshot(mid) for mid in mids}
if not a.installed:
 quiet();r=I.read();assert r['epoch']==a.epoch
 if a.variant=='draft3':
  assert r['mode']=='PAUSED' and a.epoch==79
 else:
  assert r['mode']=='RUNNING'
  r=operations.synchronize(S,'pause',str(os.getuid()),'Owner benchmark: previous MTP cohort complete and quiet; change only MTP draft length, no product continuation',expected_epoch=a.epoch,authentication={'method':'OS_STATE_DIRECTORY_OWNER'})
  a.epoch=r['epoch']
 before=history();immutable_json(E/'history-before-activation.json',before)
 def fenced(fn):
  with I.lock():
   x=I.read();assert x['epoch']==a.epoch and x['mode'] in ('STOPPED','PAUSED');quiet();return fn()
 for unit in ('forge-qwen-mission-recorder.service','forge-afo-watchdog-014-omniverse2.timer','forge-afo-watchdog-014-omniverse2.service',operations.UNIT):
  fenced(lambda unit=unit:subprocess.run(['systemctl','--user','stop',unit],check=True,timeout=45))
 N=P/'deployment/qualification-mtp-speed-a9b2ddf-mtp-paused79-v1'
 proof=json.loads((N/'provenance.json').read_text())
 assert proof['source_revision']==s['source_revision'] and proof['pytest_exit_code']==0 and proof['summary']=={'tests':126,'failures':0,'errors':0,'skipped':0}
 assert proof['source_clean_before'] and proof['source_clean_after'] and proof['model_requests']==0 and proof['operator_intent_unchanged']
 for variant in ('draft3','draft2','draft4','draft6'):
  D=O/variant;g=json.loads((D/'authorization.json').read_text())
  assert authz.signature_valid(g,D/'authorization-message.bin.sig',authz.ALLOWED_SIGNERS)
  assert g['signed_runbook_ref']=='qualification-014:'+s['grants'][variant]['manifest_sha256'] and g['policy_sha256']==s['grants'][variant]['policy_sha256']
  assert g['approval_evidence_ref']=='owner-mtp-speed-20261030:'+digest(s)
 tools=json.loads((O/'execution-tools.json').read_text())
 from forge_factory.common import sha256_file
 assert sha256_file(Path(__file__))==tools['activate-mtp-speed.py']['sha256']
 rec=json.loads((P/'run/services.json').read_text());immutable_json(E/'services-before-activation.json',rec)
 old=rec.get('serving_instance')
 if old and not provider_process.quiet(old):
  stopped=provider_process.stop(old,fenced_effect=fenced);immutable_json(E/'provider-stop.json',stopped)
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
  assert history()==before and not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
  current=subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()
  if current!=s['source_revision']:
   assert a.variant=='draft3' and current=='37c0c354629312a70eb6a199989477036bb674d9'
   Q=P/'deployment/qualification-mtp-speed-a9b2ddf-mtp-paused79-v1/repo'
   subprocess.run(['git','-C',str(R),'fetch',str(Q),'HEAD'],check=True,capture_output=True)
   subprocess.run(['git','-C',str(R),'merge','--ff-only',s['source_revision']],check=True,capture_output=True)
  assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
  saved=json.loads((P/'run/services.json').read_text())
  saved['processes']={}
  for key in ('serving_instance','serving_holder'):saved.pop(key,None)
  stack._save_services(P,saved)
  for effort in ('draft3','draft2','draft4','draft6'):
   D=O/effort;g=json.loads((D/'authorization.json').read_text())
   immutable_json(authz.AUTH_DIR/(g['authorization_id']+'.json'),g);immutable_bytes(authz.AUTH_DIR/g['signature_ref'],(D/'authorization-message.bin.sig').read_bytes())
  policy_path=Path(os.environ['FORGE_AFO_POLICY']);immutable_bytes(E/'policy-before-activation.yaml',policy_path.read_bytes());atomic(policy_path,(E/'policy.yaml').read_bytes())
  envfile=P/'state/afo/conductor.env';raw=envfile.read_bytes();immutable_bytes(E/'conductor.env.before',raw);(E/'conductor.env.before').chmod(0o600)
  previous=os.environ['FORGE_LRTX_PROFILE'];atomic(envfile,raw.replace(previous.encode(),profile.encode()))
  for name in ('forge-conductor-local-omniverse2.service','forge-afo-watchdog-014-omniverse2.service'):
   unit=Path.home()/'.config/systemd/user'/name;raw=unit.read_bytes();immutable_bytes(E/(name+'.before'),raw)
   if previous in raw.decode():atomic(unit,raw.replace(previous.encode(),profile.encode()))
  os.environ['FORGE_LRTX_PROFILE']=profile;os.environ['FORGE_OPERATIONS_PROFILE']=profile
  assert policy.load().sha256==ginfo['policy_sha256'] and policy.load().mode=='PILOT'
  (P/'fabro/settings.toml').write_text(stack.fabro_config(stack.settings(profile)))
  subprocess.run(['systemctl','--user','daemon-reload'],check=True,timeout=20)
  assert history()==before
 fenced(install)
 os.execv(sys.executable,[sys.executable,__file__,'--variant',a.variant,'--epoch',str(a.epoch),'--installed'])
# Fresh exact-source process: cached modules from older deployment cannot launch a new provider.
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==s['source_revision']
quiet();assert I.read()['epoch']==a.epoch and I.read()['mode'] in ('STOPPED','PAUSED')
r=operations.synchronize(S,'resume',str(os.getuid()),'Owner-signed MTP-speed benchmark only: '+a.variant+'; old LL remains BLOCKED, no product retry or historical reset',expected_epoch=a.epoch,authentication={'method':'OS_STATE_DIRECTORY_OWNER'})
settings=stack.settings(profile);load_start=time.monotonic()
try:
 health=stack.start(settings,recovery=True)
finally:
 # Model-free supervision survives an unhealthy experimental provider too.
 with I.lock():
  if I.read()['mode']=='RUNNING' and I.read()['epoch']==r['epoch']:
   subprocess.run(['systemctl','--user','--no-block','start',operations.UNIT,'forge-afo-watchdog-014-omniverse2.timer'],check=True,timeout=20)
for _ in range(120):
 assert I.read()['mode']=='RUNNING' and I.read()['epoch']==r['epoch']
 health=stack.status(settings)
 if all(health['health'].get(k) for k in ('fabro','gateway','ollama','llama_server')):break
 time.sleep(1)
else:raise RuntimeError('BENCHMARK_STACK_NOT_HEALTHY')
with I.lock():
 assert I.read()['mode']=='RUNNING' and I.read()['epoch']==r['epoch'];quiet()
 subprocess.run(['systemctl','--user','--no-block','start',operations.UNIT,'forge-afo-watchdog-014-omniverse2.timer'],check=True,timeout=20)
 immutable_json(E/'activation.json',{'status':'BENCHMARK_ONLY_ACTIVE_NO_PRODUCT_RETRY','source_revision':s['source_revision'],'variant':a.variant,'reasoning':'xhigh','mtp_draft':ginfo['mtp_draft'],'profile':profile,'operator_epoch':r['epoch'],'health':health['health'],'load_and_control_start_seconds':time.monotonic()-load_start,'provider_instance':stack.serving_instance(settings),'model_requests':0,'historical_missions_reset':False})
print(json.dumps({'status':'BENCHMARK_ONLY_ACTIVE','variant':a.variant,'reasoning':'xhigh','mtp_draft':ginfo['mtp_draft'],'operator_epoch':r['epoch'],'health':health['health']}))

