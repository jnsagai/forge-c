"""Only durable request measurements, typed refusals and trusted task binding; no request bodies."""
from pathlib import Path
import json,os,sys
P=Path('/mnt/data/forge-c/production-local-014')
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.durable import digest
from forge_factory.common import sha256_file,utc_now,state_dir
scope=json.loads((P/'deployment/afo-repair-live-20261029-v6/scope.json').read_text())
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as db:
 with db.tx() as c:
  job=json.loads(c.execute('SELECT record FROM afo_local_agent_jobs WHERE order_id=?',(scope['new_order_id'],)).fetchone()[0])
  metadata=[json.loads(r[0]) for r in c.execute("SELECT record FROM afo_execution_evidence WHERE job_id=? AND kind LIKE 'REQUEST_METADATA:%'",(job['job_id'],))]
  refs=[]
  for r in c.execute("SELECT record,sha256 FROM afo_execution_evidence WHERE job_id=? AND kind LIKE 'REQUEST_REFUSAL:%'",('afo-agent-97d070852addbf37acf1b7c9',)):
   d=json.loads(r[0]);assert digest(d)==r[1];refs.append(d)
 unit=state_dir()/'afo/agent-jobs'/job['job_id']/'maintenance-work-unit.json';assert sha256_file(unit)==job['maintenance_work_unit_sha256']
 print(json.dumps({'at':utc_now(),'job_id':job['job_id'],'state':job['state'],'work_unit':json.loads(unit.read_text()),'work_unit_sha256':sha256_file(unit),'complete_request_metadata':metadata,'v5_refusals':refs,'raw_prompts_or_reasoning_saved':False,'model_requests':0},indent=2))
