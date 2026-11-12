from pathlib import Path
import json,sys,hashlib
P=Path('/mnt/data/forge-c/production-local-014');ws=P/'state/workorders/WO-AFO-774900b297bdde37-a1/workspace'
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.inspection.engine import Store
from forge_factory.common import utc_now
store=Store(ws);baseline=store.latest_baseline('SWE.3')
gates=[]
for line in (ws/'.forge-run/gates/gate-log.jsonl').read_text().splitlines():
 rec=json.loads(line)
 if rec.get('phase')=='SWE.3':
  gates.append({k:v for k,v in rec.items() if k in ('phase','step','check','verdict','result','delivery','code_mode','code_findings','conformance_findings','errors','issues','missing','baseline_id')})
tools=[]
p=ws/'evidence/tool-results.jsonl'
if p.exists():
 for line in p.read_text().splitlines():
  rec=json.loads(line)
  if rec.get('phase')=='SWE.3':
   result=rec.get('result') or {}
   tools.append({'at':rec.get('ts_utc'),'server':rec.get('server'),'op':rec.get('op'),'role':rec.get('role'),
    'status':result.get('status'),'issues':result.get('issues'),
    'summary':result.get('summary'),'provenance':result.get('provenance'),'artifact_refs':result.get('artifact_refs'),'metric_fields':list((result.get('metrics') or {}).keys()),'measured_dimensions':{k:v for k,v in (result.get('metrics') or {}).items() if isinstance(v,(int,float,bool)) or (k=='scope' and isinstance(v,str) and len(v)<256)}})
build=[{'path':str(p.relative_to(ws)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
 for p in sorted((ws/'build/target-cm55-gcc').rglob('*')) if p.is_file()]
print(json.dumps({'at':utc_now(),'phase':'SWE.3','baseline':baseline,
 'current_baseline':bool(baseline and baseline['baseline_hash']==store.current_hash('SWE.3')),
 'gate':store.gate('SWE.3'),'gates':gates,'tools':tools,'build_files':build,
 'read_only':True,'generation_requests':0},indent=2))
