from pathlib import Path
import json,os,sys,subprocess
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1')
os.environ.update(json.loads((E/'control/runtime-env-v6.json').read_text()));sys.path.insert(0,str(E/'source/factory/python'))
from forge_factory.fabro.client import FabroClient,load_token
from forge_factory.mcp.sdk import args_digest
from forge_factory.mcp.servers.evidence import DefectIn
from forge_factory.afo.durable import digest,immutable_json
from forge_factory.common import sha256_file,utc_now
rid='01M6855WHNYHGCV6PFB5HPHAVH';tool='mcp__forge_evidence_mcp__report_defect'
starts={};calls=[]
with FabroClient(base_url='http://127.0.0.1:32404/api/v1',token=load_token(str(E/'fabro/storage')),timeout=15) as c:
 for e in c.iter_events(rid):
  d=(e.get('properties') or {}).get('event',{})
  if e['event']=='agent.tool.started':
   t=d['ToolCallStarted']
   if t.get('tool_name')==tool:starts[t['tool_call_id']]=t['arguments']
  if e['event']=='agent.tool.completed':
   t=d['ToolCallCompleted']
   if t.get('tool_name')!=tool or not e.get('node_id','').startswith('swe5'):continue
   raw=starts[t['tool_call_id']];expanded=DefectIn.model_validate(raw).model_dump()
   v=json.loads(t['output'])
   if 'content' in v:v=json.loads(next(x['text'] for x in v['content'] if x.get('type')=='text'))
   calls.append({'at':e['ts'],'node':e['node_id'],'status':v.get('status'),'issues':v.get('issues'), 'argument_keys':sorted(raw),'injected_factory_fields':[k for k,f in DefectIn.model_fields.items() if k not in raw and f.default_factory in (list,dict)],'hook_digest':args_digest(tool,raw),'expanded_digest':args_digest(tool,expanded),'hashes_equal':args_digest(tool,raw)==args_digest(tool,expanded),'event_sha256':digest(e)})
ws=E/'state/workorders/WO-AFO-f83452175591716f-a1/workspace'
history=[json.loads(l) for l in (ws/'evidence/test-integrity.jsonl').read_text().splitlines() if l.strip()]
history=[x for x in history if x.get('phase')=='SWE.5']
out={'schema':'forge-c/native-defect-ticket-diagnosis/1','at':utc_now(),'native_id':rid,'source_revision':subprocess.check_output(['git','-C',str(E/'source'),'rev-parse','HEAD'],text=True).strip(),'declaration_calls':calls,'target_integrity_history':history,'candidate_sha256':sha256_file(ws/'software/ll/stm32n6xx_ll_crc.h'),'model_calls_by_observer':0,'candidate_execution_by_observer':False,'workspace_written_by_observer':False,'limits':'Captured native tool failures and read-only runtime argument hashes; no declaration/repair incident or new model/test execution created.'}
p=E/'control/qualification-observations/cohort/afo-f83452175591716f'/('defect-ticket-diagnosis-'+digest(out)+'.json');immutable_json(p,out)
print(json.dumps({'path':str(p),'sha256':sha256_file(p),'declaration_calls':calls,'target_integrity_history':history}))
