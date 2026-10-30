"""Owner-requested standalone native artifact trial; no AFO intake, grants or inference ledger."""
from pathlib import Path
import argparse,hashlib,json,os,secrets,subprocess,sys,time
import httpx

P=Path('/mnt/data/forge-c/production-local-014')
N=Path('/mnt/data/forge-c/native-artifacts-014-20261030-v1')
Q=N/'source';REV='c221b65ebc011cbed488db83af3e2804790c1129'
PROFILE='local-rtx-v2-omniverse2-q38-qm-native-artifacts'
WO='WO-F014-QWEN-NATIVE-ARTIFACTS-20261030-LL-01'
ap=argparse.ArgumentParser();ap.add_argument('--start',action='store_true');a=ap.parse_args()
for key in list(os.environ):
 if key.startswith('FORGE_'):os.environ.pop(key)
fab=None
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line.startswith('FORGE_FABRO_BIN='):fab=line.split('=',1)[1]
assert fab and Path(fab).is_file()
os.environ.update(FORGE_REPO_ROOT=str(Q),FORGE_LRTX_ROOT=str(N),FORGE_FABRO_BIN=fab)
sys.path.insert(0,str(Q/'factory/python'))
from forge_factory import workorder as W
from forge_factory.afo.durable import immutable_json
from forge_factory.common import utc_now,sha256_file,pretty_json
from forge_factory.lrtx import profile,stack
from forge_factory.workflow.builder import build,binding_for,scale_timeouts
from forge_factory.fabro.runconfig import write_run
from forge_factory.fabro.client import FabroClient,load_token
assert subprocess.check_output(['git','-C',str(Q),'rev-parse','HEAD'],text=True).strip()==REV
prof=profile.load(PROFILE)
assert prof['work_order_purpose']=='QM' and not any(prof['structured']['phases_by_layer'].values())
for name in ('state','archives','fabro/storage','fabro/home/.fabro','logs','run','home','cache/uv','cache/pip','cache/xdg'):
 (N/name).mkdir(mode=0o700,parents=True,exist_ok=True)
for name,target in prof['deployment']['shared_readonly'].items():
 link=N/name
 if not link.exists():link.symlink_to(target)
 if link.is_symlink():assert link.resolve()==Path(target).resolve()
if not (N/'venv').exists():(N/'venv').symlink_to(P/'venv')
settings={'profile':prof,'root':N,'ports':prof['deployment']['ports']}
env=stack.envmap(settings)
env.update(FORGE_DURABLE_AUTONOMY='0',FORGE_DURABLE_NATIVE_HEADER='0',PYTHONDONTWRITEBYTECODE='1',
 FORGE_GATEWAY_REASONING=stack.gateway_reasoning(prof),FORGE_GATEWAY_REQUEST_TIMEOUT_S='86400',
 FORGE_GATEWAY_ROUTES=json.dumps({prof['models']['default']:'http://127.0.0.1:11457'}),
 FORGE_GATEWAY_REQUEST_MEASUREMENT='{}')
# No admission queue/token/cancellation enforcement is configured in this diagnostic gateway.
for key in ('FORGE_GATEWAY_MAX_INFLIGHT','FORGE_OPERATIONS_INTENT','FORGE_AFO_POLICY','FORGE_AFO_AUTH_DIR','FORGE_AFO_ALLOWED_SIGNERS'):
 env.pop(key,None)
os.environ.update(env)
(N/'fabro/settings.toml').write_text(stack.fabro_config(settings))
(N/'fabro/home/.fabro/settings.toml').write_text('_version = 1\n[cli.target]\ntype = "http"\nurl = "http://127.0.0.1:32401/api/v1"\n')
secretfile=N/'fabro/storage/server.env'
if not secretfile.exists():
 secretfile.write_text('SESSION_SECRET='+secrets.token_hex(32)+'\nFABRO_DEV_TOKEN=fabro_dev_'+secrets.token_hex(32)+'\n');secretfile.chmod(0o600)
serverenv={**env,'HOME':str(N/'fabro/home')}
for line in secretfile.read_text().splitlines():
 if '=' in line:k,v=line.split('=',1);serverenv[k]=v
(N/'fabro/home/.fabro/auth.json').write_text(json.dumps({'servers':{'http://127.0.0.1:32401':{'kind':'dev-token','token':serverenv['FABRO_DEV_TOKEN'],'logged_in_at':utc_now()}}}))
(N/'fabro/home/.fabro/auth.json').chmod(0o600)
prepared=N/'prepared.json';ws=N/'state/workorders'/WO/'workspace'
if not prepared.exists():
 ws,m=W.prepare(Q/'examples/0002a-arm_55_rcc_ll',WO,purpose='QM',
                execution_policy='qm-pipeline-demonstration-repair-v2')
 m['local_profile']={'id':PROFILE,'version':prof['version'],'config':prof['_path'],'config_sha256':prof['_sha256'],
  'status':prof['status'],'enforcement':{'AFO_generation_admission':'BYPASSED_OWNER_DEVELOPMENT_REQUEST','budget_enforcement':'DISABLED_FOR_STANDALONE_TRIAL','qualification':'NOT_QUALIFIED'}}
 m['native_artifact_trial']={'owner_request':'ignore trusted role identity, token accounting and cancellation controls; produce artifacts and retain deterministic checks where possible','standalone':True,'AFO_intake':False,'no_production_acceptance':True}
 (ws/'.forge-run/manifest.json').write_text(pretty_json(m))
 structured=W.local_profile_structured(prof,m,prof['models']['default'])
 graph,nodes=build(WO,goal='QM native artifact development; findings retained, no accepted-product claim',
  sections=W.section_map(ws),layer='LL',trace=True,chunk_lines=150,
  execution_policy=m['development_execution'],assessment_manifest=m,structured=structured)
 graph=scale_timeouts(graph,10)
 assert 'forge_factory.lrtx.runner' not in graph
 (ws/'.forge-run/model-profile.json').write_text(pretty_json(W.model_profile(prof['models']['default'],'ollama',None,nodes)))
 roles=sorted({v['role'] for v in nodes.values()})
 agents=W.agent_preflight(roles);mcps=W.mcp_preflight(roles,live=True)
 assert agents['status']=='PASS' and mcps['status']=='PASS',(agents['status'],mcps['status'])
 toml=write_run(ws,graph,'Qwen native QM artifact trial',binding_for(WO,str(ws),nodes),
                W.fabro_mcp_config(mcps['servers']),model=prof['models']['default'],provider='ollama')
 immutable_json(prepared,{'at':utc_now(),'source_revision':REV,'profile':PROFILE,'work_order':WO,'workspace':str(ws),
  'model':prof['models']['default'],'workflow':'SHARED_NATIVE_AGENT_MCP_PHASES','structured_substitutions':False,
  'controls':'OWNER_REQUESTED_STANDALONE_DEVELOPMENT_MODE','quality':'DEMONSTRATION_ONLY_NOT_QUALIFIED',
  'agents_preflight':agents['status'],'mcp_preflight':mcps['status'],'workflow_sha256':sha256_file(ws/'.forge-run/workflow.fabro')})
