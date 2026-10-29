"""Exact SDK contract tests, only after inference and existing verification resources are quiet."""
from pathlib import Path
import hashlib,json,os,resource,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';N=P/'deployment/qualification-focused-maintenance-c1f1378-v2';REV='c1f1378733af388b50ba1d6e5de37c16f3c0a9ee'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.operations import Intent
from forge_factory.reliability import isolation
assert Intent().read()['mode']=='RUNNING' and Intent().read()['epoch']==44
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as db:
 with db.tx() as c:
  busy=c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchall()
  verify=c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchall()
  if busy or verify:print(json.dumps({'status':'NOT_READY_EXISTING_WORKER_LIVE','model_requests':0}));raise SystemExit(3)
N.mkdir(mode=0o700);Q=N/'repo';B=P/'deployment/focused-maintenance-c1f1378-source.bundle'
subprocess.run(['git','clone','--shared','--no-checkout',str(R),str(Q)],capture_output=True,check=True)
subprocess.run(['git','-C',str(Q),'fetch',str(B),'HEAD'],capture_output=True,check=True)
subprocess.run(['git','-C',str(Q),'checkout','--detach',REV],capture_output=True,check=True)
assert not subprocess.check_output(['git','-C',str(Q),'status','--porcelain'])
T=N/'scratch';T.mkdir(mode=0o777);T.chmod(0o777)
env={'PATH':str(P/'venv/bin')+':/usr/bin:/bin','HOME':str(T),'TMPDIR':str(T),'LANG':'C.UTF-8','PYTHONPATH':str(Q/'factory/python'),'FORGE_REPO_ROOT':str(Q),'FORGE_DATA_ROOT':str(P),'FORGE_STATE_DIR':str(T/'state'),'FORGE_EVENTS_DIR':str(T/'events'),'FORGE_FABRO_LIVE':'0','PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'}
os.sched_setaffinity(0,[sorted(os.sched_getaffinity(0))[0]]);os.nice(15)
command=[str(P/'venv/bin/python'),'-m','pytest','-q','-p','no:cacheprovider','--rootdir',str(Q),'factory/python/tests/test_mcp_input_schema_metadata.py','factory/python/tests/test_afo_retained_work_unit.py','--junitxml='+str(T/'pytest.xml')]
resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3));resource.setrlimit(resource.RLIMIT_CPU,(45,45))
start=time.time();r=isolation.execute('verifier',command,cwd=Q,env=env,writable=[T],readable=[Q],timeout=60);(N/'pytest.log').write_bytes(r.stdout+r.stderr)
report={'source_revision':REV,'source_clean_before':True,'source_clean_after':not subprocess.check_output(['git','-C',str(Q),'status','--porcelain']),'pytest_exit_code':r.returncode,'command':command,'started':start,'finished':time.time(),'model_requests':0,'gpu_devices_exposed':False,'network':False,'cpu_affinity':sorted(os.sched_getaffinity(0)),'address_space_limit_bytes':1024**3,'cpu_seconds_limit':45,'backend':isolation.backend(),'bundle_sha256':hashlib.sha256(B.read_bytes()).hexdigest(),'production_changed':False};(N/'provenance.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));raise SystemExit(r.returncode)
