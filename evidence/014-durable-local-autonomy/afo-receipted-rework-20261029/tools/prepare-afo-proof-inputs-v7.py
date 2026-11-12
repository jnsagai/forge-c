from pathlib import Path
import ast,hashlib,json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/afo-repair-live-20261029-v7'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.operations import Intent
from forge_factory.afo.durable import immutable_json,digest
from forge_factory.lrtx import stack
from forge_factory.common import utc_now
s=json.loads((O/'scope.json').read_text());assert Intent().read()['epoch']==46 and Intent().read()['mode']=='RUNNING'
settings=stack.settings(s['profile']);provider=stack.serving_instance(settings)
health=stack.status(settings)['health'];assert all(health.get(k) for k in ('fabro','gateway','ollama','llama_server')),health
code="import json,urllib.request; x=json.load(urllib.request.urlopen('http://127.0.0.1:11457/props',timeout=5)); print(json.dumps({'context':x.get('default_generation_settings',{}).get('n_ctx'),'slots':x.get('total_slots')}))"
r=subprocess.run(stack._nsenter(stack._holder(settings))+[str(P/'venv/bin/python'),'-c',code],capture_output=True,text=True,timeout=15,check=True)
assert json.loads(r.stdout)=={'context':262144,'slots':1}
a={'schema':'forge-c/context-allocation-probe/1','status':'PASS_ALLOCATION_ONLY','provider_context_tokens':262144,'provider_slot_count':1,'model_digest':s['model_digest'],'precision':'Q8_0','kv_precision':'f16','mtp_draft':3,'reasoning_effort':'xhigh','profile_sha256':s['profile_sha256'],'generation_requests':0,'at':utc_now(),'provider_instance':provider,'health':health}
if (O/'allocation.json').exists():
 old=json.loads((O/'allocation.json').read_text());assert old['provider_instance']==provider and old['profile_sha256']==s['profile_sha256']
else:immutable_json(O/'allocation.json',a)
paths=['factory/python/forge_factory/fabro/runconfig.py','factory/python/forge_factory/common.py']
rows=[]
for p in paths:
 raw=subprocess.check_output(['git','-C',str(R),'show',s['repair_baseline_revision']+':'+p]);tree=ast.parse(raw)
 symbols=[{'name':n.name,'line':n.lineno} for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
 rows.append({'path':p,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'top_level_symbols':symbols})
cat={'schema':'forge-c/baseline-source-catalog/1','source_revision':s['repair_baseline_revision'],'entries':rows,'basis':'Only exact original baseline paths, sizes, hashes and AST symbol names. No reference patch or verifier.','model_requests':0}
immutable_json(O/'baseline-source-catalog.json',cat)
incident={'source_catalog_baseline':s['repair_baseline_revision'],'source_catalog_sha256':digest(cat)}
for i,row in enumerate(rows):
 incident['source_catalog_file_'+str(i)]=row['path']+'; bytes='+str(row['bytes'])+'; sha256='+row['sha256']
 names=','.join(v['name']+'@'+str(v['line']) for v in row['top_level_symbols'])
 for j,start in enumerate(range(0,len(names),350)):incident['source_catalog_symbols_'+str(i)+'_'+str(j)]=names[start:start+350]
assert all(len(v)<=400 for v in incident.values());immutable_json(O/'incident-catalog-fields.json',incident)
print(json.dumps({'status':'FRESH_ALLOCATION_AND_BASELINE_CATALOG_FROZEN','files':len(rows),'model_requests':0,'deadline':s['deadline_utc']}))
