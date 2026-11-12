from pathlib import Path
import os,sys,json,subprocess
P=Path('/mnt/data/forge-c/production-local-014')
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.afo.operations import Intent
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.lrtx import stack,provider_process
from forge_factory.common import utc_now
state=Intent().read()
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as db:
 mission=MissionLedger(db).snapshot('F014-IDR-M1-HIGH-20261028')
 order=db.order('afo-774900b297bdde37')
 with db.tx() as c:
  pending=c.execute("SELECT COUNT(*) FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()[0]
  live=json.loads(c.execute('SELECT record FROM afo_execution_liveness WHERE job_id=?',('afo-product-b715f920180f440b708e55a0',)).fetchone()[0])
settings=stack.settings('local-rtx-v2-omniverse2-q38-qm-demo-mtp')
print(json.dumps({'at':utc_now(),'operator':{k:state.get(k) for k in ('mode','epoch','effective_stop')},
 'provider_quiet':bool(provider_process.quiet(stack.serving_instance(settings))),
 'production_revision':subprocess.check_output(['git','-C',str(P/'repo'),'rev-parse','HEAD'],text=True).strip(),
 'production_source_clean':not bool(subprocess.check_output(['git','-C',str(P/'repo'),'status','--porcelain'])),
 'outstanding_requests':pending,'mission':mission,
 'execution':{k:live.get(k) for k in ('job_id','execution_liveness','resource_lease','task_outcome','terminal_reason','native_run_ids')},
 'parent_order':{k:order.get(k) for k in ('order_id','state','terminal_reason')},
 'read_only':True,'model_requests':0,'operator_or_service_mutation':False},indent=2))

