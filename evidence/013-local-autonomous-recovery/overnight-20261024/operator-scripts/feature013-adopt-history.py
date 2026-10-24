import json,hashlib
from pathlib import Path
from forge_factory.common import REPO_ROOT,state_dir,utc_now
from forge_factory.afo import policy,cli,dispatch,checkpoints
from forge_factory.afo.queue import Store
from forge_factory.fabro.client import client_for_workspace
root=state_dir()/'operator-runs/feature013'
items=[('WO-0008A-STM32N6-RCC-LL-q36c','01M5Q6Y9GQ6AVR1FJ5K6S9F73C'),('WO-0008A-STM32N6-RCC-LL-q36auto02','01M5QDK92JNCJD9SSCHWBJS6ZT'),('WO-0008A-STM32N6-RCC-LL-q36auto03','01M5QHW4PRS3GQ38N8ND38WC2Y'),('WO-0008A-STM32N6-RCC-LL-q36-n1','01M5QNBH2BDY55PPBMF195H6WG'),('WO-0008A-STM32N6-RCC-LL-q36-n2','01M5QPG9HT2SZW0PY5ZQSNE78X')]
verified=[]
for name,rid in items:
 ws=state_dir()/'workorders'/name/'workspace'
 mf=ws/'.forge-run/manifest.json';pkg=ws/'.forge-run/package.json'
 m=json.loads(mf.read_text());p=json.loads(pkg.read_text());run=client_for_workspace(ws,timeout=15).get_run(rid)
 run=run.get('data',run);kind=dispatch.run_kind(run)
 assert kind in dispatch.TERMINAL,(name,kind)
 assert m['work_order']==name,(name,m['work_order'])
 assert p['package_status']=='BLOCKED',(name,p['package_status'])
 verified.append(dict(work_order=name,run_id=rid,native_status=kind,package_status=p['package_status'],gap_count=p['gap_count'],manifest_sha256=hashlib.sha256(mf.read_bytes()).hexdigest(),package_sha256=hashlib.sha256(pkg.read_bytes()).hexdigest(),factory_revision=m['factory_revision']['commit'],original_created_utc=m['created_at'],original_finished_utc=p['finalized_at']))
eff=policy.load();assert eff.mode=='PILOT',eff
store=Store();env=json.loads((root/'work-order.json').read_text())
oid,created=store.submit(env,repo=REPO_ROOT,max_queued=100,approve=lambda env:cli.approve(env,eff))
assert created,'Refuse duplicate/partial historical import; inspect before continuing'
epoch=store.acquire_lease('scheduler','operator-historical-adoption',120);assert epoch
last=None
for i,v in enumerate(verified):
 if i==0:
  aid=store.admit(oid,epoch=epoch,scope='scheduler',policy_sha256=eff.sha256,authorization_id=eff.authorization_id,max_concurrent=1)
 else:
  store.transition(oid,'WAITING_RECOVERY','Historical receipt import only; no new model call or launch')
  aid=checkpoints.new_attempt(store,oid,plan_id='operator-import:feature013/adoption.json',epoch=epoch,max_attempts=6,source_wo=last)
 cmd=next(c for c in store.commands('PENDING') if c['attempt_id']==aid)
 store.attempt_transition(aid,'DISPATCH_PENDING',workspace_ref='workorder:'+v['work_order'],evidence_refs=['operator-history-import:feature013/adoption.json','manifest_sha256:'+v['manifest_sha256'],'original_created_utc:'+v['original_created_utc']])
 dispatch.adopt(store,cmd,v['run_id'],v['factory_revision'])
 if i < len(verified)-1:
  store.attempt_transition(aid,dispatch.TERMINAL[v['native_status']],exit_status=v['native_status'].lower(),terminal_package_status='BLOCKED',finished_utc=v['original_finished_utc'])
 with store.tx() as c:store._event(c,'operator_historical_receipt_adopted',oid,aid,{**v,'new_model_calls':0,'new_launches':0,'actor':'owner-authorized operator','reason':'Count all five existing attempts; preserve native immutable workspaces'})
 last=v['work_order']
record=dict(schema_version='1.0',recorded_utc=utc_now(),order_id=oid,source_revision='c008ba11d36e2e23b60c455115ac637a95cf7fd9',historical_attempts=verified,new_model_calls=0,new_launches=0,max_total_attempts=6,remaining_attempts=1,owner_authorization=eff.authorization_id,policy_sha256=eff.sha256)
(root/'adoption.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(dict(order_id=oid,state=store.order(oid)['state'],historical_attempts=len(verified),pending_launches=len(store.commands('PENDING')),remaining_attempts=1)))
