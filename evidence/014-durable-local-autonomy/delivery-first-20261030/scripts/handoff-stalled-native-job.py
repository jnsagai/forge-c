
from pathlib import Path
import json,sys,os,signal,time,httpx,hashlib
N=Path('/mnt/data/forge-c/native-artifacts-014-20261030-v1');Q=N/'source'
os.environ['FORGE_REPO_ROOT']=str(Q);sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.fabro.client import FabroClient,load_token,run_status
from forge_factory.afo.durable import immutable_json
from forge_factory.common import utc_now
from forge_factory.lrtx import pidfd
launch=json.loads((N/'launch.json').read_text());assert launch['native_id']=='01M671YCDV672HSSY5QDGH4SNT'
ws=Path(launch['workspace']);folder=N/'delivery-first-handoff-v1';folder.mkdir(exist_ok=True)
receipt=folder/'stop-receipt.json'
if receipt.exists():print(receipt.read_text());raise SystemExit(0)
operator=json.loads(Path('/home/omniverse2/.local/state/forge-c-production-014/operations.json').read_text())
assert operator['mode']=='PAUSED' and operator['epoch']==111,'NEWER_OPERATOR_INTENT'
expected={'workproducts/SWE.1/software_requirements.md':'602814ad616f05643f6d7597f04ce1cb772a2149c92d7157142f71ef759afced',
'workproducts/SWE.1/register_effects.json':'5b08fa09e573ecb3210700c66ef2cb5ea61a93a8a1213e4118a997486ab3c45e',
'traceability/requirements_to_tests.csv':'ec1cf1b4159730c2cfe261d2c0840be9fe324e69f77c70772cc02a00398acf88',
'traceability/upstream_gaps.md':'10ed713c152cad2849592ff1d044d585bb5453c2560b7493c93c5ea1b7c8f706'}
now={rel:hashlib.sha256((ws/rel).read_bytes()).hexdigest() for rel in expected}
if now!=expected:
 print(json.dumps({'status':'HANDOFF_NOT_EXECUTED_ARTIFACT_PROGRESS_REQUIRES_REVIEW','changed':[r for r in expected if now[r]!=expected[r]]}))
 raise SystemExit(2)
intent=folder/'intent.json'
assert not intent.exists(),'UNCERTAIN_HANDOFF_RECONCILE_FIRST'
immutable_json(intent,{'at':utc_now(),'native_id':launch['native_id'],'operator_epoch':111,'reason':'OWNER_AUTHORIZED_STOP_AND_RETHINK_AFTER_NO_ARTIFACT_PROGRESS; DELIVERY_FIRST_NEW_JOB','unchanged_seed_hashes':now})
with FabroClient(base_url='http://127.0.0.1:32401',token=load_token(str(N/'fabro/storage')),timeout=15) as c:
 status=run_status(c.get_run(launch['native_id']))
 code=c.cancel(launch['native_id']) if status=='RUNNING' else None
 for _ in range(20):
  status=run_status(c.get_run(launch['native_id']))
  if status in ('SUCCEEDED','FAILED','CANCELLED','CANCELED'):break
  time.sleep(.5)
 assert status in ('SUCCEEDED','FAILED','CANCELLED','CANCELED'),'NATIVE_CANCEL_PENDING_KEEP_CAPACITY_HELD'
services=json.loads((N/'run/services.json').read_text());row=services['gateway'];pid=row['pid']
proc=Path('/proc')/str(pid);signals=[]
if proc.exists():
 fd=pidfd.open_pid(pid)
 try:
  actual=[x.decode() for x in (proc/'cmdline').read_bytes().split(b'\0') if x]
  assert actual==row['argv'],'GATEWAY_PID_IDENTITY_CHANGED'
  pidfd.send_signal(fd,signal.SIGTERM);signals.append('SIGTERM')
  for _ in range(10):
   if not proc.exists():break
   time.sleep(.5)
  if proc.exists():
   # Force only the exact retired trial gateway, closing its provider socket.
   # The model process is never signalled. Actual slot state is checked below.
   pidfd.send_signal(fd,signal.SIGKILL);signals.append('SIGKILL')
 finally:os.close(fd)
slots=httpx.get('http://127.0.0.1:11457/slots',timeout=10).json()
rec={'at':utc_now(),'native_id':launch['native_id'],'cancel_http_status':code,'native_status':status,
'classification':'EXTERNALLY_SUPERSEDED_FOR_NEW_DELIVERY_EXPERIMENT_NOT_MODEL_COMPLETION','gateway_pid':pid,'gateway_signals':signals,
'model_server_signalled':False,'provider_slots':[{'id':r['id'],'is_processing':r['is_processing']} for r in slots],
'inference_quiescent':len(slots)==1 and not slots[0]['is_processing'],'original_artifacts_and_failures_preserved':True,
'historical_mission_reset':False,'replacement_started':False}
immutable_json(receipt,rec);print(json.dumps(rec))

