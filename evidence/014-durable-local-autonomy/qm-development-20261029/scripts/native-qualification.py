import hashlib,json,os,subprocess,time,socket,shutil
from pathlib import Path
P=Path('/mnt/data/forge-c/production-local-014')
N=P/'deployment/qualification-qm-5b398d2'
R=N/'repo'
REV='5b398d27f2ee60d3c059dc115dd612f0ff105199'
BUNDLE_SHA='dcad63396245aa273c831e3cd1acc65a9e781cbd3f8be34a59e8a91b2c0cc54b'
assert socket.gethostname()=='omniverse2'
assert not R.exists()
assert hashlib.sha256((N/'source.bundle').read_bytes()).hexdigest()==BUNDLE_SHA
def git(*a,cwd=R):
 return subprocess.check_output(['git',*a],cwd=cwd,text=True).strip()
subprocess.run(['git','clone','--no-checkout',str(P/'repo'),str(R)],check=True,capture_output=True)
subprocess.run(['git','-C',str(R),'fetch',str(N/'source.bundle'),'HEAD'],check=True,capture_output=True)
subprocess.run(['git','-C',str(R),'checkout','--detach',REV],check=True,capture_output=True)
assert git('rev-parse','HEAD')==REV
ignored=git('ls-files','--others','--ignored','--exclude-standard','--','examples',cwd=P/'repo').splitlines()
links=[]
for rel in ignored:
 src=P/'repo'/rel
 dst=R/rel
 if src.is_file() and src.suffix in ('.md','.json','.yaml') and ('/inputs/' in rel or rel.endswith('/hal_driver_guideline.md')) and not dst.exists():
  dst.parent.mkdir(parents=True,exist_ok=True)
  shutil.copyfile(src, dst)
  assert hashlib.sha256(dst.read_bytes()).hexdigest()==hashlib.sha256(src.read_bytes()).hexdigest()
  links.append({'path':rel,'sha256':hashlib.sha256(src.read_bytes()).hexdigest()})
data=N/'data'
data.mkdir(mode=0o700)
for name in ('inputs','toolchains'):
 (data/name).symlink_to(P/name,target_is_directory=True)
for name in ('tmp','cache','events','state','archives'):
 (N/name).mkdir(mode=0o700)
env={k:v for k,v in os.environ.items() if not k.startswith(('FORGE_','OPENAI_','ANTHROPIC_'))}
env.update(PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',FORGE_FABRO_LIVE='0',
 PYTHONPATH=str(R/'factory/python'),FORGE_REPO_ROOT=str(R),FORGE_DATA_ROOT=str(data),
 FORGE_STATE_DIR=str(N/'state'),FORGE_EVENTS_DIR=str(N/'events'),FORGE_ARCHIVE_DIR=str(N/'archives'),
 TMPDIR=str(N/'tmp'),XDG_CACHE_HOME=str(N/'cache'))
env['PATH']=':'.join([str(P/'venv/bin'),str(P/'toolchains/LLVM-19.1.7-Linux-X64/bin'),
 '/usr/local/bin','/usr/bin','/bin',str(P/'toolchains/formal/bin'),str(P/'toolchains/sysroot/usr/bin')])
files=['test_qm_development', 'test_mission_deadline', 'test_da014_overnight', 'test_development_diagnostics', 'test_incremental_delivery', 'test_lrtx_tool_accounting', 'test_lrtx_inspection_accounting', 'test_incremental_incident_resume', 'test_lrtx_compat', 'test_da014_high_allowance', 'test_aspice_development', 'test_t009_workflow_gates']
cmd=[str(P/'venv/bin/python'),'-m','pytest','-q',*['factory/python/tests/'+f+'.py' for f in files],
 '--junitxml='+str(N/'pytest.xml')]
before=git('status','--porcelain')
assert not before, before
record={'source_revision':REV,'host':socket.gethostname(),'command':cmd,
 'environment':{k:env[k] for k in ('PYTHONPATH','FORGE_REPO_ROOT','FORGE_DATA_ROOT','FORGE_STATE_DIR',
 'FORGE_EVENTS_DIR','TMPDIR','PATH','FORGE_FABRO_LIVE')},'private_input_copies':links,
 'source_clean_before':True,'model_requests_expected':0,'deployment_changed':False,'services_changed':False,
 'authority_created_or_renewed':False,'started_epoch':time.time()}
(N/'provenance.json').write_text(json.dumps(record,indent=2)+'\n')
with (N/'pytest.log').open('w') as output:
 result=subprocess.run(cmd,cwd=R,env=env,stdout=output,stderr=subprocess.STDOUT)
record.update(exit_code=result.returncode,source_clean_after=not git('status','--porcelain'),
 completed_epoch=time.time())
(N/'provenance.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ('source_revision','exit_code','source_clean_before','source_clean_after')}))
raise SystemExit(result.returncode)

