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
base=N/'tool-clarification-v1';base.mkdir(exist_ok=True)
receipt=base/'receipt.json';record=base/'intent.json'
if receipt.exists():print(receipt.read_text());raise SystemExit(0)
if record.exists():raise RuntimeError('UNCERTAIN_PRIOR_DELIVERY_DO_NOT_RETRY')
message=(
'Owner-authorized development tool clarification; continue the same complete engineering scope and preserve all real findings. '
'The selected qm-pipeline-demonstration-repair-v2 policy allows '+str(limit)+' tool calls per visit; '
'the old workflow phrases about20 calls or submitting by the15th call are stale instructions, not the active allowance. '
'For existing artifacts, use edit_file or apply_patch directly on affected output files and retain other content. '
'The exposed native file tools write or patch text; they do not execute Python helpers, and shell/Python execution is not an exposed tool. '
'Writing /tmp/swe1_patch.py cannot perform the intended transformation through this tool surface. '
'Continue using the exposed direct-edit tools on your role output paths (workproducts/SWE.1 and traceability). '
'Complete the actual deterministic verification and report unresolved issues honestly. '
'The compact result next_action must be a literal next, rework, halt, package, escalate, none or retry; explanations go in issues. '
'No reference engineering repair or expected test values are supplied. This is external clarification of tool/policy facts, not an autonomous model discovery.'
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

