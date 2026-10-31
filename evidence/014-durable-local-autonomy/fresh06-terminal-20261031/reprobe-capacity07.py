from pathlib import Path
import os,sys,json,time
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1')
os.environ.update(json.loads((E/'control/runtime-env-v6.json').read_text()));sys.path.insert(0,str(E/'source/factory/python'))
from forge_factory.afo.queue import Store
from forge_factory.afo.operations import Intent
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.durable import immutable_json,digest
from forge_factory.afo import policy,authority
from forge_factory.common import utc_now,sha256_file
s=json.loads((E/'control/delivery-first-afo-authority-20261031-v4b/scope.json').read_text())
assert time.time()<s['deadline_epoch']
S=Store();L=MissionLedger(S);intent=Intent();eff=policy.load()
oid='afo-f83452175591716f'
before=L.snapshot(s['mission_id'])
with intent.lock():
 assert intent.read()['mode']=='RUNNING' and intent.read()['epoch']==6
 assert not Executions(S).pending(),'POSSIBLY_LIVE_EXECUTION_STILL_HELD'
 with S.tx() as c:
  holder=c.execute("SELECT holder FROM afo_resource_ownership WHERE resource='inference'").fetchone()
 assert holder and not holder[0]
 order=S.order(oid);assert order['state']=='QUEUED' and not S.attempts(oid)
 env=json.loads(order['envelope'])
 auth=authority.decide('recover_workorder',{'order_id':env['request_id'],'driver_class':'LL','model':s['model']},afo=eff)
 assert auth.allow,(auth.code,auth.reason if hasattr(auth,'reason') else '')
 old={k:order[k] for k in ('order_id','state','defer_count','not_before_epoch')}
 wait=S.defer(oid,'OWNER_REQUESTED_CAPACITY_REPROBE_AFTER_PROVEN_QUIESCENCE; SOURCE_AND_LIMITS_UNCHANGED',base_s=0,cap_s=0)
 assert wait==0
 after_order=S.order(oid)
 assert after_order['defer_count']==old['defer_count']+1
 assert after_order['manifest_sha256']==order['manifest_sha256']
 after=L.snapshot(s['mission_id']);assert after==before
record={'at':utc_now(),'kind':'EXTERNAL_BETWEEN_JOBS_ADMINISTRATIVE_REPROBE','order_id':oid,
 'before':old,'after':{k:after_order[k] for k in ('order_id','state','defer_count','not_before_epoch')},
 'reason':'Latest wait was NATIVE_INFERENCE_CAPACITY_HELD with3600s backoff; all native ownership now proven quiescent/released',
 'method':'Existing Store.defer withzero wait, preserving/incrementing defer history; ordinary Conductor rechecks all admission gates',
 'mission_before':before,'mission_after':after,'source_revision':s['source_revision'],'model':s['model'],
 'deadline_utc':s['deadline_utc'],'new_orders':0,'new_attempts_by_this_script':0,'model_calls_by_this_script':0,
 'native_signal_sent':False,'runtime_or_profile_changed':False,'factory_self_healing_claim':False}
path=E/'control/qualification-observations/cohort'/('capacity-reprobe-'+digest(record)+'.json');immutable_json(path,record)
print(json.dumps({'path':str(path),'sha256':sha256_file(path),'record':record}))

