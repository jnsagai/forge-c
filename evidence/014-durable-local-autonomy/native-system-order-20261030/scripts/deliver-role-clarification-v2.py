from pathlib import Path
import json,sys,hashlib
N=Path('/mnt/data/forge-c/native-artifacts-014-20261030-v1');sys.path.insert(0,str(N/'source/factory/python'))
from forge_factory.fabro.client import FabroClient,load_token,run_status
from forge_factory.development_execution import selected
from forge_factory.afo.durable import immutable_json,immutable_bytes
from forge_factory.common import utc_now
launch=json.loads((N/'launch.json').read_text());ws=Path(launch['workspace'])
policy=selected(ws);assert policy['name']=='qm-pipeline-demonstration-repair-v2'
limit=policy['max_tool_calls_per_visit'];assert limit==10000
intent=json.loads(Path('/home/omniverse2/.local/state/forge-c-production-014/operations.json').read_text())
assert intent['mode']=='PAUSED' and intent['epoch']==111
base=N/'tool-clarification-role-v2';base.mkdir(exist_ok=True)
receipt=base/'receipt.json';record=base/'intent.json'
if receipt.exists():print(receipt.read_text());raise SystemExit(0)
if record.exists():raise RuntimeError('UNCERTAIN_PRIOR_DELIVERY_DO_NOT_RETRY')
message=(
'Role clarification to the previous administrative tool guidance: editing advice applies only when acting as an AUTHOR. '
'INSPECTORS remain read-only, examine the current baseline and submit honest findings with check_inspection; do not edit author artifacts. '
'Authors edit only their own assigned output paths using the exposed tools. The prior SWE.1 author path examples were not inspector write authority. '
'The selected QM demonstration policy allows10000 tool calls per visit for these roles; the old20-call and15th-call phrases are stale, not the active allowance. '
'Preserve every recorded failure and unresolved finding. No semantic answer, expected code, test result or PASS is supplied by this clarification. '
'Continue the role of your actual current node.'
)
assert len(message)<=8192
with FabroClient(base_url='http://127.0.0.1:32401',token=load_token(str(N/'fabro/storage')),timeout=25) as c:
 status=run_status(c.get_run(launch['native_id']));assert status=='RUNNING',status
 schema=c._http.get('/api/v1/openapi.json').json()
 assert '/api/v1/runs/{id}/steer' in schema['paths']
 immutable_bytes(base/'message.txt',message.encode())
 sha=hashlib.sha256(message.encode()).hexdigest()
 immutable_json(record,{'at':utc_now(),'native_id':launch['native_id'],'message_sha256':sha,
                       'actual_policy_tool_calls':limit,'runtime_source_revision':launch['source_revision'],
                       'prospective_prompt_fix':'f484459e','existing_scope_and_findings_preserved':True,
                       'scope_expanded':False,'reference_fix_supplied':False,'external_clarification':True})
 response=c._http.post('/api/v1/runs/'+launch['native_id']+'/steer',json={'text':message,'interrupt':False})
 immutable_bytes(base/'api-result.bin',response.content)
 result={'at':utc_now(),'native_id':launch['native_id'],'http_status':response.status_code,
         'status':'QUEUED_TOOL_CLARIFICATION' if response.status_code==202 else 'DELIVERY_FAILED_NO_AUTOMATIC_RETRY',
         'message_sha256':sha,'interrupt':False,'native_restarted':False,'new_native_runs':0,
         'external_clarification_not_autonomous_repair':True}
 immutable_json(receipt,result)
 print(json.dumps(result))

