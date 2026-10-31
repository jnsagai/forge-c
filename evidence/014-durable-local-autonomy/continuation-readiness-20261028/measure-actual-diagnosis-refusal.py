from pathlib import Path
import os,sys,json
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#'):
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.common import state_dir,utc_now
from forge_factory.afo.durable_agent import request_material
from forge_factory.afo.diagnosis_packet import load
from forge_factory.afo.semantic_proposal import two_step
from forge_factory.lrtx.profile import load as profile
from forge_factory.registry.agents import load_agents
from forge_factory.lrtx.profile import role_job_tokens
ws=state_dir()/'workorders/WO-AFO-533cd9ba25e792a5-a1/workspace'
man=json.loads((ws/'.forge-run/manifest.json').read_text());rows=[]
for case in (state_dir()/'afo/cases').glob('*/case.json'):
 doc=json.loads(case.read_text())
 if doc.get('bundle',{}).get('attempt_id')!='afo-533cd9ba25e792a5-a1' or not doc.get('packet_ref'):continue
 p=load(doc['packet_ref']); selected=sorted(p['obligations'])[:1]
 job={'case':str(case),'model':'qwen3.8:27b-q8_0','profile':man['local_profile']['id'],'role':'afo-recovery-planner',
 'selected_obligations':selected,'role_capabilities':man.get('role_capabilities') or {}}
 prof=profile(job['profile']);agent=next(a for a in load_agents(include_afo=True)[0] if a.id==job['role'])
 reserved=role_job_tokens(prof,job['role'],agent.max_stage_tokens)
 try:
  body,measured=request_material(job,step=1 if two_step(job) else None)
  need=measured['input_tokens']+measured['effective_output_cap']
  rows.append({'case_id':case.parent.name,'packet_ref':doc['packet_ref'],'selected_obligations':selected,'two_step':two_step(job),
  'reservation':reserved,'measurement':measured,'total_request_bound':need,'excess':max(0,need-reserved),
  'artifacts':[{'path':a['path'],'bytes':a.get('bytes'),'sha256':a.get('sha256'),'selected':a['ref'] in p['obligations'][selected[0]]['evidence_refs']} for a in p['artifacts']],
  'findings':len(p['findings']),'obligations':len(p['obligations'])})
 except Exception as exc:rows.append({'case_id':case.parent.name,'error':type(exc).__name__+':'+str(exc)})
print(json.dumps({'at':utc_now(),'source_revision':'fcb15cba0bbc1b5e6e7c91c86aba08db244b5c61','method':'read_only_request_material; no job preparation/reservation/gateway contact','cases':rows}))
