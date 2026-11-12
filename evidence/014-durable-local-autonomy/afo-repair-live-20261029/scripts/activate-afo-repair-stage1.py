"""Owner-authorized exact controller/profile activation; no order or generation."""
from pathlib import Path
import json,os,signal,subprocess,sys,time,tempfile,xml.etree.ElementTree as ET
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';D=P/'deployment'
Q=D/'qualification-core-stop-3015e47-v6/repo';O=D/'afo-repair-live-20261029-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.afo import authz,policy,operations,mission_deadline
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.common import utc_now
from forge_factory.lrtx import stack,provider_process,pidfd
scope=json.loads((O/'scope.json').read_text());approval=json.loads((O/'owner-approval.json').read_text())
assert digest(scope)==approval['scope_sha256']
assert approval['owner_answer']=='you can load again the qwen model on omniverse and use it'
assert time.time()<scope['deadline_epoch']
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
assert git(R,'rev-parse','HEAD')==scope['repair_baseline_revision'] and not git(R,'status','--porcelain')
assert git(Q,'rev-parse','HEAD')==scope['source_revision'] and not git(Q,'status','--porcelain')
for label,count in (('qualification-swe6-stop-3015e47-v4',41),('qualification-core-stop-3015e47-v6',89)):
    n=D/label; s=next(ET.parse(n/'pytest.xml').getroot().iter('testsuite'))
    assert int(s.get('tests'))==count and all(s.get(k)=='0' for k in ('failures','errors','skipped'))
    p=json.loads((n/'provenance.json').read_text())
    assert p['source_revision']==scope['source_revision'] and p['source_clean_before'] and p['source_clean_after'] and p['pytest_exit_code']==0
for label in ('primary','time'):
    g=json.loads((O/(label+'-authorization.json')).read_text())
    assert authz.signature_valid(g,O/(label+'-authorization-message.bin.sig'),authz.ALLOWED_SIGNERS)
    assert g['policy_sha256']==scope['policy_sha256'] and g['expires_utc']==scope['deadline_utc']
S=Store();I=operations.Intent();L=MissionLedger(S)
def quiet():
    assert not Executions(S).pending()
    with S.tx() as c:
        assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
        assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
        assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
def fenced(effect):
    with I.lock():
        assert I.read()['mode']=='STOPPED' and I.read()['epoch']==33 and I.read()['effective_stop']
        quiet();return effect()
assert digest(L.snapshot(scope['mission_id']))==scope['mission_snapshot_sha256']
for unit in ('forge-afo-watchdog-014-omniverse2.timer','forge-afo-watchdog-014-omniverse2.service','forge-conductor-local-omniverse2.service'):
    fenced(lambda unit=unit:subprocess.run(['systemctl','--user','stop',unit],check=True,timeout=45))
fenced(lambda:immutable_json(O/'database-backup.json',S.backup(O/'conductor-before.sqlite3')))
services=json.loads((P/'run/services.json').read_text());immutable_json(O/'services-before.json',services)
provider=stack.serving_instance(stack.settings('local-rtx-v2-omniverse2-q38-qm-demo-mtp'))
assert provider_process.quiet(provider)
pr=services['processes'].get('fabro')
if pr:
    def terminate():
        actual=stack.process_identity(pr['pid'])
        if actual is None:return
        assert actual==pr['identity']
        fd=pidfd.open_pid(pr['pid'])
        try:
            assert stack.process_identity(pr['pid'])==pr['identity'];pidfd.send_signal(fd,signal.SIGTERM)
        finally:os.close(fd)
    fenced(terminate)
    for _ in range(100):
        actual=stack.process_identity(pr['pid'])
        if actual is None or actual.get('start_ticks')!=pr['identity']['start_ticks']:break
        time.sleep(.05)
    else:raise RuntimeError('PREVIOUS_FABRO_NOT_QUIESCENT')
def atomic(path,raw):
    fd,name=tempfile.mkstemp(prefix='.afo-repair-next-',dir=path.parent)
    with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    os.chmod(name,0o600);os.replace(name,path)
    fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
