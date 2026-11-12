"""Finite qualification window using existing intent, cancellation and provider reconciliation."""
from pathlib import Path
import argparse,json,os,sys,time
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1')
p=argparse.ArgumentParser();p.add_argument('--run',action='store_true');a=p.parse_args()
env=json.loads((E/'control/runtime-env-v5.json').read_text());os.environ.update(env);sys.path.insert(0,str(E/'source/factory/python'))
from forge_factory.afo import operations
from forge_factory.afo.queue import Store
from forge_factory.afo.durable import immutable_json,Refused
from forge_factory.fabro.client import FabroClient,load_token
from forge_factory.common import utc_now
scope=json.loads((E/'control/delivery-first-afo-authority-20261030-v3/scope.json').read_text())
deadline=scope['deadline_epoch'];assert scope['deadline_utc']=='2026-10-31T07:57:59Z'
expected_epoch=4
monotonic_end=time.monotonic()+max(0,deadline-time.time())
intent=operations.Intent()
if not a.run:
 print(json.dumps({'status':'PREPARED_NOT_RUNNING','deadline_utc':scope['deadline_utc'],'expected_epoch':expected_epoch,'model_requests':0}))
 raise SystemExit(0)
immutable_json(E/'control/window-guard-start.json',{'at':utc_now(),'pid':os.getpid(),'deadline_utc':scope['deadline_utc'],
 'expected_operations_epoch':expected_epoch,'scope':'EXISTING_QUALIFICATION_RUNTIME_ONLY','model_requests':0})
while True:
 rec=intent.read()
 if rec['mode']=='STOPPED':break
 if rec['epoch']!=expected_epoch:
  immutable_json(E/'control/window-guard-fenced.json',{'at':utc_now(),'reason':'NEWER_OPERATOR_INTENT',
   'observed_mode':rec['mode'],'observed_epoch':rec['epoch'],'model_or_native_signal_sent':False})
  raise SystemExit(0)
 remaining=min(deadline-time.time(),monotonic_end-time.monotonic())
 if remaining<=0:
  try:
   operations.synchronize(Store(),'shutdown','jnsagai-delegated-10h-window',
    'Owner-requested ten-hour inference window ended; no grant renewal',expected_epoch=expected_epoch)
  except Refused as exc:
   immutable_json(E/'control/window-guard-fenced.json',{'at':utc_now(),'reason':exc.code,'model_or_native_signal_sent':False})
   raise SystemExit(0)
  break
 time.sleep(min(15,max(.1,remaining)))
def no_unrelated_unit(args):
 raise Refused('QUALIFICATION_HAS_NO_SYSTEMD_UNIT_ACTION',str(args))
attempts=[]
with FabroClient(base_url='http://127.0.0.1:32404',token=load_token(str(E/'fabro/storage')),timeout=10) as client:
 for i in range(120):
  if intent.read()['mode']!='STOPPED':
   immutable_json(E/'control/window-end-fenced.json',{'at':utc_now(),'reason':'NEWER_OPERATOR_INTENT'})
   raise SystemExit(0)
  try:
   result=operations.settle_shutdown(Store(),external=True,client=client,stop_runner=no_unrelated_unit)
   attempts.append({'at':utc_now(),'result':result})
   if result['settled']:
    immutable_json(E/'control/window-end.json',{'at':utc_now(),'deadline_utc':scope['deadline_utc'],
     'settled':True,'attempts':attempts,'renewed':False})
    raise SystemExit(0)
  except (Refused,OSError,ValueError) as exc:
   attempts.append({'at':utc_now(),'error':getattr(exc,'code',type(exc).__name__)})
  time.sleep(5)
immutable_json(E/'control/window-end.json',{'at':utc_now(),'deadline_utc':scope['deadline_utc'],
 'settled':False,'attempts':attempts,'renewed':False,'state':'REQUIRES_RECONCILIATION_NO_NEW_INFERENCE'})

