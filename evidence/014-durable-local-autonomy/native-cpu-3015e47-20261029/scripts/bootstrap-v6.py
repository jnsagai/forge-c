"""Finite zero-model qualification. Run only after production execution is quiescent."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,time,socket,shutil,threading,signal
import xml.etree.ElementTree as ET
import resource
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:8])
os.nice(10)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--expected-operator-epoch",type=int,required=True)
args=parser.parse_args()
assert args.expected_operator_epoch>0
P=Path('/mnt/data/forge-c/production-local-014')
N=P/'deployment/qualification-core-stop-3015e47-v6'
R=N/'repo';REV='3015e47f93de7bfd1e81c8dd7bf4426d8c13ddc6'
assert socket.gethostname()=='omniverse2'
sys.path.insert(0,str(P/'repo/factory/python'))
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
from forge_factory.afo.operations import Intent
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.lrtx import stack,provider_process
settings=stack.settings('local-rtx-v2-omniverse2-q38-qm-demo-mtp')
intent=Intent()
def available():
 with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as db:
  state=intent.read()
  if state['mode']!='STOPPED' or not state.get('effective_stop') or state['epoch']!=args.expected_operator_epoch or Executions(db).pending():return False
  with db.tx() as c:
   if c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone():return False
   if c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone():return False
   if c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone():return False
 try:return bool(provider_process.quiet(stack.serving_instance(settings)))
 except (OSError,ValueError):return False
assert available(),'PRODUCTION_NOT_QUIESCENT_OR_NEW_OPERATOR_INTENT'
assert not R.exists()
assert hashlib.sha256((N/'source.bundle').read_bytes()).hexdigest()=='fcd35d8fc7649494032519888c1ecbf8703ee9b57f74a95e29ba43eb8b13c1e9'
def git(*args,cwd=R):
 return subprocess.check_output(['git',*args],cwd=cwd,text=True).strip()
subprocess.run(['git','clone','--no-checkout',str(P/'repo'),str(R)],check=True,capture_output=True)
subprocess.run(['git','-C',str(R),'fetch',str(N/'source.bundle'),'refs/qualification/014-swe6-route-3015e47'],check=True,capture_output=True)
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
from forge_factory.afo.host import init as init_volume,preflight
sentinel=init_volume(data)
assert preflight(data)['ok']
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
 'model_generation_requests':0,'production_changed':False,'authority_changed':False,'operator_mode':'STOPPED','model_network_isolated':True,
 'volume_sentinel_sha256':hashlib.sha256(sentinel.read_bytes()).hexdigest(),'volume_preflight':preflight(data),
 'private_input_copies':copies,'started_epoch':time.time(),'operator_epoch':args.expected_operator_epoch,
 'cpu_affinity':sorted(os.sched_getaffinity(0)),'nice':os.getpriority(os.PRIO_PROCESS,0),
 'environment':{k:env[k] for k in ('FORGE_DATA_ROOT','FORGE_STATE_DIR','PYTHONPATH','PATH','TMPDIR')}}
halt=[];done=threading.Event();child=None
def interrupted(signum,frame):
 raise KeyboardInterrupt("QUALIFICATION_INTERRUPTED")
signal.signal(signal.SIGTERM,interrupted)
def guard():
 deadline=time.monotonic()+600
 while not done.wait(.5):
  if time.monotonic()>=deadline or not available():
   halt.append('QUALIFICATION_TIMEBOX_OR_NEW_EXECUTION_OR_OPERATOR_INTENT')
   if child and child.poll() is None:
    try:os.killpg(child.pid,signal.SIGTERM)
    except ProcessLookupError:pass
   return
threading.Thread(target=guard,daemon=True).start()
namespace=[shutil.which('unshare'),'--user','--map-root-user','--pid','--net','--fork','--mount-proc','--kill-child=SIGKILL','--']
assert namespace[0], 'PRIVATE_PID_NAMESPACE_PREREQUISITE_UNAVAILABLE'
cmd=namespace+[str(P/'venv/bin/python'),'-m','pytest','-q',
 'factory/python/tests/test_da014_integration.py',
 'factory/python/tests/test_da014_maintenance.py',
 'factory/python/tests/test_da014_role_envelopes.py',
 'factory/python/tests/test_da014_product_role_trial.py',
 '--junitxml='+str(N/'pytest.xml')]
record['command']=cmd
try:
 assert available()
 with (N/'pytest.log').open('w') as output:
  child=subprocess.Popen(cmd,cwd=R,env=env,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
  record['pytest_exit_code']=child.wait(timeout=480)
 assert record['pytest_exit_code']==0 and not halt
 suite=ET.parse(N/'pytest.xml').getroot().find('testsuite')
 assert suite is not None and suite.get('tests')=='89'
 assert all(suite.get(key)=='0' for key in ('errors','failures','skipped'))
 record['pytest_case_counts']=dict(suite.attrib)
 assert available()
finally:
 done.set()
 if child and child.poll() is None:
  try:os.killpg(child.pid,signal.SIGTERM)
  except ProcessLookupError:pass
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:
   try:os.killpg(child.pid,signal.SIGKILL)
   except ProcessLookupError:pass
   child.wait()
 record['child_peak_rss_kib']=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
 record.update(halt=halt,source_clean_after=not git('status','--porcelain'),completed_epoch=time.time())
 (N/'provenance.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps(record),flush=True)
assert record['pytest_exit_code']==0 and not halt and record['source_clean_after']
