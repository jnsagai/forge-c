"""Start the existing Conductor for the enrolled, finite, signed development scope."""
from pathlib import Path
import os,sys,json,time
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1');Q=E/'source'
env=json.loads((E/'control/runtime-env-v5.json').read_text());os.environ.update(env);sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.afo import policy
from forge_factory.afo.operations import Intent,fenced_call
from forge_factory.afo.queue import Store
from forge_factory.lrtx import stack
from forge_factory.afo.durable import immutable_json
from forge_factory.common import utc_now
scope=json.loads((E/'control/delivery-first-afo-authority-20261030-v3/scope.json').read_text())
assert time.time()<scope['deadline_epoch']
assert not (E/'control/conductor-v3.json').exists(),'EXISTING_HANDLE_MUST_BE_RECONCILED'
assert Store().order(scope['order_id'])['state']=='QUEUED'
assert policy.load().sha256==scope['policy_sha256']
assert Intent().read()['mode']=='RUNNING' and Intent().read()['epoch']==4
settings=stack.settings(scope['profile']);holder=json.loads((E/'run/services.json').read_text())['holder_pid']
argv=[str(E/'venv/bin/python'),'-m','forge_factory.afo.conductor','--interval','15']
proc=fenced_call(4,lambda:stack._in_ns(holder,argv,env,E/'logs/conductor.log',Q))
until=time.monotonic()+5
identity=None
while time.monotonic()<until:
 identity=stack.process_identity(proc.pid)
 if identity and identity['netns']==json.loads((E/'run/services.json').read_text())['netns']:break
 time.sleep(.05)
assert identity and proc.poll() is None
rec={'at':utc_now(),'pid':proc.pid,'identity':identity,'argv':argv,'source_revision':scope['source_revision'],
 'scope_order_id':scope['order_id'],'operations_epoch':4,'deadline_utc':scope['deadline_utc'],
 'implementation':'EXISTING_AFO_CONDUCTOR_MODULE','native_launch':'EXISTING_SCHEDULER_AND_OUTBOX',
 'model_requests':'OBSERVE_REQUEST_LEDGER; NOT_INFERRED_FROM_PROCESS_START'}
immutable_json(E/'control/conductor-v3.json',rec)
print(json.dumps(rec))

