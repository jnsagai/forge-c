from pathlib import Path
import os,sys,subprocess,json
P=Path('/mnt/data/forge-c/production-local-014')
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.lrtx import stack
s=stack.settings('local-rtx-v2-omniverse2-q38-afo-repair-mtp')
code='''import urllib.request,json
u=urllib.request.Request('http://127.0.0.1:11455/api/show',data=json.dumps({'model':'qwen3.8:27b-q8_0'}).encode(),headers={'Content-Type':'application/json'})
x=json.load(urllib.request.urlopen(u,timeout=20));m=x.get('model_info',{});print(json.dumps({'model_info':{k:v for k,v in m.items() if any(s in k for s in ('context_length','architecture','embedding_length','block_count','head_count'))},'details':x.get('details')}))'''
r=subprocess.run(stack._nsenter(stack._holder(s))+[str(P/'venv/bin/python'),'-c',code],capture_output=True,text=True,timeout=30,check=True)
print(r.stdout);print(json.dumps({'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=memory.total,memory.used,memory.free','--format=csv,noheader'],text=True).strip(),'generation_requests':0}))
