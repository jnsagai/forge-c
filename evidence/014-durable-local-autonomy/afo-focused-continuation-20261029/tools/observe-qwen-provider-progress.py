"""Readonly numeric slot/metric/GPU observations; never return prompt or generated text."""
from pathlib import Path
import json,os,subprocess,sys
P=Path('/mnt/data/forge-c/production-local-014')
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.lrtx import stack
from forge_factory.common import utc_now
s=stack.settings('local-rtx-v2-omniverse2-q38-afo-max-mtp')
code="""import json,urllib.request
result={}
for endpoint in ['slots','metrics']:
 try:
  raw=urllib.request.urlopen('http://127.0.0.1:11457/'+endpoint,timeout=5).read()
  if endpoint=='slots':
   slots=json.loads(raw);result['slot_numeric_timings']=[{k:v for k,v in (row.get('timings') or {}).items() if isinstance(v,(int,float,bool))} for row in slots];result['slot_field_names']=[sorted(row) for row in slots];result['slots']=[{k:v for k,v in row.items() if k in ['id','id_task','n_ctx','is_processing','n_past','n_decoded','n_predict','n_prompt_tokens','n_prompt_tokens_processed','state'] and isinstance(v,(int,float,bool,str))} for row in slots]
  else:
   result['metrics']=[line for line in raw.decode().splitlines() if line and not line.startswith('#') and any(k in line for k in ['tokens_predicted','tokens_generated','requests_processing','requests_deferred','predicted_tokens','prompt_tokens'])]
 except Exception as exc:result[endpoint+'_unavailable']=type(exc).__name__
print(json.dumps(result))
"""
r=subprocess.run(stack._nsenter(stack._holder(s))+[str(P/'venv/bin/python'),'-c',code],capture_output=True,text=True,timeout=15,check=True)
gpu=subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,power.draw','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
print(json.dumps({'at':utc_now(),'native':json.loads(r.stdout),'gpu_numeric':gpu.stdout.strip(),'model_requests':0,'generated_text_saved':False}))
