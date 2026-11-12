from pathlib import Path
import os,sys,json,time,copy,subprocess,signal,hashlib,tempfile
P=Path('/mnt/data/forge-c/production-local-014');O=P/'deployment/idr-context-allocation-262144-20261029-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.afo import operations
from forge_factory.afo.queue import Store
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.durable import immutable_json,digest
from forge_factory.common import utc_now
from forge_factory.lrtx import stack,provider_process
S=Store();I=operations.Intent();L=MissionLedger(S)
assert I.read()['mode']=='RUNNING' and I.read()['epoch']==28
def quiet():
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
quiet()
with S.tx() as c:mids=[r[0] for r in c.execute('SELECT mission_id FROM afo_missions')]
before={mid:L.snapshot(mid) for mid in mids}
O.mkdir(mode=0o700)
settings=stack.settings('local-rtx-v2-omniverse2-q38-qm-demo-mtp')
provider=stack.serving_instance(settings)
oldservices=json.loads((P/'run/services.json').read_text())
assert settings['profile']['runtime']['context_limit_tokens']==131072
operations.synchronize(S,'pause',str(os.getuid()),'Owner requests substantially larger context; finite zero-generation allocation probe',expected_epoch=28,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
def fenced(effect):
 with I.lock():
  assert I.read()['mode']=='PAUSED' and I.read()['epoch']==29
  quiet()
  return effect()
units=('forge-conductor-local-omniverse2.service','forge-afo-watchdog-014-omniverse2.timer','forge-afo-watchdog-014-omniverse2.service')
for unit in units:fenced(lambda unit=unit:subprocess.run(['systemctl','--user','stop',unit],check=True,timeout=45))
proof=provider_process.stop(provider,fenced_effect=fenced);assert proof
immutable_json(O/'prior-provider-quiescence.json',proof)
profile=copy.deepcopy(settings['profile']);profile['runtime']['ollama']['OLLAMA_CONTEXT_LENGTH']='262144'
argv,env,_,_=stack.llama_server_spec(P,profile,settings['ports'],stack.envmap(settings))
argv[argv.index('--port')+1]='32597';argv[argv.index('-b')+1]='1024';argv[argv.index('-ub')+1]='512'
holder=stack._holder(settings);assert holder
record={'schema':'forge-c/context-allocation-probe/1','status':'NOT_RUN','started_at':utc_now(),
 'requested_context_tokens':262144,'model':profile['models']['default'],
 'model_digest':profile['models']['allowed'][profile['models']['default']]['digest'],'precision':'Q8_0',
 'kv_precision':'f16','slots':1,'reasoning_effort':'xhigh','mtp_draft':3,'generation_requests':0,
 'production_source_unchanged':True,'argv':argv,'halt':[]}
process=None
try:
 output=(O/'server.log').open('w')
 process=fenced(lambda:subprocess.Popen(stack._nsenter(holder)+argv,env=env,cwd=P,stdout=output,stderr=subprocess.STDOUT,start_new_session=True))
 started=time.monotonic()
 while time.monotonic()-started<120:
  if I.read()['mode']!='PAUSED' or I.read()['epoch']!=29:
   record['halt'].append('NEW_OPERATOR_INTENT');break
  if process.poll() is not None:
   record['halt'].append('ALLOCATION_PROCESS_EXIT:'+str(process.returncode));break
  code="import json,urllib.request; x=json.load(urllib.request.urlopen('http://127.0.0.1:32597/props',timeout=1)); print(json.dumps({'context':x.get('default_generation_settings',{}).get('n_ctx'),'slots':x.get('total_slots')}))"
  check=subprocess.run(stack._nsenter(holder)+[str(P/'venv/bin/python'),'-c',code],env=env,capture_output=True,text=True,timeout=5)
  if check.returncode==0:
   actual=json.loads(check.stdout)
   if actual=={'context':262144,'slots':1}:
    record.update(status='PASS_ALLOCATION_ONLY',provider_context_tokens=actual['context'],provider_slot_count=actual['slots'],
     gpu_memory=subprocess.check_output(['nvidia-smi','--query-gpu=memory.total,memory.used,memory.free','--format=csv,noheader'],text=True).strip())
    break
  time.sleep(.5)
 else:record['halt'].append('ALLOCATION_START_TIMEOUT')
finally:
 if process:
  try:os.killpg(process.pid,signal.SIGTERM)
  except ProcessLookupError:pass
  try:process.wait(timeout=15)
  except subprocess.TimeoutExpired:
   os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=10)
  record['process_exit_code']=process.returncode
  record['own_provider_stopped']=True
 record['finished_at']=utc_now()
 immutable_json(O/'result.json',record)
 print(json.dumps(record),flush=True)
 def clear_retired():
  current=json.loads((P/'run/services.json').read_text())
  assert current['serving_instance']==provider
  for key in ('serving_instance','serving_holder'):current.pop(key,None)
  current['processes']={k:v for k,v in current['processes'].items() if k not in ('ollama','gateway','llama_server')}
  stack._save_services(P,current)
 fenced(clear_retired)
 operations.synchronize(S,'resume',str(os.getuid()),'Restore existing profile after bounded zero-generation allocation probe',expected_epoch=29,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
 health=stack.start(settings,recovery=True)
 for _ in range(6):
  if all(health['health'].get(k) for k in ('fabro','gateway','ollama','llama_server')):break
  time.sleep(5);health=stack.start(settings,recovery=True)
 assert all(health['health'].get(k) for k in ('fabro','gateway','ollama','llama_server')),health['health']
 with I.lock():
  assert I.read()['mode']=='RUNNING' and I.read()['epoch']==30
  quiet();assert {mid:L.snapshot(mid) for mid in mids}==before
  subprocess.run(['systemctl','--user','--no-block','start',*units[:2]],check=True,timeout=20)
  immutable_json(O/'restored.json',{'operator_epoch':30,'production_configuration_restored':True,'mission_history_unchanged':True,'health':health['health'],'generation_requests':0,'at':utc_now()})
 print(json.dumps({'status':'PROBE_COMPLETE_PRODUCTION_RESTORED','allocation':record['status'],'operator_epoch':30,'history_unchanged':True}),flush=True)
