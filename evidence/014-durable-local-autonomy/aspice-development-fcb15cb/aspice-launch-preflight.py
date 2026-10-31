from pathlib import Path
import os,sys,json,hashlib
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/aspice-window-20261028'
profile='local-rtx-v2-omniverse2-q38-aspice'
if '--inside' not in sys.argv:
 for line in (P/'state/afo/conductor.env').read_text().splitlines():
  if line and not line.startswith('#'):
   k,v=line.split('=',1);os.environ[k]=v
 sys.path.insert(0,str(R/'factory/python'))
 from forge_factory.lrtx import stack
 stack.exec_in(stack.settings(profile),[str(P/'venv/bin/python'),__file__,'--inside'])
sys.path.insert(0,str(R/'factory/python'))
from forge_factory import workorder as W
from forge_factory.lrtx.profile import select
from forge_factory.registry.agents import preflight as agents
from forge_factory.mcp.preflight import preflight as mcp
from forge_factory.workflow.builder import build
from forge_factory.afo.durable import immutable_json
from forge_factory.lrtx import swe1,runner
model='qwen3.8:27b-q8_0'
local=select(profile,model=model,provider='ollama',code_model=None,acp_authors=None,acp_inspectors=None)
os.environ['FORGE_STATE_DIR']=str(O/'preflight-state');os.environ['FORGE_EVENTS_DIR']=str(O/'preflight-events')
ws,man=W.prepare(R/'examples/0014c-st-cube-crc','WO-ASPICE-CRC-PREFLIGHT',purpose='ASPICE_ONLY')
man['local_profile']=local;(ws/'.forge-run/manifest.json').write_text(json.dumps(man))
assert runner.author_module(ws,'author','SWE.1')=='swe1' and runner.inspector_module(ws,'SWE.1')=='review'
inv=swe1.inventory(ws);assert not inv['missing_sections'] and inv['registers'],inv
secmap={}
for line in (ws/'inputs/index.md').read_text().splitlines():
 parts=[x.strip() for x in line.split(' | ')]
 if len(parts)==4 and parts[0][:1].isdigit() and parts[0] not in secmap:secmap[parts[0]]=parts[3]
graph,nodes=build(man['work_order'],goal=man['driver']+' (ASPICE-only offline review)',
 sections=secmap,chunk_lines=40,layer='LL',trace=True,isolation=False,brownfield=man['code_mode'],
 peripheral=man['peripheral'],delivery_style=man['delivery']['build']['style'],
 structured=W.local_profile_structured(local,man,model))
roles=sorted({n['role'] for n in nodes.values()});a=agents(roles);m=mcp(roles,live=True)
scope=json.loads((O/'scope.json').read_text());trial=json.loads((P/'state'/scope['role_trial_ref']['path']).read_text())
result={'status':'PASS' if a['status']==m['status']=='PASS' and not set(roles)-set(trial['roles']) else 'BLOCKED',
 'source_revision':scope['source_revision'],'profile_sha256':local['config_sha256'],
 'network':local['enforcement']['network'],'model_identity':local['models'],'generation_requests':0,
 'workspace':str(ws),'delivery_intake':man['delivery_intake'],'required_register_groups':len(swe1.groups(inv)),
 'author_module':'swe1','inspector_module':'review','safec_execution':False,'purpose':man['purpose'],
 'roles':roles,'graph_sha256':hashlib.sha256(graph.encode()).hexdigest(),
 'agents':{k:a[k] for k in ['status','issues']},
 'mcp':{k:m[k] for k in ['status','issues','disabled_optional_ops','handshakes']},
 'missing_signed_trial_roles':sorted(set(roles)-set(trial['roles'])),
 'model_capability_or_product_success':'NOT_ESTABLISHED'}
immutable_json(O/'launch-prerequisites.json',result);print(json.dumps(result))
raise SystemExit(0 if result['status']=='PASS' else 1)
