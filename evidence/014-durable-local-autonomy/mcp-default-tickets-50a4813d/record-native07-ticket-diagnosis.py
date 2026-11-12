from pathlib import Path
import os,json,sys,subprocess,hashlib
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1');Q=E/'source'
os.environ.update(json.loads((E/'control/runtime-env-v6.json').read_text()));sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.fabro.client import FabroClient,load_token
from forge_factory.mcp.sdk import args_digest
from forge_factory.afo.durable import digest,immutable_json
from forge_factory.common import utc_now,sha256_file
rid='01M6855WHNYHGCV6PFB5HPHAVH';name='mcp__forge_build_mcp__compile'
candidate=E/'state/workorders/WO-AFO-f83452175591716f-a1/workspace/software/ll/stm32n6xx_ll_crc.h'
before=sha256_file(candidate)
with FabroClient(base_url='http://127.0.0.1:32404/api/v1',token=load_token(str(E/'fabro/storage')),timeout=15) as c:
 events=list(c.iter_events(rid))
 starts={};results=[]
 for e in events:
  d=(e.get('properties') or {}).get('event',{})
  if e['event']=='agent.tool.started':
   t=d['ToolCallStarted']
   if t.get('tool_name')==name:starts[t['tool_call_id']]={'at':e['ts'],'node':e['node_id'],'arguments':t['arguments']}
  if e['event']=='agent.tool.completed':
   t=d['ToolCallCompleted']
   if t.get('tool_name')==name and e.get('node_id')=='df_author_0':
    v=json.loads(t['output'])
    if 'content' in v:
     v=json.loads(next(x['text'] for x in v['content'] if x.get('type')=='text'))
    results.append({'at':e['ts'],'node':e['node_id'],'start':starts.get(t['tool_call_id']),'result':{k:v.get(k) for k in ('status','summary','issues')}})
audit=[]
for line in (E/'state/events/factory-events.jsonl').open():
 if rid not in line or name not in line:continue
 d=json.loads(line);audit.append({k:v for k,v in d.items() if k in ('ts_utc','occurred_utc','ts','message','correlation_id','run_id','agent_id','tool_id','channel')})
examples=[]
for prof in ('host-clang','target-cm55-gcc'):
 a={'profile':prof};b={**a,'defines':[]}
 examples.append({'hook_arguments':a,'mcp_expanded_arguments':b,'hook_sha256':args_digest(name,a),'expanded_sha256':args_digest(name,b),'hashes_equal':args_digest(name,a)==args_digest(name,b)})
out={'schema':'forge-c/mcp-default-ticket-diagnosis/1','at':utc_now(),'native_id':rid,
 'source_revision':subprocess.check_output(['git','-C',str(Q),'rev-parse','HEAD'],text=True).strip(),
 'observed_compile_calls':results,'policy_events':audit,'actual_runtime_argument_hash_reproduction':examples,
 'candidate_before':before,'candidate_after':sha256_file(candidate),'candidate_executed':False,'model_calls':0,
 'runtime_mutated':False,'status':'REPRODUCED_ARGUMENT_CANONICALIZATION_MISMATCH',
 'limits':'Read-only SDK hash reproduction and captured native calls; no new compile/model call, no ticket issued or consumed. Inactive fix qualified separately.'}
assert out['source_revision']=='0e342eef3c68786d29e5b9843606892c4ab68b60' and out['candidate_before']==out['candidate_after']
assert len(results)==2 and all(x['result']['status']=='BLOCKED' for x in results)
assert all(not x['hashes_equal'] for x in examples)
p=E/'control/qualification-observations/cohort/afo-f83452175591716f'/('mcp-default-ticket-diagnosis-'+digest(out)+'.json')
immutable_json(p,out);print(json.dumps({'path':str(p),'sha256':sha256_file(p),'status':out['status'],'compile_calls':len(results),'candidate_unchanged':before==out['candidate_after']}))
