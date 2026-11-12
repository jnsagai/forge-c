from pathlib import Path
import sys,json,hashlib
N=Path('/mnt/data/forge-c/native-artifacts-014-20261030-v1');sys.path.insert(0,str(N/'source/factory/python'))
from forge_factory.fabro.client import FabroClient,load_token,run_status
from forge_factory.mcp.servers.evidence import _ITEM
from forge_factory.afo.durable import immutable_json,immutable_bytes
from forge_factory.common import utc_now
d=json.loads((N/'launch.json').read_text());ws=Path(d['workspace']);original=ws/'inspection/SWE.1/INS-SWE.1-001.json'
inspection=json.loads(original.read_text());out=N/'native-full-feedback-v1';out.mkdir(exist_ok=True)
with FabroClient(base_url='http://127.0.0.1:32401',token=load_token(str(N/'fabro/storage')),timeout=20) as c:
 es=list(c.iter_events(d['native_id']))
 candidates=[]
 for e in es:
  if e['event']!='agent.tool.started':continue
  t=((e.get('properties') or {}).get('event') or {}).get('ToolCallStarted',{})
  if t.get('tool_name')!='mcp__forge_evidence_mcp__check_inspection':continue
  a=t.get('arguments') or {}
  if isinstance(a,str):a=json.loads(a)
  if a.get('phase')=='SWE.1' and a.get('baseline_id')=='BL-SWE.1-001':candidates.append((t,a))
 assert candidates
 t,a=candidates[0];raw=a['verdicts'];assert isinstance(raw,str)
 hits=list(_ITEM.finditer(raw));notes={}
 for i,m in enumerate(hits):
  if m.group(2).upper() not in ('FAIL','FAILED','REWORK','REJECT','REJECTED','NOK','NOT_OK'):continue
  end=hits[i+1].start() if i+1<len(hits) else len(raw)
  note=raw[m.end():end].strip().lstrip(':').strip().rstrip(';.,').strip();item=m.group(1).upper()
  if inspection['items'][item].get('source')=='deterministic':continue
  stored=inspection['items'][item]['findings'][0]
  assert note[:120]==stored,(item,len(note),len(stored))
  notes[item]={'full_original_finding':note,'stored_chars':len(stored),'full_chars':len(note),'stored_prefix_matches':True}
 payload={'at':utc_now(),'inspection_id':'INS-SWE.1-001','original_inspection_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
          'original_verdict_argument_sha256':hashlib.sha256(raw.encode()).hexdigest(),'native_call_id':t['tool_call_id'],
          'findings':notes,'original_record_rewritten':False,'source':'RECOVERED_ORIGINAL_INSPECTOR_SUBMISSION_NOT_NEW_SEMANTIC_REVIEW'}
 immutable_json(out/'recovered-findings.json',payload)
 receipt=out/'delivery-receipt.json';intent=out/'delivery-intent.json'
 if receipt.exists():print(receipt.read_text());raise SystemExit(0)
 if intent.exists():raise RuntimeError('UNCERTAIN_PRIOR_FEEDBACK_DELIVERY_DO_NOT_RETRY')
 active=[e.get('node_id') for e in es if e['event']=='stage.started'][-1]
 if active!='swe1_author' or run_status(c.get_run(d['native_id']))!='RUNNING':
  print(json.dumps({'status':'RECOVERED_NOT_DELIVERED_PHASE_CHANGED','active_node':active,'findings':notes}));raise SystemExit(0)
 message=('Existing independent inspection feedback was truncated by the native flat-verdict parser at120characters. '
 'The original INS-SWE.1-001 remains unchanged. Recover its complete originally submitted FAIL finding below; '
 'verify it against your baseline and correct only the affected authored outputs. This is the original inspector statement, '
 'not a new reference answer or an altered verdict. '
 'Procedural fact: the deterministic SWE.1 author gate generates software_requirements.reqif from the markdown. '
 'After your assigned edits and actual checks, return the compact JSON with an honest status so that gate executes; '
 'ReqIF generation does not require searching factory source or executing a Python helper. Recovered original finding: '+json.dumps(notes,sort_keys=True))
 assert len(message)<8192
 immutable_bytes(out/'message.txt',message.encode())
 sha=hashlib.sha256(message.encode()).hexdigest()
 immutable_json(intent,{'at':utc_now(),'message_sha256':sha,'native_id':d['native_id'],'original_feedback_only':True,'external_delivery':True})
 response=c._http.post('/api/v1/runs/'+d['native_id']+'/steer',json={'text':message,'interrupt':False})
 result={'at':utc_now(),'http_status':response.status_code,'message_sha256':sha,'native_id':d['native_id'],'interrupt':False,
         'original_inspection_rewritten':False,'reference_engineering_fix_supplied':False,'external_delivery_not_autonomous_recovery':True,
         'recovered_item_ids':list(notes)}
 immutable_json(receipt,result);print(json.dumps(result))

