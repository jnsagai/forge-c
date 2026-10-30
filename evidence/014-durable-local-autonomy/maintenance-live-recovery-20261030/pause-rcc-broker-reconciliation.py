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
with S.tx() as c:j=json.loads(c.execute('SELECT record FROM afo_local_agent_jobs WHERE job_id=?',(jid,)).fetchone()[0])
assert j['state']=='RUNNING' and j['run_id']=='01M65A075HQ97KJXSG6A1Z9KC6'
case=json.loads(Path(j['case']).read_text());intent=json.loads((Path(j['case']).parent/'submission-intent.json').read_text())
assert digest(intent)=='1fac9374b0f7ccaa85b36991569188e78de6b9a7f46293d9018d59ad668d6881'
actual=subprocess.check_output(['git','-C',case['src'],'show','-s','--format=%P%n%T%n%B','HEAD'],text=True).strip().split('\n',2)
assert actual==[intent['parent'],intent['tree'],intent['message'].rstrip(' ')] and actual[2]!=intent['message']
with I.lock():
 assert I.read()['mode']=='RUNNING' and I.read()['epoch']==54
 for unit in ('forge-afo-watchdog-014-omniverse2.timer','forge-afo-watchdog-014-omniverse2.service',operations.UNIT):
  subprocess.run(['systemctl','--user','stop',unit],check=True,timeout=45)
operations.synchronize(S,'pause',str(os.getuid()),'Owner-directed maintenance under standing approval and stop/rethink instruction: sealed Qwen commit differs only in Git-trimmed trailing space; preserve existing effect and qualify deterministic broker reconciliation',expected_epoch=54,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
with I.lock():
 assert I.read()['mode']=='PAUSED' and I.read()['epoch']==55
 with FabroClient(token=load_token(),timeout=10) as client:
  state=Executions(S).reconcile(jid,client,cancel=True)
 immutable_json(O/'broker-maintenance-pause-v1.json',{'status':'AUTHENTICATED_OPERATOR_MAINTENANCE_PAUSE','operator_epoch':55,'job_id':jid,'run_id':j['run_id'],'intent_sha256':digest(intent),'candidate':'b64f64daf03aec12d72a5513fa322426cf9c93bd','cause':'GIT_REMOVED_TRAILING_MESSAGE_SPACE_AFTER_HASH_BOUND_COMMIT','parent_and_tree_match':True,'job_state_not_rewritten':True,'native_cancellation_requested':True,'execution':state,'provider_stopped':False,'budget_or_deadline_changed':False,'owner_standing_delegation':'always approve it for now on automatically','at':utc_now()})
 print(json.dumps({'status':'PAUSED_FOR_QUALIFIED_BROKER_RECOVERY','operator_epoch':55,'native_liveness':state['execution_liveness'],'lease':state['resource_lease'],'at':utc_now()}))
