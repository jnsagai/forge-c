from pathlib import Path
import os,sys,json,sqlite3,hashlib,subprocess
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1')
os.environ.update(json.loads((E/'control/runtime-env-v6.json').read_text()));sys.path.insert(0,str(E/'source/factory/python'))
from forge_factory.fabro.client import FabroClient,load_token,run_status
from forge_factory.common import utc_now
db=sqlite3.connect('file:'+str(E/'state/conductor/conductor.sqlite3')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
ids=['afo-7f71565db57f0a76','afo-f83452175591716f','afo-48b5f7eb60495e69']
out={'at':utc_now(),'source_revision':subprocess.check_output(['git','-C',str(E/'source'),'rev-parse','HEAD'],text=True).strip(),'orders':[],'read_only':True,'model_calls':0,'deadline_utc':'2026-10-31T07:57:59Z'}
with FabroClient(base_url='http://127.0.0.1:32404',token=load_token(str(E/'fabro/storage')),timeout=15) as c:
 for oid in ids:
  row=dict(db.execute('SELECT order_id,state,terminal_reason FROM afo_work_orders WHERE order_id=?',(oid,)).fetchone())
  row['attempts']=[]
  for a in db.execute('SELECT attempt_id,record FROM afo_attempts WHERE order_id=? ORDER BY seq',(oid,)):
   v=json.loads(a['record']);rid=v.get('fabro_run_id');name=v.get('workspace_ref','').removeprefix('workorder:')
   current={'attempt_id':a['attempt_id'],'native_id':rid,'workspace':name}
   if rid:
    current['native_status']=run_status(c.get_run(rid));events=list(c.iter_events(rid))
    stages=[e for e in events if e['event'] in ('stage.started','stage.completed','stage.failed')]
    current['latest_stage']={k:stages[-1].get(k) for k in ('event','node_id','ts')} if stages else None
   ws=E/'state/workorders'/name/'workspace'
   initial=ws/'.forge-run/delivery-first/initial.json'
   current['candidate_initially_absent']=json.loads(initial.read_text()).get('candidate_initially_absent') if initial.is_file() else 'PREFLIGHT_PENDING'
   candidate=ws/'software/ll/stm32n6xx_ll_crc.h'
   current['candidate_sha256']=hashlib.sha256(candidate.read_bytes()).hexdigest() if candidate.is_file() else None
   current['verifiers']=[{'path':str(p.relative_to(ws)),'status':json.loads(p.read_text())['status']} for p in sorted((ws/'.forge-run/delivery-first').glob('attempt-*/result.json'))]
   row['attempts'].append(current)
  out['orders'].append(row)
out['nonquiescent_requests']=[dict(r) for r in db.execute("SELECT job_id,state,COUNT(*) AS n FROM afo_request_ledger WHERE state NOT IN ('QUIESCENT','RESERVED') GROUP BY job_id,state")]
print(json.dumps(out))
