from pathlib import Path
import os,json,sys,collections
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1');os.environ.update(json.loads((E/'control/runtime-env-v6.json').read_text()));sys.path.insert(0,str(E/'source/factory/python'))
from forge_factory.fabro.client import FabroClient,load_token
from forge_factory.afo.durable import digest,immutable_json
from forge_factory.common import utc_now,sha256_file
rows=[]
with FabroClient(base_url='http://127.0.0.1:32404/api/v1',token=load_token(str(E/'fabro/storage')),timeout=15) as c:
 for rid in ('01M67ETTPXS1Q73QPMQ98DNJX0','01M67R1HNE9TKPWCYJ2SVKEPJS','01M67ZJWDYS7H33828MPTK6E6D'):
  calls=[];counts=collections.Counter()
  for e in c.iter_events(rid):
   if e['event']!='agent.tool.completed':continue
   t=e['properties']['event']['ToolCallCompleted']
   if t.get('tool_name')!='mcp__forge_build_mcp__compile':continue
   v=json.loads(t['output'])
   if 'content' in v:v=json.loads(next(x['text'] for x in v['content'] if x.get('type')=='text'))
   counts[v.get('status','UNKNOWN')]+=1
   calls.append({'at':e['ts'],'node':e['node_id'],'status':v.get('status'),'issues':v.get('issues',[])})
  rows.append({'native_id':rid,'counts':dict(counts),'calls':calls})
out={'schema':'forge-c/historical-compile-ticket-observation/1','at':utc_now(),'native_runs':rows,'read_only':True,'model_calls':0,'candidate_execution':False,'limits':'Captured normal MCP compile outcomes only; independent verifier calls and authored unit/target builds are separate. No retrospective gate change.'}
p=E/'control/qualification-observations'/('historical-compile-ticket-'+digest(out)+'.json');immutable_json(p,out)
print(json.dumps({'path':str(p),'sha256':sha256_file(p),'runs':[{'native_id':r['native_id'],'counts':r['counts']} for r in rows]}))
