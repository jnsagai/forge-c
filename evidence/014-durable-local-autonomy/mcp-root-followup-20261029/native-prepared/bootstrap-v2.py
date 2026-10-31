"""Finite zero-model qualification. Run only after production execution is quiescent."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time,socket,shutil,threading,signal
P=Path('/mnt/data/forge-c/production-local-014')
N=P/'deployment/qualification-mcp-root-9f9a93f'
R=N/'repo';REV='9f9a93f174f46aa0add59c16a423be7d56988614'
assert socket.gethostname()=='omniverse2'
sys.path.insert(0,str(P/'repo/factory/python'))
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
from forge_factory.afo.operations import Intent
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.execution_lifecycle import Executions
intent=Intent()
def available():
 with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as db:
  state=intent.read()
  if state['mode']!='RUNNING' or state['epoch']!=32 or Executions(db).pending():return False
  with db.tx() as c:
   if c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone():return False
   if c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone():return False
   if c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone():return False
 return True
assert available(),'PRODUCTION_NOT_QUIESCENT_OR_NEW_OPERATOR_INTENT'
assert not R.exists()
assert hashlib.sha256((N/'source.bundle').read_bytes()).hexdigest()=='754b64a9a73641bdc2c5301686d0b9ea5bc6c45c8262c244abb63256e4a982e8'
def git(*args,cwd=R):
 return subprocess.check_output(['git',*args],cwd=cwd,text=True).strip()
subprocess.run(['git','clone','--no-checkout',str(P/'repo'),str(R)],check=True,capture_output=True)
subprocess.run(['git','-C',str(R),'fetch',str(N/'source.bundle'),'refs/qualification/014-mcp-root-9f9a93f'],check=True,capture_output=True)
subprocess.run(['git','-C',str(R),'checkout','--detach',REV],check=True,capture_output=True)
assert git('rev-parse','HEAD')==REV
copies=[]
for rel in git('ls-files','--others','--ignored','--exclude-standard','--','examples',cwd=P/'repo').splitlines():
 src=P/'repo'/rel;dst=R/rel
 if src.is_file() and src.suffix in ('.md','.json','.yaml') and ('/inputs/' in rel or rel.endswith('/hal_driver_guideline.md')) and not dst.exists():
  dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
  digest=hashlib.sha256(dst.read_bytes()).hexdigest()
  assert digest==hashlib.sha256(src.read_bytes()).hexdigest();copies.append({'path':rel,'sha256':digest})
data=N/'data';data.mkdir(mode=0o700)
for name in ('inputs','toolchains'):(data/name).symlink_to(P/name,target_is_directory=True)
for name in ('tmp','cache','state','events','archives'):(N/name).mkdir(mode=0o700)
env={'PATH':':'.join([str(P/'venv/bin'),str(P/'toolchains/LLVM-19.1.7-Linux-X64/bin'),
 '/usr/local/bin','/usr/bin','/bin',str(P/'toolchains/formal/bin'),str(P/'toolchains/sysroot/usr/bin')]),
 'LANG':'C.UTF-8','LC_ALL':'C.UTF-8','TZ':'UTC','PYTHONDONTWRITEBYTECODE':'1',
 'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','FORGE_FABRO_LIVE':'0','PYTHONPATH':str(R/'factory/python'),
 'FORGE_REPO_ROOT':str(R),'FORGE_DATA_ROOT':str(data),'FORGE_STATE_DIR':str(N/'state'),
 'FORGE_EVENTS_DIR':str(N/'events'),'FORGE_ARCHIVE_DIR':str(N/'archives'),
 'TMPDIR':str(N/'tmp'),'XDG_CACHE_HOME':str(N/'cache')}
assert not git('status','--porcelain')
record={'source_revision':REV,'host':socket.gethostname(),'source_clean_before':True,
 'model_generation_requests':0,'production_changed':False,'authority_changed':False,
 'private_input_copies':copies,'started_epoch':time.time(),'operator_epoch':32,
 'environment':{k:env[k] for k in ('FORGE_DATA_ROOT','FORGE_STATE_DIR','PYTHONPATH','PATH','TMPDIR')}}
halt=[];done=threading.Event();child=None
def guard():
 deadline=time.monotonic()+300
 while not done.wait(.5):
  if time.monotonic()>=deadline or not available():
   halt.append('QUALIFICATION_TIMEBOX_OR_NEW_EXECUTION_OR_OPERATOR_INTENT')
   if child and child.poll() is None:
    try:os.killpg(child.pid,signal.SIGTERM)
    except ProcessLookupError:pass
   return
threading.Thread(target=guard,daemon=True).start()
cmd=[str(P/'venv/bin/python'),'-m','pytest','-q',
 'factory/python/tests/test_fabro_runconfig_context.py',
 'factory/python/tests/test_da014_qualification_state.py',
 'factory/python/tests/test_m2_mcp.py::test_t018_preflight_live_handshake_and_run_config_has_no_shell',
 '--junitxml='+str(N/'pytest.xml')]
record['command']=cmd
try:
 assert available()
 with (N/'pytest.log').open('w') as output:
  child=subprocess.Popen(cmd,cwd=R,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
  record['pytest_exit_code']=child.wait(timeout=180)
 assert record['pytest_exit_code']==0 and not halt
 assert available()
 render=[str(P/'venv/bin/python'),str(N/'render-real-unit-cases-v2.py')]
 with (N/'real-render.log').open('w') as output:
  child=subprocess.Popen(render,cwd=R,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
  record['real_render_exit_code']=child.wait(timeout=90)
finally:
 done.set()
 if child and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
 record.update(halt=halt,source_clean_after=not git('status','--porcelain'),completed_epoch=time.time())
 (N/'provenance.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps(record),flush=True)
assert record['real_render_exit_code']==0 and not halt and record['source_clean_after']