else:
 d=json.loads(prepared.read_text());assert d['source_revision']==REV and d['workspace']==str(ws)
def healthy(url):
 try:return httpx.get(url,timeout=2).status_code==200
 except httpx.HTTPError:return False
services=N/'run/services.json'
rec=json.loads(services.read_text()) if services.exists() else {}
def start(name,argv,penv,url):
 if name in rec and healthy(url):return
 if healthy(url):raise RuntimeError('UNEXPECTED_SERVICE_ON_TRIAL_PORT:'+name)
 log=(N/'logs'/('native-'+name+'.log')).open('ab',buffering=0)
 child=subprocess.Popen(argv,env=penv,cwd=N,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 rec[name]={'pid':child.pid,'argv':argv,'health':url,'started_at':utc_now()}
 services.write_text(json.dumps(rec,indent=2)+'\n');services.chmod(0o600)
 for _ in range(180):
  if healthy(url):return
  if child.poll() is not None:raise RuntimeError('TRIAL_SERVICE_EXITED:'+name)
  time.sleep(1)
 raise RuntimeError('TRIAL_SERVICE_START_PENDING:'+name)
start('gateway',[str(P/'venv/bin/python'),'-m','forge_factory.llm_gateway','--port','11458',
                 '--upstream','http://127.0.0.1:11457','--meter',str(N/'state/llm-gateway/usage.jsonl')],env,'http://127.0.0.1:11458/health')
start('fabro',[fab,'server','start','--foreground','--no-web','--no-upgrade-check','--config',
               str(N/'fabro/settings.toml'),'--storage-dir',str(N/'fabro/storage')],serverenv,'http://127.0.0.1:32401/health')
if not a.start:
 print(json.dumps({'status':'PREPARED_SERVICES_ONLY_NO_INFERENCE','root':str(N),'work_order':WO,'source_revision':REV}));raise SystemExit(0)
launchfile=N/'launch.json'
if launchfile.exists():print(launchfile.read_text());raise SystemExit(0)
# Current production work must already be stopped by the owner-requested maintenance.
intent=json.loads(Path('/home/omniverse2/.local/state/forge-c-production-014/operations.json').read_text())
assert intent['mode']=='PAUSED' and intent['epoch']==111
if not healthy('http://127.0.0.1:11457/health'):
 physical=profile.load('local-rtx-v2-omniverse2-q38-aspice-medium-author-xhigh-inspector-capacity')
 spec=stack.llama_server_spec(P,physical,physical['deployment']['ports'],env)
 start('llama_server',spec[0],spec[1],spec[2])
origin=P/'state/workorders/WO-AFO-f2a638a42fadd518-a1/workspace'
drafts=[]
for rel in ('workproducts/SWE.1/software_requirements.md','workproducts/SWE.1/register_effects.json',
            'traceability/requirements_to_tests.csv','traceability/upstream_gaps.md'):
 src=origin/rel;dst=ws/rel
 if src.is_file():
  raw=src.read_bytes();dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw)
  drafts.append({'path':rel,'source_sha256':hashlib.sha256(raw).hexdigest(),'origin':str(src),'status':'WORKING_DRAFT_REQUIRES_CURRENT_CHECKS'})
immutable_json(ws/'.forge-run/native-working-draft-provenance.json',{'drafts':drafts,'old_inspection_or_phase_pass_imported':False})
toml=ws/'.forge-run/workflow.toml'
rid=W.launch_run(ws,WO,toml,fab,{'trial':'native-artifacts-014','quality':'DEVELOPMENT_ONLY'})
(ws/'.forge-run/fabro_server.json').write_text(json.dumps({'url':env['FORGE_FABRO_URL'],'storage':env['FORGE_FABRO_STORAGE']}))
record={'at':utc_now(),'status':'NATIVE_QWEN_ARTIFACT_TRIAL_RUNNING','source_revision':REV,'work_order':WO,
 'native_id':rid,'workspace':str(ws),'root':str(N),'workflow':'NATIVE_MCP_SWE1_TO_SWE6','seeded_working_drafts':len(drafts),
 'AFO_intake':False,'budget_enforcement':False,'trusted_generation_role_admission':False,
 'new_trial_tokens':'NOT_CHARGED_TO_AFO_LEDGER; retain available gateway usage separately','production_qualification':'NOT_PROVEN'}
immutable_json(launchfile,record);print(json.dumps(record))
