"""Independent pre-candidate mechanical oracle; real failed SWE.1 evidence, no model response or acceptance."""
import json,os,re,shlex,shutil,subprocess,sys
from pathlib import Path
import pytest
SOURCE=Path(os.environ['F014_CONTEXT_SOURCE'])
FROZEN=Path(os.environ['F014_CONTEXT_FROZEN'])
CHILD=r"""
import importlib,json,os,sys
from pathlib import Path
real=importlib.import_module
def observed(name,*args,**kwargs):
 m=real(name,*args,**kwargs)
 if name in ('forge_factory.lrtx.review','forge_factory.lrtx.review_semantic'):
  def stop(packet,*a,**k):
   from forge_factory.afo.diagnosis_packet import measure_request
   body={'model':packet['model'],'messages':packet['_messages'],'stream':True,'max_tokens':packet['output_reserve'],
         'stream_options':{'include_usage':True},'response_format':{'type':'json_schema','json_schema':{'name':'packet_output','strict':True,'schema':packet['output_schema']}}}
   measured=measure_request(body)
   Path(os.environ['F014_PROBE_CAPTURE']).write_text(json.dumps({'task':packet['task'],'accounting_context':packet['accounting']['context_tokens'],
    'measured_input_tokens':measured['input_tokens'],'output_reserve':packet['output_reserve'],'model_requests':0}))
   raise RuntimeError('INDEPENDENT_ORACLE_STOP_BEFORE_GENERATION')
  sys.modules['forge_factory.lrtx.structured'].call=stop
 return m
importlib.import_module=observed
from forge_factory.lrtx import runner
raise SystemExit(runner.main(json.loads(sys.argv[1])))
"""
def probe(tmp_path,profile_id,expected):
 from forge_factory import acp,workorder as W
 from forge_factory.lrtx import profile
 ws=tmp_path/'workspace';shutil.copytree(FROZEN,ws)
 man=json.loads((ws/'.forge-run/manifest.json').read_text());prof=profile.load(profile_id)
 man['local_profile']={'id':profile_id,'version':prof['version'],'config':prof['_path'],'config_sha256':prof['_sha256']}
 (ws/'.forge-run/manifest.json').write_text(json.dumps(man))
 os.environ['FORGE_LRTX_PROFILE']=profile_id
 model=prof['models']['default']
 graph,_=W.build(man['work_order'],goal='Frozen original RCC context probe',layer='LL',
                   structured=W.local_profile_structured(prof,man,model),assessment_manifest=man)
 attrs=next(attrs for _,_,_,name,attrs in acp.statements(graph) if name=='swe1_inspector')
 match=re.search(r'\bscript=("(?:\\.|[^"\\])*")',attrs);assert match
 words=shlex.split(json.loads(match[1]));env=dict(os.environ)
 # Consume actual generated command assignments; no invented context override.
 while words and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*',words[0]):
  k,v=words.pop(0).split('=',1);env[k]=v
 assert words[1:3]==['-m','forge_factory.lrtx.runner']
 assert not any(x in words for x in (';','&&','||','|'))
 env.update(F014_PROBE_CAPTURE=str(tmp_path/'capture.json'),FORGE_REPO_ROOT=str(SOURCE),
            FORGE_STATE_DIR=str(tmp_path/'state'),FORGE_EVENTS_DIR=str(tmp_path/'events'),
            PYTHONPATH=str(SOURCE/'factory/python'),PYTHONDONTWRITEBYTECODE='1')
 result=subprocess.run([sys.executable,'-c',CHILD,json.dumps(words[3:])],cwd=ws,env=env,
                       capture_output=True,text=True,timeout=45)
 assert result.returncode==0,(result.stdout+result.stderr)[-1500:]
 path=tmp_path/'capture.json'
 reply=ws/'.forge-run/lrtx/SWE.1/inspect-reply.json'
 assert path.exists(),json.loads(reply.read_text()).get('issues') if reply.exists() else result.stderr[-1000:]
 facts=json.loads(path.read_text())
 assert facts['model_requests']==0 and facts['accounting_context']==expected
 assert facts['measured_input_tokens']+facts['output_reserve']<=expected
 assert 'INDEPENDENT_ORACLE_STOP_BEFORE_GENERATION' in reply.read_text()
 return facts

@pytest.mark.parametrize('profile_id,expected',[
 ('local-rtx-v2-omniverse2-q38-aspice-max-mtp',262144),
 ('local-rtx-v2-omniverse2-q38-aspice-mtp',131072)])
def test_actual_generated_inspector_uses_bound_profile_context(tmp_path,profile_id,expected):
 probe(tmp_path,profile_id,expected)

def test_legacy_unset_context_fallback_is_preserved(tmp_path):
 env=dict(os.environ)
 for key in ('FORGE_LRTX_PROFILE','FORGE_LRTX_CONTEXT_TOKENS'):env.pop(key,None)
 env.update(PYTHONPATH=str(SOURCE/'factory/python'),FORGE_REPO_ROOT=str(SOURCE),PYTHONDONTWRITEBYTECODE='1')
 code="from forge_factory.lrtx.structured import CONTEXT_TOKENS; assert CONTEXT_TOKENS==24576"
 subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,check=True,timeout=20)
