"""Read-only frozen-verifier prerequisites; no benchmark, candidate, model or authority effect."""
from pathlib import Path
import json,os,shutil,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/afo-repair-live-20261029-v4'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.reliability import benchmark as B,reproduce as RR,isolation
from forge_factory.common import sha256_file,utc_now
before=os.environ['PATH'];variants=[]
pid=int(subprocess.check_output(['systemctl','--user','show','forge-conductor-local-omniverse2.service','-p','MainPID','--value'],text=True))
actual_env=dict(v.split(b'=',1) for v in (Path('/proc')/str(pid)/'environ').read_bytes().split(b'\0') if b'=' in v)
actual_path=actual_env[b'PATH'].decode()
for label,path in [('environment_file_only_not_running_conductor',before),('actual_running_conductor',actual_path),('pinned_llvm',str(P/'toolchains/LLVM-19.1.7-Linux-X64/bin')+':'+before)]:
 os.environ['PATH']=path;suites=[]
 for kind in ('golden','holdout'):
  sp=B.SUITES[kind];s=B.load_suite(kind);rows=[]
  for e in s['cases']:
   rows.append({'case_id':e['case']['case_id'],'frozen_compiler_version':e['case']['compiler_version'],'prerequisite_issue':B.check_case(e,sp.parent,R)})
  suites.append({'kind':kind,'manifest_sha256':sha256_file(sp),'cases':rows})
 variants.append({'label':label,'compiler':shutil.which('clang'),'compiler_version':B._tool_version(['clang','--version']),'suites':suites})
os.environ['PATH']=before
reps,issues=RR.load_manifest()
r={'schema':'forge-c/afo-verifier-prerequisite-audit/1','at':utc_now(),'actual_conductor_pid':pid,'other_process_environment_saved':False,'source_revision':subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip(),'variants':variants,'frozen_reproducer_count':len(reps),'frozen_reproducer_issues':issues,'isolation_backend':isolation.backend(),'tools':{t:shutil.which(t) for t in ('bwrap','cppcheck','clang','java','arm-none-eabi-gcc')},'model_requests':0,'candidate_or_benchmark_executed':False,'environment_changed_persistently':False,'protected_oracles_changed':False}
print(json.dumps(r,indent=2))
