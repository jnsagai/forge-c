from pathlib import Path
import hashlib,json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';N=P/'deployment/qualification-afo-max-context-92c49a6-v2';REV='92c49a6adde181737af19bb32a5efbd2130e9cd4'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations
from forge_factory.afo.queue import ReadSnapshot
I=operations.Intent();assert I.read()['mode']=='RUNNING' and I.read()['epoch']==40
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as db:
 with db.tx() as c:
  assert not c.execute("SELECT record FROM afo_execution_liveness WHERE json_extract(record,'$.resource_lease')='HELD'").fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
N.mkdir(mode=0o700);Q=N/'repo';B=P/'deployment/afo-max-context-from979.bundle'
subprocess.run(['git','clone','--shared','--no-checkout',str(R),str(Q)],capture_output=True,check=True)
subprocess.run(['git','-C',str(Q),'fetch',str(B),'HEAD'],capture_output=True,check=True)
subprocess.run(['git','-C',str(Q),'checkout','--detach',REV],capture_output=True,check=True)
assert not subprocess.check_output(['git','-C',str(Q),'status','--porcelain'])
import tarfile
with tarfile.open(P/'deployment/afo-max-context-test-inputs.tar') as tf:
 for m in tf:
  assert m.isfile() and m.name.startswith('examples/') and '..' not in Path(m.name).parts
  target=Q/m.name;raw=tf.extractfile(m).read()
  if target.exists():assert target.read_bytes()==raw
  else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
T=N/'tmp';T.mkdir();env={'PATH':str(P/'venv/bin')+':/usr/bin:/bin','HOME':str(T),'TMPDIR':str(T),'LANG':'C.UTF-8','PYTHONPATH':str(Q/'factory/python'),'FORGE_REPO_ROOT':str(Q),'FORGE_DATA_ROOT':str(P),'FORGE_STATE_DIR':str(T/'state'),'FORGE_EVENTS_DIR':str(T/'events'),'FORGE_FABRO_LIVE':'0','PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'}
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);os.nice(10)
command=[str(P/'venv/bin/python'),'-m','pytest','-q','-p','no:cacheprovider','factory/python/tests/test_da014_llama_server.py','factory/python/tests/test_da014_product_role_trial.py','factory/python/tests/test_da014_q38_quality_profile.py','--junitxml='+str(N/'pytest.xml')]
start=time.time();r=subprocess.run(command,cwd=Q,env=env,capture_output=True,timeout=180);(N/'pytest.log').write_bytes(r.stdout+r.stderr)
after=not subprocess.check_output(['git','-C',str(Q),'status','--porcelain']);result={'source_revision':REV,'source_clean_before':True,'source_clean_after':after,'pytest_exit_code':r.returncode,'command':command,'started':start,'finished':time.time(),'model_requests':0,'gpu_tests':False,'bundle_sha256':hashlib.sha256(B.read_bytes()).hexdigest()};(N/'provenance.json').write_text(json.dumps(result,indent=2));print(json.dumps(result));raise SystemExit(r.returncode)