def promote():
    assert provider_process.quiet(provider)
    subprocess.run(['git','-C',str(R),'fetch',str(Q),'HEAD'],check=True,capture_output=True)
    subprocess.run(['git','-C',str(R),'merge','--ff-only',scope['source_revision']],check=True,capture_output=True)
    assert not git(R,'status','--porcelain')
    current=json.loads((P/'run/services.json').read_text());assert current['serving_instance']==provider
    for k in ('serving_instance','serving_holder'):current.pop(k,None)
    current['processes']={k:v for k,v in current['processes'].items() if k not in ('fabro','ollama','gateway','llama_server')}
    stack._save_services(P,current)
    env=P/'state/afo/conductor.env';old=env.read_bytes();immutable_bytes(O/'conductor.env.before',old)
    previous='local-rtx-v2-omniverse2-q38-qm-demo-mtp'
    assert previous in old.decode();atomic(env,old.decode().replace(previous,scope['profile']).encode())
    for name in ('forge-conductor-local-omniverse2.service','forge-afo-watchdog-014-omniverse2.service'):
        unit=Path('/home/omniverse2/.config/systemd/user')/name;raw=unit.read_bytes()
        immutable_bytes(O/(name+'.before'),raw)
        assert previous in raw.decode();atomic(unit,raw.decode().replace(previous,scope['profile']).encode())
    subprocess.run(['systemctl','--user','daemon-reload'],check=True,timeout=20)
    for label in ('primary','time'):
        g=json.loads((O/(label+'-authorization.json')).read_text())
        immutable_json(authz.AUTH_DIR/(g['authorization_id']+'.json'),g)
        immutable_bytes(authz.AUTH_DIR/g['signature_ref'],(O/(label+'-authorization-message.bin.sig')).read_bytes())
    target=Path(os.environ['FORGE_AFO_POLICY']);immutable_bytes(O/'policy.before',target.read_bytes())
    atomic(target,(O/'proposed-policy.yaml').read_bytes())
    eff=policy.load(log=False);assert eff.mode=='PILOT' and eff.sha256==scope['policy_sha256'],eff.issues
    immutable_json(O/'deadline-extension-receipt.json',mission_deadline.extend(S,json.loads((O/'deadline-extension.json').read_text()),eff))
    after=L.snapshot(scope['mission_id']);before=scope['mission_before']
    for key in ('attempts','jobs','requests','tools','corrections','charged_tokens','usage_unknown','unique_executions'):
        assert after[key]==before[key]
    assert {k:v for k,v in after['limits'].items() if k!='deadline'}=={k:v for k,v in before['limits'].items() if k!='deadline'}
    for mid,snap in json.loads((O/'all-missions-before.json').read_text()).items():
        if mid!=scope['mission_id']:assert L.snapshot(mid)==snap
    immutable_json(O/'mission-after-window.json',after)
fenced(promote)
for line in (P/'state/afo/conductor.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1);os.environ[k]=v
os.environ['FORGE_OPERATIONS_PROFILE']=scope['profile'];os.environ['FORGE_LRTX_PROFILE']=scope['profile']
rec=operations.synchronize(S,'resume',str(os.getuid()),'Owner explicitly permits loading Qwen and using the prepared scoped AFO maintenance trial; four-hour signed window',
    expected_epoch=33,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
assert rec['epoch']==34
settings=stack.settings(scope['profile']);(P/'fabro/settings.toml').write_text(stack.fabro_config(settings))
print(json.dumps({'status':'SIGNED_SCOPE_ACTIVATED_LOADING_QWEN','operator_epoch':34,'source_revision':scope['source_revision'],'model_requests':0}),flush=True)
health=stack.start(settings,recovery=True)
for _ in range(12):
    if all(health['health'].get(k) is True for k in ('fabro','gateway','ollama','llama_server')):break
    time.sleep(3);health=stack.start(settings,recovery=True)
assert all(health['health'].get(k) is True for k in ('fabro','gateway','ollama','llama_server')),health['health']
immutable_json(O/'provider-ready.json',{'health':health['health'],'serving_instance':health['serving_instance'],
    'source_revision':scope['source_revision'],'profile_sha256':scope['profile_sha256'],'at':utc_now(),'generation_requests':0})
code="import json,urllib.request; x=json.load(urllib.request.urlopen('http://127.0.0.1:11457/props',timeout=5)); print(json.dumps({'context':x.get('default_generation_settings',{}).get('n_ctx'),'slots':x.get('total_slots')}))"
probe=subprocess.run(stack._nsenter(stack._holder(settings))+[str(P/'venv/bin/python'),'-c',code],capture_output=True,text=True,timeout=15,check=True)
actual=json.loads(probe.stdout);assert actual=={'context':131072,'slots':1},actual
allocation={'schema':'forge-c/context-allocation-probe/1','status':'PASS_ALLOCATION_ONLY','provider_context_tokens':131072,
 'provider_slot_count':1,'model_digest':scope['model_digest'],'precision':'Q8_0','kv_precision':'f16','mtp_draft':3,
 'reasoning_effort':'xhigh','profile_sha256':scope['profile_sha256'],'generation_requests':0,'at':utc_now(),
 'gpu_memory':subprocess.check_output(['nvidia-smi','--query-gpu=memory.total,memory.used,memory.free','--format=csv,noheader'],text=True).strip()}
immutable_json(O/'allocation.json',allocation)
print(json.dumps({'status':'QWEN_LOADED_HEALTHY_NO_GENERATION','health':health['health'],'allocation':allocation,'operator_epoch':34}),flush=True)
