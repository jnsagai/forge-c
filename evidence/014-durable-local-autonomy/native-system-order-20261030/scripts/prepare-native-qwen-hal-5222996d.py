"""Use the existing QM native workflow after this trial's own sealed provisional LL; default is read-only check."""
from pathlib import Path
import argparse,json,os,sys,subprocess
N=Path('/mnt/data/forge-c/native-artifacts-014-20261030-v1');Q=N/'source-hal-5222996d'
REV='5222996d7f76318438086bbd158866fe26f4ab16';PROFILE='local-rtx-v2-omniverse2-q38-qm-native-artifacts'
WO='WO-F014-QWEN-NATIVE-ARTIFACTS-20261030-HAL-01'
ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--start',action='store_true');args=ap.parse_args()
for key in list(os.environ):
 if key.startswith('FORGE_'):os.environ.pop(key)
os.environ.update(FORGE_REPO_ROOT=str(Q),FORGE_LRTX_ROOT=str(N))
sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.lrtx import profile,stack
from forge_factory.fabro.client import FabroClient,load_token,run_status
from forge_factory.common import utc_now,pretty_json,sha256_file
from forge_factory import workorder as W
from forge_factory.development_demonstration import provided_ll
from forge_factory.afo.durable import immutable_json
from forge_factory.release.finalize import verify_archive
from forge_factory.workflow.builder import build,binding_for,scale_timeouts
from forge_factory.fabro.runconfig import write_run
assert subprocess.check_output(['git','-C',str(Q),'rev-parse','HEAD'],text=True).strip()==REV
p=profile.load(PROFILE);env=stack.envmap({'profile':p,'root':N,'ports':p['deployment']['ports']})
env.update(FORGE_DURABLE_AUTONOMY='0',FORGE_DURABLE_NATIVE_HEADER='0',PYTHONDONTWRITEBYTECODE='1')
for line in Path('/mnt/data/forge-c/production-local-014/state/afo/conductor.env').read_text().splitlines():
 if line.startswith('FORGE_FABRO_BIN='):env['FORGE_FABRO_BIN']=line.split('=',1)[1]
os.environ.update(env)
existing=N/'launch-hal.json'
if existing.exists():print(existing.read_text());raise SystemExit(0)
ll=json.loads((N/'launch.json').read_text())
with FabroClient(base_url='http://127.0.0.1:32401',token=load_token(str(N/'fabro/storage')),timeout=15) as c:
 status=run_status(c.get_run(ll['native_id']))
 if status not in ('SUCCEEDED','FAILED','CANCELLED','CANCELED'):
  print(json.dumps({'status':'NOT_RUN_LL_STILL_LIVE','native_id':ll['native_id'],'native_status':status,'model_calls':0}));raise SystemExit(0)
 llws=Path(ll['workspace']);pkg=llws/'.forge-run/package.json'
 if not pkg.is_file():
  print(json.dumps({'status':'NOT_RUN_LL_PACKAGE_REQUIRED','native_status':status,'model_calls':0}));raise SystemExit(0)
 package=json.loads(pkg.read_text());audit=verify_archive(Path(package['archive']))
 if audit['integrity']!='PASS':raise ValueError('LL_ARCHIVE_INTEGRITY_FAILED')
 try:data,provenance=provided_ll(ll['work_order'],'rcc')
 except (OSError,ValueError) as exc:
  print(json.dumps({'status':'NOT_RUN_PROVISIONAL_LL_REQUIRED','blocker':str(exc)[:250],'model_calls':0}));raise SystemExit(0)
 if not args.prepare and not args.start:
  print(json.dumps({'status':'READY_TO_PREPARE_PROVISIONAL_QM_HAL','LL_header_sha256':provenance['sha256'],'quality_accepted':False,'model_calls':0}));raise SystemExit(0)
 # The LL parent must be terminal and no other run may be generating on this trial's shared server.
 for run in c.list_runs(limit=200):
  if run_status(run) not in ('SUCCEEDED','FAILED','CANCELLED','CANCELED'):
   raise ValueError('TRIAL_NATIVE_RUN_STILL_ACTIVE:'+str(run.get('id')))
prepared=N/'prepared-hal.json';ws=N/'state/workorders'/WO/'workspace'
if not prepared.exists():
 ws,m=W.prepare(Q/'examples/0002b-arm_55_rcc_hal',WO,purpose='QM',execution_policy='qm-pipeline-demonstration-repair-v2',provided_from=ll['work_order'])
 m['local_profile']={'id':PROFILE,'version':p['version'],'config':p['_path'],'config_sha256':p['_sha256'],'status':p['status'],
                     'enforcement':{'AFO_generation_admission':'BYPASSED_OWNER_DEVELOPMENT_REQUEST','budget_enforcement':'DISABLED_FOR_STANDALONE_TRIAL','qualification':'NOT_QUALIFIED'}}
 m['native_artifact_trial']={'standalone':True,'AFO_intake':False,'no_production_acceptance':True,'source_LL':ll['work_order']}
 (ws/'.forge-run/manifest.json').write_text(pretty_json(m))
 graph,nodes=build(WO,goal='QM HAL native artifact development; failed findings retained, no accepted-product claim',
  sections=W.section_map(ws),layer='HAL',trace=True,chunk_lines=150,
  execution_policy=m['development_execution'],assessment_manifest=m,
  structured=W.local_profile_structured(p,m,p['models']['default']))
 graph=scale_timeouts(graph,10);assert 'forge_factory.lrtx.runner' not in graph
 roles=sorted({v['role'] for v in nodes.values()});agents=W.agent_preflight(roles);mcps=W.mcp_preflight(roles,live=True)
 assert agents['status']=='PASS' and mcps['status']=='PASS'
 write_run(ws,graph,'Qwen native QM HAL artifact trial',binding_for(WO,str(ws),nodes),W.fabro_mcp_config(mcps['servers']),model=p['models']['default'],provider='ollama')
 (ws/'.forge-run/model-profile.json').write_text(pretty_json(W.model_profile(p['models']['default'],'ollama',None,nodes)))
 immutable_json(prepared,{'at':utc_now(),'source_revision':REV,'work_order':WO,'workspace':str(ws),'provided_LL':provenance,
                          'workflow_sha256':sha256_file(ws/'.forge-run/workflow.fabro'),'quality_accepted':False})
if not args.start:
 print(prepared.read_text());raise SystemExit(0)
launch=N/'launch-hal.json'
if launch.exists():print(launch.read_text());raise SystemExit(0)
intent=json.loads(Path('/home/omniverse2/.local/state/forge-c-production-014/operations.json').read_text())
assert intent['mode']=='PAUSED' and intent['epoch']==111
rid=W.launch_run(ws,WO,ws/'.forge-run/workflow.toml',env['FORGE_FABRO_BIN'],{'trial':'native-artifacts-014','quality':'DEVELOPMENT_ONLY'})
(ws/'.forge-run/fabro_server.json').write_text(json.dumps({'url':env['FORGE_FABRO_URL'],'storage':env['FORGE_FABRO_STORAGE']}))
record={'at':utc_now(),'status':'NATIVE_QWEN_HAL_ARTIFACT_TRIAL_RUNNING','source_revision':REV,'work_order':WO,'native_id':rid,
        'workspace':str(ws),'root':str(N),'provided_LL':provenance,'AFO_intake':False,'budget_enforcement':False,'production_qualification':'NOT_PROVEN'}
immutable_json(launch,record);print(json.dumps(record))
