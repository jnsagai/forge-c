"""Frozen operator reproducer from native planner 01M5QTF2X5M4WMSFKXPJ6KRHEJ; makes no model calls."""
import json,sys,time,tempfile,hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
SIG='planner schema limits disappear and native success lacks validated output'
def main():
 from forge_factory.afo import contracts,local_agent as L,recovery
 from forge_factory.mcp.servers.afo import PlanIn
 # Same shape/length failure as the two native rejected submissions; use public deterministic fixtures.
 b=dict(order_id='afo-fixture',attempt_id='afo-fixture-a5',fingerprint='fixture',phase='SWE.3')
 p=recovery._base(b,'REWORK_LOCAL','SWE.3','R'*201,material_difference_ref='M'*201)
 errors=[x[:120] for x in contracts.errors('recovery-plan',p)]
 limits=all('maxLength=200' in x and 'actual_length=201' in x for x in errors) and len(errors)==2
 tool=PlanIn.model_json_schema()['properties']['plan_json'].get('description','')
 limits=limits and '200 characters' in tool and 'tokens_max' in tool
 with tempfile.TemporaryDirectory() as tmp:
  d=Path(tmp);case=d/'case.json';case.write_text('{}')
  job=dict(job_id='afo-agent-'+'1'*24,role='afo-recovery-planner',state='RUNNING',run_id='R1',model='qwen3.6:35b-a3b',policy_sha256='a'*64,deadline_epoch=time.time()+60,case=str(case),case_sha256=hashlib.sha256(case.read_bytes()).hexdigest(),reserved_tokens=16000,reported_tokens=None)
  eff=SimpleNamespace(sha256='a'*64,mode='PILOT',get=lambda *args:True)
  client=SimpleNamespace(get_run=lambda _:dict(lifecycle=dict(status=dict(kind='SUCCEEDED'))),usage=lambda _:dict(stages=[]))
  with patch.object(L,'authorized',return_value=True),patch.object(L,'save'),patch.object(L,'directory',return_value=d):
   result=L.poll(None,{},job,eff,client=client)
  strict=result['state']=='FAILED' and result.get('error')=='LOCAL_AGENT_OUTPUT_MISSING_OR_INVALID'
 if not(limits and strict):
  print('SYMPTOM_PRESENT:'+SIG);return 1
 print('SYMPTOM_ABSENT');return 0
if __name__=='__main__':
 try:sys.exit(main())
 except Exception as e:print('REPRODUCER_ERROR:'+type(e).__name__+':'+str(e)[:160]);sys.exit(2)
