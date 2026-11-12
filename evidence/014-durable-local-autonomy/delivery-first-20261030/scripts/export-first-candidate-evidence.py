
from pathlib import Path
import sys,json,hashlib,shutil,httpx
R=Path('/mnt/data/forge-c/delivery-first-014-20261030-v1');sys.path.insert(0,str(R/'source/factory/python'))
from forge_factory.fabro.client import FabroClient,load_token,run_status
from forge_factory.afo.durable import immutable_json,immutable_bytes
from forge_factory.common import utc_now
from forge_factory.release.finalize import verify_archive
OUT=R/'public-evidence-first-candidate-v1';OUT.mkdir(exist_ok=True)
manifest=[]
for sub,files in {
 '': ['prepared.json','launch.json','source-preparation.json'],
 'fixture-only':['prepared.json','launch.json','context-overflow-stop.json','context-overflow-package.json','fixture-service-stop.json','state/llm-gateway/request-measurements.jsonl','fixture-requests.jsonl'],
 'fixture-v2':['prepared.json','launch.json','state/llm-gateway/request-measurements.jsonl','fixture-requests.jsonl']}.items():
 for rel in files:
  p=R/sub/rel
  if not p.is_file():continue
  dest=OUT/(sub or 'live')/rel
  immutable_bytes(dest,p.read_bytes());manifest.append({'path':str(dest.relative_to(OUT)),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
d=json.loads((R/'launch.json').read_text());ws=Path(d['workspace'])
rel='software/ll/stm32n6xx_ll_crc.h';root=ws/'.forge-run/delivery-first/attempt-0'
assert json.loads((root/'result.json').read_text())['candidate_hashes'][rel]=='511956a9345ca465b265a60214f16fb43c5d2395b18dfcf7fd4766a980cc29f5'
for f in root.rglob('*'):
 if f.is_file() and f.suffix not in ('.o',) and f.name!='oracle':
  dest=OUT/'first-candidate'/f.relative_to(root);immutable_bytes(dest,f.read_bytes());manifest.append({'path':str(dest.relative_to(OUT)),'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()})
with FabroClient(base_url='http://127.0.0.1:32402',token=load_token(str(R/'fabro/storage')),timeout=15) as c:
 es=list(c.iter_events(d['native_id']));started=[];completed=[]
 for e in es:
  obj=(e.get('properties') or {}).get('event',{})
  if not isinstance(obj,dict):continue
  for kind,dest in [('ToolCallStarted',started),('ToolCallCompleted',completed)]:
   item=obj.get(kind)
   if isinstance(item,dict) and item.get('tool_call_id')=='mHnH8gGd0lrf3zT1BPh3e6z9O9luRX4D':
    rec={'native_tool_call_id':item['tool_call_id'],'node':e.get('node_id'),'event_kind':kind,'is_error':item.get('is_error'),'name':item.get('tool_name')}
    if kind=='ToolCallStarted':
     a=item['arguments'];a=json.loads(a) if isinstance(a,str) else a
     rec['submitted_content_sha256']=hashlib.sha256(a['content'].encode()).hexdigest()
    dest.append(rec)
 assert len(started)==len(completed)==1 and not completed[0]['is_error'],(started,completed)
 auth={'at':utc_now(),'native_id':d['native_id'],'source_revision':d['source_revision'],'profile':json.loads((R/'prepared.json').read_text())['profile'],
 'candidate_sha256':'511956a9345ca465b265a60214f16fb43c5d2395b18dfcf7fd4766a980cc29f5',
 'initially_absent':json.loads((ws/'.forge-run/delivery-first/initial.json').read_text())['candidate_initially_absent'],
 'native_write_started':started,'native_write_completed':completed,'imported_vendor_implementation':False,
 'candidate_source':'ACTUAL_NATIVE_QWEN_TOOL_SUBMISSION','full_functional_milestone':'NOT_PROVEN'}
 immutable_json(OUT/'authorship.json',auth);manifest.append({'path':'authorship.json','sha256':hashlib.sha256((OUT/'authorship.json').read_bytes()).hexdigest()})
fx=R/'fixture-v2';launch=json.loads((fx/'launch.json').read_text());fws=Path(launch['workspace'])
with FabroClient(base_url='http://127.0.0.1:32403',token=load_token(str(fx/'fabro/storage')),timeout=15) as c:
 es=list(c.iter_events(launch['native_id']));status=run_status(c.get_run(launch['native_id']))
 phases={f'SWE.{i}':{'author_attempted':any(e['event']=='stage.started' and e.get('node_id')==f'swe{i}_author' for e in es),
 'inspector_attempted':any(e['event']=='stage.started' and e.get('node_id')==f'swe{i}_inspector' for e in es)} for i in range(1,7)}
 pp=json.loads((fws/'.forge-run/package.json').read_text())
 proof={'at':utc_now(),'native_id':launch['native_id'],'source_revision':launch['source_revision'],'native_status':status,
 'phases':phases,'real_qwen_generation_calls':0,'mode':'FIXTURE_ONLY','package_status':pp['package_status'],'gap_count':pp['gap_count'],
 'archive_sha256':pp['archive_sha256'],'integrity':verify_archive(Path(pp['archive']))['integrity'],
 'functional_verification':json.loads((R/'fixture-v2/archives/staging'/launch['work_order']/'verification/delivery-first/report.json').read_text())['functional_verification']}
 assert status=='SUCCEEDED' and all(all(v.values()) for v in phases.values()) and proof['package_status']=='BLOCKED'
 immutable_json(OUT/'fixture-v2-terminal-proof.json',proof);manifest.append({'path':'fixture-v2-terminal-proof.json','sha256':hashlib.sha256((OUT/'fixture-v2-terminal-proof.json').read_bytes()).hexdigest()})
immutable_json(OUT/'transfer-manifest.json',{'files':manifest,'private_inputs_exported':False,'hidden_reasoning_exported':False})
print(json.dumps({'export':str(OUT),'files':len(manifest),'authorship_verified':True,'fixture_phases':6,'fixture_integrity':proof['integrity']}))

