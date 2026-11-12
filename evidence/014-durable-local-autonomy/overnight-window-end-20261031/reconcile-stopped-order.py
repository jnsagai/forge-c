from pathlib import Path
import os,sys,json
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1')
os.environ.update(json.loads((E/'control/runtime-env-v6.json').read_text()));sys.path.insert(0,str(E/'source/factory/python'))
from forge_factory.afo.queue import Store
from forge_factory.afo.operations import Intent
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo import dispatch
from forge_factory.afo.durable import digest,immutable_json
from forge_factory.fabro.client import FabroClient,load_token,run_status
from forge_factory.common import utc_now,sha256_file
S=Store();I=Intent();oid='afo-48b5f7eb60495e69';rid='01M68CMQAZNN7QGRZSX5DGRMYY';mid='mission-feature014-delivery-first-20261030'
with I.lock():
 intent=I.read();assert intent['mode']=='STOPPED' and intent['epoch']==7 and intent['effective_stop']
 assert not Executions(S).pending()
 before=MissionLedger(S).snapshot(mid);old=S.order(oid)
 with FabroClient(base_url='http://127.0.0.1:32404/api/v1',token=load_token(str(E/'fabro/storage')),timeout=5) as c:
  native=c.get_run(rid);kind=run_status(native)
 assert kind in ('FAILED','CANCELLED','CANCELED')
 live=Executions(S).get('afo-product-db4a6451b1d049d5966ddcc2')
 assert live['task_outcome']=='BLOCKED' and live['terminal_reason']=='OPERATOR_SHUTDOWN' and live['resource_lease']=='RELEASED'
 assert [x['order_id'] for x in S.orders(('RUNNING',))] in ([oid],[])
 projection=[]
 if old['state']=='RUNNING':projection=dispatch.reconcile_running(S,lambda:[{**native,'id':rid}],recover=None)
 if S.order(oid)['state']=='VALIDATING':
  S.transition(oid,'BLOCKED','Operator ten-hour window ended; native terminal, no final package; no recovery launched',terminal_reason='OPERATOR_SHUTDOWN')
 assert S.order(oid)['state']=='BLOCKED'
 after=MissionLedger(S).snapshot(mid);assert after==before
 out={'schema':'forge-c/owner-stop-queue-reconciliation/1','at':utc_now(),'operator_epoch':7,'native_id':rid,'native_status':kind,'order_before':{k:old[k] for k in ('order_id','state','terminal_reason')},'order_after':{k:S.order(oid)[k] for k in ('order_id','state','terminal_reason')},'projection':projection,'mission_before':before,'mission_after':after,'new_native_launches':0,'model_calls':0,'artifact_changes':False,'capacity_released_by_this_script':False,'classification':'OPERATOR_FIXED_WINDOW_STOP_NOT_MODEL_FAILURE','limits':'Administrative terminal projection after independently proven physical/native/request settlement; no package/verification fabricated'}
 p=E/'control/qualification-observations'/('owner-stop-queue-reconciliation-'+digest(out)+'.json');immutable_json(p,out)
print(json.dumps({'path':str(p),'sha256':sha256_file(p),'before':out['order_before'],'after':out['order_after'],'projection':projection,'model_calls':0,'mission_unchanged':before==after}))
