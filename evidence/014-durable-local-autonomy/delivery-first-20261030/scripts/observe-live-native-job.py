
from pathlib import Path
import sys,json,hashlib
R=Path('/mnt/data/forge-c/delivery-first-014-20261030-v1');sys.path.insert(0,str(R/'source/factory/python'))
from forge_factory.fabro.client import FabroClient,load_token,run_status
from forge_factory.common import utc_now
d=json.loads((R/'launch.json').read_text());ws=Path(d['workspace'])
with FabroClient(base_url='http://127.0.0.1:32402',token=load_token(str(R/'fabro/storage')),timeout=20) as c:
 es=list(c.iter_events(d['native_id']));names=[];errors=0;writes=[]
 for e in es:
  obj=(e.get('properties') or {}).get('event',{})
  if not isinstance(obj,dict):continue
  t=obj.get('ToolCallStarted') or {}
  if isinstance(t,dict) and t.get('tool_name'):names.append(t['tool_name'])
  done=obj.get('ToolCallCompleted') or {}
  if isinstance(done,dict) and done.get('is_error'):errors+=1
  if isinstance(t,dict) and t.get('tool_name')=='write_file':
   a=t.get('arguments') or {}
   if isinstance(a,str):
    try:a=json.loads(a)
    except ValueError:a={}
   if isinstance(a,dict):
    raw=a.get('file_path') or a.get('path');content=a.get('content')
    if raw and isinstance(content,str):
     target=Path(raw) if Path(raw).is_absolute() else ws/raw
     if target==ws/'software/ll/stm32n6xx_ll_crc.h':
      writes.append({'tool_call_id':t.get('tool_call_id'),'node':e.get('node_id'),'submitted_content_sha256':hashlib.sha256(content.encode()).hexdigest()})
 stages=[{'at':e.get('created_at'),'event':e['event'],'node':e.get('node_id')} for e in es if e['event'] in ('stage.started','stage.completed','stage.failed')]
 candidate=ws/'software/ll/stm32n6xx_ll_crc.h'
 out={'at':utc_now(),'native_id':d['native_id'],'native_status':run_status(c.get_run(d['native_id'])),'source_revision':d['source_revision'],
 'stages':stages[-8:],'tool_calls':len(names),'tools_used':sorted(set(names)),'tool_errors':errors,
 'candidate':{'exists':candidate.is_file(),'sha256':hashlib.sha256(candidate.read_bytes()).hexdigest() if candidate.is_file() else None,
 'bytes':candidate.stat().st_size if candidate.is_file() else None,'native_write_submissions':writes}}
 for name,key in [('usage.jsonl','reported_responses'),('request-measurements.jsonl','measured_requests')]:
  f=R/'state/llm-gateway'/name;rows=[json.loads(s) for s in f.read_text().splitlines()] if f.is_file() else []
  out[key]=len(rows)
  if name=='usage.jsonl':out['reported_output_tokens']=sum(x.get('tokens_output') or 0 for x in rows)
  else:out['last_measurement']=rows[-1] if rows else None
 records=sorted((ws/'.forge-run/delivery-first').glob('attempt-*/result.json'))
 out['independent_checks']=[json.loads(p.read_text()) for p in records]
 pp=ws/'.forge-run/package.json'
 if pp.is_file():out['package']={k:v for k,v in json.loads(pp.read_text()).items() if k in ('package_status','archive','archive_sha256','gap_count')}
 print(json.dumps(out))

