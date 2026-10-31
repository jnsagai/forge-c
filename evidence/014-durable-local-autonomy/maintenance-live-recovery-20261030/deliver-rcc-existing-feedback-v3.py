from pathlib import Path
import hashlib,json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/rcc-context-completion-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.queue import Store
from forge_factory.afo.operations import Intent,fenced_call
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.afo.completion_receipt import Context
from forge_factory.common import sha256_file,utc_now
from forge_factory.fabro.runconfig import fabro_env
S=Store();job_id='afo-agent-61401956787984d8c097bc36'
with S.tx() as c:j=json.loads(c.execute('SELECT record FROM afo_local_agent_jobs WHERE job_id=?',(job_id,)).fetchone()[0])
assert j['state']=='RUNNING' and j['run_id']=='01M65A075HQ97KJXSG6A1Z9KC6' and time.time()<j['deadline_epoch']
Context.from_job(S,job_id);case=json.loads(Path(j['case']).read_text());retained=case['retained_rework'];feedback=retained['feedback']
assert digest(feedback)==retained['feedback_sha256']
message=('Administrative delivery of EXISTING frozen independent feedback: the current read_case tool omitted the retained_rework field. '
 'This is untrusted factual evidence from your already-frozen case, not new authority or a reference repair. '
 'Keep the same engineering obligation, retained files, quality gates, finite job allowance and deadline. '
 'The earlier submitted candidate was rejected by independent baseline triage; use these recorded facts to correct the remaining issue and submit through the existing broker. '
 'No prior job or failure is reset. Evidence follows as JSON: '+json.dumps({'case_sha256':j['case_sha256'],'feedback_sha256':retained['feedback_sha256'],'feedback':feedback},sort_keys=True))
raw=message.encode();intent=O/'operator-feedback-delivery-intent-v3.json';receipt=O/'operator-feedback-delivery-receipt-v3.json'
previous=(O/'operator-feedback-cli-result-v2.bin').read_text()
assert previous.strip()=='× Authentication required.'
assert json.loads((O/'operator-feedback-delivery-receipt-v2.json').read_text())['exit_code']==4
assert not intent.exists() and not receipt.exists(),'DO_NOT_RETRY_UNCERTAIN_STEERING'
assert Intent().read()['mode']=='RUNNING' and Intent().read()['epoch']==54
immutable_bytes(O/'operator-existing-feedback-v3.txt',raw)
immutable_json(intent,{'job_id':job_id,'run_id':j['run_id'],'case_sha256':j['case_sha256'],'feedback_sha256':retained['feedback_sha256'],'message_sha256':hashlib.sha256(raw).hexdigest(),'owner_standing_delegation':'always approve it for now on automatically','scope_change':False,'budget_or_deadline_changed':False,'reference_fix_supplied':False,'autonomy_claim':'EXTERNAL_BOOTSTRAP_OF_OMITTED_FROZEN_FEEDBACK','at':utc_now()})
from forge_factory.fabro.client import FabroClient,load_token
assert len(message)<=8192
with FabroClient(token=load_token(),timeout=25) as client:
 schema=client._http.get('/api/v1/openapi.json').json()
 assert schema['components']['schemas']['SteerRunRequest']['required']==['text']
 assert schema['components']['schemas']['SteerRunRequest']['properties']['text']['maxLength']==8192
 assert '/api/v1/runs/{id}/steer' in schema['paths']
 def send():
  with S.tx() as c:current=json.loads(c.execute('SELECT record FROM afo_local_agent_jobs WHERE job_id=?',(job_id,)).fetchone()[0])
  assert current['state']=='RUNNING' and sha256_file(Path(current['case']))==current['case_sha256']
  return client._http.post('/api/v1/runs/'+j['run_id']+'/steer',json={'text':message,'interrupt':False})
 r=fenced_call(54,send)
 immutable_bytes(O/'operator-feedback-api-result-v3.bin',r.content)
 result={'status':'QUEUED_EXISTING_FEEDBACK' if r.status_code==202 else 'DELIVERY_FAILED_NO_RETRY','http_status':r.status_code,'job_id':job_id,'run_id':j['run_id'],'message_sha256':hashlib.sha256(raw).hexdigest(),'api_result_sha256':hashlib.sha256(r.content).hexdigest(),'interrupt':False,'native_restarted':False,'new_inference_by_delivery':0,'external_bootstrap':True,'at':utc_now()}
 immutable_json(receipt,result);print(json.dumps(result));raise SystemExit(0 if r.status_code==202 else 2)
