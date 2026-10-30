from pathlib import Path
import json,os,sys,subprocess,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/rcc-context-completion-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations
from forge_factory.afo.queue import Store
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import immutable_json,digest
from forge_factory.common import utc_now
from forge_factory.fabro.client import FabroClient,load_token
S=Store();I=operations.Intent();jid='afo-agent-61401956787984d8c097bc36'
with I.lock():
 assert I.read()['mode']=='PAUSED' and I.read()['epoch']==55
 with FabroClient(token=load_token(),timeout=10) as client:state=Executions(S).reconcile(jid,client,cancel=True)
 with S.tx() as c:
  jobs=[{'job_id':r['job_id'],'state':r['state']} for r in c.execute('SELECT job_id,state FROM afo_local_agent_jobs WHERE job_id=?',(jid,))]
  requests={r['state']:r['n'] for r in c.execute('SELECT state,COUNT(*) n FROM afo_request_ledger WHERE job_id=? GROUP BY state',(jid,))}
 print(json.dumps({'at':utc_now(),'execution':state,'job':jobs,'requests':requests,'pending':len(Executions(S).pending()),'model_requests':0},indent=2))
