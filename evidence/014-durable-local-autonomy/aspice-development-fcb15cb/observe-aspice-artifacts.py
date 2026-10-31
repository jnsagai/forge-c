from pathlib import Path
import os,sys,json,hashlib,subprocess
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#'):
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.queue import Store
from forge_factory.inspection.engine import Store as Inspections,PHASES
from forge_factory.lrtx import swe1
from forge_factory.assurance.hardware import index
from forge_factory.common import utc_now
expected_source='fcb15cba0bbc1b5e6e7c91c86aba08db244b5c61'
actual_source=subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()
dirty=subprocess.check_output(['git','-C',str(R),'status','--porcelain'],text=True).strip()
if actual_source!=expected_source or dirty:
 raise RuntimeError('OBSERVER_RUNTIME_SOURCE_CHANGED_USE_THE_PINNED_SOURCE')
S=Store();oid='afo-533cd9ba25e792a5';attempts=S.attempts(oid);observations=[]
for attempt in attempts:
 ws=P/'state/workorders'/('WO-AFO-'+oid.removeprefix('afo-')+'-a'+str(attempt['seq']))/'workspace'
 if not (ws/'.forge-run/manifest.json').is_file():continue
 m=json.loads((ws/'.forge-run/manifest.json').read_text());inv=swe1.inventory(ws)
 groups={f"requirements:{g['id']}":g for g in swe1.groups(inv)};idx=index(ws / "inputs/sections/RM0486");sysname=swe1.system_name(ws)
 packets=[]
 for path in sorted((ws/'.forge-run/lrtx/SWE.1/packets').glob('*.json')):
  try:d=json.loads(path.read_text())
  except (OSError,ValueError):continue
  doc=d.get('doc') or {};task=d.get('task');errs=[]
  if d.get('status')=='VALID' and str(task).startswith('requirements:'):
   errs=swe1.validate_group(ws,doc,groups.get(task),sysname,idx)
  packets.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
   'task':task,'status':d.get('status'),'inspection_verdict':doc.get('verdict'),'inspection_finding_count':len(doc.get('findings',[])),'requirements':len(doc.get('requirements',[])),
   'effects':sum(len(r.get('effects',[])) for r in doc.get('requirements',[])),
   'effect_fields':sorted({e.get('register','')+'.'+e.get('field','') for r in doc.get('requirements',[]) for e in r.get('effects',[])}),
   'excluded_fields':[x.get('field') for x in doc.get('not_covered',[])],
   'attempt_results':[{'n':x.get('n'),'wall_ms':x.get('wall_ms'),'usage':x.get('usage'),'errors':x.get('errors',[])} for x in d.get('attempts',[])],
   'recorded_error_count':len(d.get('errors',[])),'recomputed_local_finding_codes':[e.split(':',1)[0] for e in errs]})
 st=Inspections(ws);phases=[]
 for phase in PHASES:
  baselines=st.baselines(phase);ins=st.inspections(phase)
  phases.append({'phase':phase,'baseline_count':len(baselines),
   'latest_baseline':{k:baselines[-1].get(k) for k in ['baseline_id','baseline_hash','frozen_at']} if baselines else None,
   'inspection_count':len(ins),'latest_inspection':{k:ins[-1].get(k) for k in ['inspection_id','verdict','stale_reason']} if ins else None,
   'gate':{k:v for k,v in st.gate(phase).items() if k in ['decision','reason','baseline_id','inspection_id']}})
 observations.append({'attempt_id':attempt['attempt_id'],'purpose':m.get('purpose'),'profile':m.get('local_profile'),
  'fresh_recovery_from':m.get('fresh_recovery_from'),'required_group_count':len(groups),'packets':packets,'phases':phases,
  'safeC_outputs_present':[(ws/p).exists() for p in ['workproducts/SWE.1/register_obligations.json','workproducts/SWE.1/register_oracle.json']]})
print(json.dumps({'at':utc_now(),'observations':observations,'scope':'READ_ONLY_PARTIAL_ARTIFACT_METADATA_NOT_PRODUCT_QUALIFICATION'}))
