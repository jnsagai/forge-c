from pathlib import Path
import collections,hashlib,json,os,sys
P=Path('/mnt/data/forge-c/production-local-014');O=P/'deployment/afo-repair-live-20261029-v7'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.fabro.client import FabroClient,load_token
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.common import utc_now
s=json.loads((O/'scope.json').read_text())
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as db:
 with db.tx() as c:
  j=json.loads(c.execute('SELECT record FROM afo_local_agent_jobs WHERE order_id=?',(s['new_order_id'],)).fetchone()[0])
  x=json.loads(c.execute('SELECT record FROM afo_execution_liveness WHERE job_id=?',(j['job_id'],)).fetchone()[0])
rid=j.get('run_id') or x['native_run_ids'][0];facts=[];counts=collections.Counter()
with FabroClient(token=load_token(),timeout=10) as client:
 for e in client.iter_events(rid):
  name=e['event'];p=e['properties'];inner=p.get('event') or {};counts[name]+=1
  if name=='agent.tool.started':
   v=inner['ToolCallStarted'];a=v.get('arguments') or {};facts.append({'seq':e['seq'],'at':e['ts'],'tool':v['tool_name'],'args':{k:a[k] for k in ('path','offset','skill_name','reproducer') if k in a}})
   if isinstance(a.get('content'),str):facts[-1].update(content_sha256=hashlib.sha256(a['content'].encode()).hexdigest(),content_bytes=len(a['content'].encode()))
   if isinstance(a.get('tests'),list):facts[-1]['tests']=a['tests']
  elif name=='agent.tool.completed':
   v=inner['ToolCallCompleted'];row={'seq':e['seq'],'at':e['ts'],'tool':v['tool_name'],'is_error':v.get('is_error')}
   if v['tool_name']!='use_skill':
    try:
     d=json.loads(v.get('output',''));m=d.get('metrics') or {};row.update(status=d.get('status'),issues=d.get('issues'),page={k:m.get(k) for k in ('offset','total_chars','next_offset')})
    except (ValueError,TypeError,AttributeError):row['output_format']='NON_JSON'
   facts.append(row)
  elif name=='agent.error':facts.append({'seq':e['seq'],'event':name,'error':inner.get('Error')})
print(json.dumps({'at':utc_now(),'run_id':rid,'job_id':j['job_id'],'state':j['state'],'event_counts':counts,'tool_facts':facts,'hidden_reasoning_saved':False,'observer_model_requests':0},indent=2))
