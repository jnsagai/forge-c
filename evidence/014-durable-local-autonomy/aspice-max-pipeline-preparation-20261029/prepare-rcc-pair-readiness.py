"""Prepare LL inputs and both workflow routes, without inference or fabricated HAL dependency."""
from pathlib import Path
import hashlib,json,os,subprocess
A=Path(__file__).parent;os.environ['FORGE_STATE_DIR']=str(A/'rcc-pair-preparation-state');os.environ['FORGE_EVENTS_DIR']=str(A/'rcc-pair-preparation-events')
from forge_factory.common import REPO_ROOT,sha256_file
from forge_factory import workorder as W
from forge_factory.lrtx import profile
from forge_factory.release import aspice
from forge_factory.workflow.builder import build
p=profile.load('local-rtx-v2-omniverse2-q38-aspice-max-mtp');aspice.validate_profile(aspice.PURPOSE,p)
assert not profile.selection_issues(p,model=p['models']['default'],provider='ollama',code_model=None,acp_authors=None,acp_inspectors=None)
assert p['structured']['advisory_continue'] is False
ws,m=W.prepare(REPO_ROOT/'examples/0002a-arm_55_rcc_ll','WO-F014-RCC-LL-INPUT-PREFLIGHT',purpose=aspice.PURPOSE)
assert aspice.selected(m)['safety_approval'] is None
routes={}
for layer in ['LL','HAL']:
 man={**m,'layer':layer};st=W.local_profile_structured(p,man,p['models']['default'])
 dot,nodes=build('WO-F014-RCC-'+layer+'-GRAPH-PREFLIGHT',goal='RCC '+layer+' full ASPICE pipeline',layer=layer,structured=st,assessment_manifest=man)
 roles={v['role'] for v in nodes.values()};expected={f'swe{i}-{r}' for i in range(1,7) for r in ['author','inspector']}
 assert expected<=roles,(layer,expected-roles)
 assert 'release-manager' in roles
 graph=A/('rcc-'+layer.lower()+'-prospective-workflow.fabro');graph.write_text(dot)
 routes[layer]={'phase_roles':sorted(roles),'all_six_author_and_inspector_roles_present':True,'structured_author_phases':st['phases'],'structured_inspector_phases':st['inspect_phases'],'routing':'existing structured local obligations' if layer=='LL' else 'existing Fabro SKILL/MCP agents; no unsupported structured HAL path enabled','graph_sha256':sha256_file(graph),'native_execution':'NOT_RUN'}
try:W.prepare(REPO_ROOT/'examples/0002b-arm_55_rcc_hal','WO-F014-RCC-HAL-DEPENDENCY-PREFLIGHT',purpose=aspice.PURPOSE)
except ValueError as exc:
 assert str(exc).startswith('HAL_LAYER_NEEDS_PROVIDED_LL');hal={'status':'WAITING_FOR_NEW_QWEN_LL_VERIFIED_OUTPUT','guard':str(exc),'verified_source_substituted':False}
else:raise AssertionError('HAL was prepared without verified LL')
result={'schema':'forge-c/ll-hal-pipeline-preparation/1','source_revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'profile':p['id'],'profile_sha256':p['_sha256'],'purpose':aspice.PURPOSE,'model_requests':0,'live_activation':False,'functional_gates_blocking':True,'safety_approval':None,'assessed_aspice_compliance':None,'ll_workspace':str(ws),'ll_manifest_sha256':sha256_file(ws/'.forge-run/manifest.json'),'ll_input_hashes':m['inputs'],'ll_upstream_status':m['upstream']['status'],'routes':routes,'HAL':hal,'runtime_success':'NOT_RUN','qwen_self_healing':'UNPROVEN'}
(A/'rcc-pair-preparation-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'source_revision':result['source_revision'],'profile':p['id'],'routes_verified':['LL','HAL'],'model_requests':0,'HAL':hal}))
