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
scope=json.loads((O/'scope.json').read_text())
assert operations.Intent().read()['mode']=='RUNNING' and operations.Intent().read()['epoch']==34
os.environ['FORGE_OPERATIONS_PROFILE']=scope['profile'];os.environ['FORGE_LRTX_PROFILE']=scope['profile']
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
