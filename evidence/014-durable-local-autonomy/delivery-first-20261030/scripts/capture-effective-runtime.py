
from pathlib import Path
import json,sys,subprocess,httpx,os
R=Path('/mnt/data/forge-c/delivery-first-014-20261030-v1');Q=R/'source';sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.afo.durable import immutable_json
from forge_factory.common import utc_now
services=json.loads((R/'run/services.json').read_text());gw=services['gateway'];pid=gw['pid']
env=dict(s.split('=',1) for s in (Path('/proc')/str(pid)/'environ').read_bytes().decode().split('\0') if '=' in s)
flags={k:env.get(k) for k in ('FORGE_GATEWAY_DROP_RETRIES','FORGE_GATEWAY_MEASURE_UNBOUND','FORGE_GATEWAY_NATIVE_CONTEXT_LIMIT','FORGE_DURABLE_NATIVE_HEADER')}
flags['reasoning']=json.loads(env['FORGE_GATEWAY_REASONING'])
models=[]
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:argv=[s.decode() for s in (proc/'cmdline').read_bytes().split(b'\0') if s]
 except (OSError,UnicodeDecodeError):continue
 if argv and Path(argv[0]).name=='llama-server':
  wanted={}
  for key in ('--model','-m','--ctx-size','-c','--parallel','-np','--spec-type','--draft-max','--threads','-t','--cache-type-k','--cache-type-v','--n-gpu-layers','-ngl'):
   if key in argv and argv.index(key)+1<len(argv):wanted[key]=argv[argv.index(key)+1]
  models.append({'pid':int(proc.name),'flags':wanted})
out={'at':utc_now(),'source_revision':subprocess.check_output(['git','-C',str(Q),'rev-parse','HEAD'],text=True).strip(),
 'source_clean':not subprocess.check_output(['git','-C',str(Q),'status','--porcelain','--untracked-files=no'],text=True).strip(),
 'gateway_pid':pid,'gateway_effective_flags':flags,'model_processes':models,
 'slots':[{k:s.get(k) for k in ('id','id_task','is_processing','n_ctx')} for s in httpx.get('http://127.0.0.1:11457/slots').json()],
 'profile_model_digest':'DECLARED_IN_VERSIONED_PROFILE; NO_NEW_FULL_WEIGHT_HASH_PERFORMED','AFO_intake':False,
 'production_operator_intent':json.loads(Path('/home/omniverse2/.local/state/forge-c-production-014/operations.json').read_text()),
 'controls':'SCOPED_STANDALONE_QM; LEGACY_ROLE_FILE_TOOL_POLICY_REMAINS','runtime_qualification':'NOT_PROVEN'}
# Operator record has only its published administrative intent, never credentials.
immutable_json(R/'runtime-inventory-first-candidate.json',out);print(json.dumps(out))

