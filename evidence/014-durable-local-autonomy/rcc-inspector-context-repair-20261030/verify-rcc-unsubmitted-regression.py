"""Independent frozen check of exact native-written bytes; does not forge a submission/receipt."""
from pathlib import Path
import hashlib,json,os,resource,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/rcc-inspector-context-repair-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import immutable_json,immutable_bytes
from forge_factory.afo.operations import Intent
from forge_factory.reliability import isolation
case=json.loads((P/'state/afo/maintainer/mnt-7ab1af2aa4e1d7b4-a1/case.json').read_text());src=Path(case['src'])
assert Intent().read()['mode']=='RUNNING' and Intent().read()['epoch']==52
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as S:
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
  j=json.loads(c.execute('SELECT record FROM afo_local_agent_jobs WHERE job_id=?',('afo-agent-ebfdb7f98a3999fbaf747d8a',)).fetchone()[0])
 assert j['state']=='FAILED'
 e=Executions(S).get(j['job_id']);assert e['execution_liveness']=='QUIESCENT' and e['resource_lease']=='RELEASED'
paths=subprocess.check_output(['git','-C',str(src),'diff','--name-only'],text=True).splitlines()
rel='factory/python/forge_factory/lrtx/structured.py';assert paths==[rel]
raw=(src/rel).read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert sha=='f543f709245eb9d8458a1ecc9f291afece97816bca6c136a4dbf5e258825b3c9'
V=O/'independent-unsubmitted-regression-v1';V.mkdir(mode=0o700)
immutable_bytes(V/'structured.py',raw)
immutable_bytes(V/'raw-diff.patch',subprocess.check_output(['git','-C',str(src),'diff','--',rel]))
T=V/'scratch';T.mkdir(mode=0o777);T.chmod(0o777)
env={'PATH':str(P/'venv/bin')+':/usr/bin:/bin','PYTHONPATH':str(src/'factory/python'),
 'FORGE_REPO_ROOT':str(src),'FORGE_DATA_ROOT':str(P),'FORGE_STATE_DIR':str(T/'state'),
 'FORGE_EVENTS_DIR':str(T/'events'),'TMPDIR':str(T),'HOME':str(T),'LANG':'C.UTF-8',
 'F014_CONTEXT_SOURCE':str(src),'F014_CONTEXT_FROZEN':str(O/'frozen-original-swe1'),
 'PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','FORGE_FABRO_LIVE':'0'}
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[-4:]);os.nice(5)
resource.setrlimit(resource.RLIMIT_AS,(1536*1024**2,1536*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(120,120))
command=[str(P/'venv/bin/python'),'-m','pytest','-q','-p','no:cacheprovider',
 str(src/'factory/python/tests/test_da014_settled_usage.py')+'::test_structured_refusal_preserves_bounded_typed_reason_without_body_leak','--junitxml='+str(T/'pytest.xml')]
started=time.time()
r=isolation.execute('verifier',command,cwd=src,env=env,writable=[T],
 readable=[src],timeout=180)
(V/'pytest.log').write_bytes(r.stdout+r.stderr)
assert hashlib.sha256((src/rel).read_bytes()).hexdigest()==sha
result={'status':'PASS_INHERITED_REGRESSION' if r.returncode==0 else 'FAIL_INHERITED_REGRESSION',
 'source_revision':case['base'],'source_job_id':j['job_id'],'source_native_run_id':j['run_id'],
 'native_write_seq':137,'source_sha256':sha,'source_bytes':len(raw),'paths':paths,
 'source_submission_present':False,'original_job_state':j['state'],'completion_receipt_created':False,
 'operator_authored_code':False,'pytest_exit_code':r.returncode,'command':command,
 'started':started,'finished':time.time(),'backend':isolation.backend(),'model_requests':0,
 'gpu_exposed':False,'network':False}
immutable_json(V/'result.json',result);print(json.dumps(result));raise SystemExit(r.returncode)
