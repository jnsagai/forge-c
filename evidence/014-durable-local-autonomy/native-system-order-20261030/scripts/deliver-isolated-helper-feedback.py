
from pathlib import Path
import sys,json,hashlib
N=Path('/mnt/data/forge-c/native-artifacts-014-20261030-v1');sys.path.insert(0,str(N/'source/factory/python'))
from forge_factory.fabro.client import FabroClient,load_token,run_status
from forge_factory.afo.durable import immutable_json,immutable_bytes
from forge_factory.common import utc_now
d=json.loads((N/'launch.json').read_text());out=N/'helper-feedback-v1';out.mkdir(exist_ok=True)
receipt=out/'receipt.json';intent=out/'intent.json'
if receipt.exists():print(receipt.read_text());raise SystemExit(0)
if intent.exists():raise RuntimeError('UNCERTAIN_PRIOR_DELIVERY')
with FabroClient(base_url='http://127.0.0.1:32401',token=load_token(str(N/'fabro/storage')),timeout=20) as c:
 es=list(c.iter_events(d['native_id']));active=[e.get('node_id') for e in es if e['event']=='stage.started'][-1]
 if active!='swe1_author' or run_status(c.get_run(d['native_id']))!='RUNNING':
  print(json.dumps({'status':'NOT_DELIVERED_PHASE_CHANGED','node':active}));raise SystemExit(0)
 msg=('Execution feedback for your own previously proposed /tmp/swe1_patch.py, SHA256 '
 '3f1fdd369838180a37a59fde9caa98fd57f201639381505a3f61d942dd0e0e68: '
 'an external diagnostic executed the exact script against isolated copies of the four seed artifacts, '
 'without modifying your workspace or supplying reference implementation code. It exited1 in33.6ms, '
 'before any artifact changes. stdout: existing SWRs:642; gaps:4. Error at line186: TypeError: '
 'not all arguments converted during string formatting. Your proposed format string has fewer placeholders '
 'than the arguments you supplied. This is real failing execution feedback, not a new review verdict. '
 'No Python execution tool has been added to your current role. For this rework retain the existing '
 'requirements and repair only the complete original INS-SWE.1-001 finding using direct edit_file/apply_patch. '
 'Finish the honest compact result after actual checks so the deterministic author gate can generate ReqIF. '
 'Repeated analysis without an artifact edit is not a repair. Do not fabricate a PASS or change inspection evidence.')
 immutable_bytes(out/'message.txt',msg.encode());sha=hashlib.sha256(msg.encode()).hexdigest()
 immutable_json(intent,{'at':utc_now(),'native_id':d['native_id'],'message_sha256':sha,'external_diagnostic':True})
 r=c._http.post('/api/v1/runs/'+d['native_id']+'/steer',json={'text':msg,'interrupt':False})
 rec={'at':utc_now(),'http_status':r.status_code,'native_id':d['native_id'],'message_sha256':sha,'interrupt':False,
 'live_artifacts_changed_by_external_helper':False,'external_intervention':True,'model_authored_helper_exit_code':1}
 immutable_json(receipt,rec);print(json.dumps(rec))

