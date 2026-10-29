"""Read-only bounded trial facts, without prompts or hidden reasoning."""
from pathlib import Path
import json,os,sys,subprocess
P=Path('/mnt/data/forge-c/production-local-014');O=P/'deployment/afo-repair-live-20261029-v7'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.operations import Intent
from forge_factory.common import utc_now
scope=json.loads((O/'scope.json').read_text())
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as db:
    order=db.order(scope['new_order_id']);old=db.order(scope['continuation_of'])
    mission=MissionLedger(db).snapshot(scope['mission_id'])
    with db.tx() as c:
        jobs=[json.loads(r[0]) for r in c.execute('SELECT record FROM afo_local_agent_jobs WHERE order_id=?',(scope['new_order_id'],))]
        records=[]
        for j in jobs:
            execution=c.execute('SELECT record FROM afo_execution_liveness WHERE job_id=?',(j['job_id'],)).fetchone()
            verifier=c.execute('SELECT state,record FROM afo_verification_jobs WHERE job_id=?',(j['job_id'],)).fetchone()
            requests={r['state']:r['n'] for r in c.execute('SELECT state,COUNT(*) n FROM afo_request_ledger WHERE job_id=? GROUP BY state',(j['job_id'],))}
            case=Path(j['case']);case_doc=json.loads(case.read_text())
            src=Path(case_doc['src'])
            diff=subprocess.run(['git','-C',str(src),'diff','--stat'],capture_output=True,text=True,timeout=10)
            row={k:j.get(k) for k in ('job_id','state','role','model','model_digest','profile','factory_revision','run_id','receipt_id','reserved_tokens','reported_tokens','deadline_epoch','review_state','error')}
            row['request_states']=requests;row['candidate_uncommitted_diff_stat']=diff.stdout
            row['candidate_submission_present']=(case.parent/'submission.json').is_file()
            row['execution']=json.loads(execution[0]) if execution else None
            row['verification_state']=verifier['state'] if verifier else None
            records.append(row)
        proposals=[{'status':r['status'],'record_sha256':r['record_sha256']} for r in c.execute('SELECT status,record_sha256 FROM afo_maintainer_proposals WHERE order_id=? ORDER BY seq',(scope['new_order_id'],))]
from forge_factory.fabro.client import FabroClient,load_token,run_status
with FabroClient(token=load_token(),timeout=10) as client:
 for row in records:
  if row.get('run_id'):row['native_status_now']=run_status(client.get_run(row['run_id']))
state=Intent().read()
print(json.dumps({'at':utc_now(),'trial_id':scope['trial_id'],'source_revision':scope['source_revision'],
 'operator':{k:state.get(k) for k in ('mode','epoch','effective_stop')},'deadline_utc':scope['deadline_utc'],
 'order':{k:(order or {}).get(k) for k in ('order_id','state','terminal_reason')},
 'original_order':{k:old.get(k) for k in ('order_id','state','terminal_reason')},
 'jobs':records,'mission':mission,'proposals':proposals,'read_only':True,'model_requests_by_observer':0,
 'independent_frozen_candidate_verification':'NOT_RUN'},indent=2))
