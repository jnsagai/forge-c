from pathlib import Path
import json,os,sys,sqlite3
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1')
os.environ.update(json.loads((E/'control/runtime-env-v6.json').read_text()));sys.path.insert(0,str(E/'source/factory/python'))
from forge_factory.fabro.client import FabroClient,load_token
from forge_factory.afo.durable import digest,immutable_json
from forge_factory.common import utc_now,sha256_file
rid='01M6855WHNYHGCV6PFB5HPHAVH';failures=[]
with FabroClient(base_url='http://127.0.0.1:32404/api/v1',token=load_token(str(E/'fabro/storage')),timeout=15) as c:
 for e in c.iter_events(rid):
  if e['event']=='stage.failed' and e.get('node_id') in ('swe5_inspector','swe6_test_author','swe6_author'):
   p=e.get('properties') or {}
   failures.append({'at':e['ts'],'node':e['node_id'],'failure':p.get('failure'),'timing':p.get('timing'),'event_sha256':digest(e)})
meter=E/'state/llm-gateway/usage.jsonl';rows=[]
for line in meter.open():
 d=json.loads(line)
 if not ('2026-10-31T06:48:25'<d.get('ts_utc','')<'2026-10-31T06:48:55'):continue
 if not ('refused' in d or 'tokens_output' in d):continue
 rows.append({k:v for k,v in d.items() if k in ('ts_utc','model','refused','upstream_called','tokens_input','tokens_output','latency_ms','tool_calls','finish_reason','local')})
request_rows=[]
with sqlite3.connect('file:'+str(E/'state/conductor/conductor.sqlite3')+'?mode=ro',uri=True) as db:
 for row in rows:
  req=(row.get('local') or {}).get('request_id')
  if not req:continue
  record=db.execute('SELECT record FROM afo_request_ledger WHERE request_id=?',(req,)).fetchone()
  if record:
   d=json.loads(record[0]);request_rows.append({k:v for k,v in d.items() if k in ('request_id','mission_id','job_id','state','reserved_at','started_at','quiescent_at','reported_tokens','charge')})
out={'schema':'forge-c/native-timeout-drain-observation/1','at':utc_now(),'native_id':rid,'source_revision':'0e342eef3c68786d29e5b9843606892c4ab68b60','stage_failures':failures,'gateway_rows':rows,'completed_request_ledger':request_rows,'model_calls_by_observer':0,'candidate_execution_by_observer':False,'workspace_written_by_observer':False,'limits':'Captured timeline and durable request identity, not new model execution or measured benefit of inactive fix'}
assert len(failures)==3 and any(x.get('refused')=='INFERENCE_REQUEST_BUSY' for x in rows)
p=E/'control/qualification-observations/cohort/afo-f83452175591716f'/('native-timeout-drain-'+digest(out)+'.json');immutable_json(p,out)
print(json.dumps({'path':str(p),'sha256':sha256_file(p),'failures':failures,'gateway_rows':rows,'completed_request_ledger':request_rows}))
