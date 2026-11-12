"""Independent frozen check of exact native-written bytes; does not forge a submission/receipt."""
from pathlib import Path
import hashlib,json,os,resource,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/rcc-context-completion-20261030-v1';F=P/'deployment/rcc-inspector-context-repair-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import immutable_json,immutable_bytes
from forge_factory.afo.operations import Intent
from forge_factory.reliability import isolation
scope=json.loads((O/'scope.json').read_text())
assert Intent().read()['mode']=='RUNNING' and Intent().read()['epoch']==54
assert time.time()<scope['deadline_epoch']
from forge_factory.afo import maintainer as M
from forge_factory.afo.completion_receipt import Context
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as S:
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
  jobs=[json.loads(r[0]) for r in c.execute('SELECT record FROM afo_local_agent_jobs WHERE order_id=?',(scope['new_order_id'],))]
 valid=[]
 for job in jobs:
  case=json.loads(Path(job['case']).read_text())
  proposal=S.proposal(case['proposal_id'])
  if proposal and proposal['status'] in ('PUBLISHED','ELIGIBLE_FOR_OFFLINE_REVIEW'):valid.append((job,case,proposal))
 assert len(valid)==1, 'NO_SINGLE_INDEPENDENTLY_ELIGIBLE_RECEIPTED_CANDIDATE'
 j,case,proposal=valid[0];Context.from_job(S,j['job_id'])
 e=Executions(S).get(j['job_id']);assert e['execution_liveness']=='QUIESCENT' and e['resource_lease']=='RELEASED'
 sub,receipt=M.submission(case,require_receipt=True)
 assert not sub['veto'] and sub['candidate']==proposal['record']['candidate_commit']
src=Path(case['src']);rel='factory/python/forge_factory/lrtx/structured.py'
assert subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()==sub['candidate']
assert not subprocess.check_output(['git','-C',str(src),'status','--porcelain'])
paths=M.changed_paths(case['base'],sub['candidate'],src)
assert rel in paths and all(x==rel or x.startswith(M.CANDIDATE_TESTS) for x in paths)
raw=(src/rel).read_bytes();sha=hashlib.sha256(raw).hexdigest()
assert 'time.monetic(' not in raw.decode()
assert hashlib.sha256((F/'test_frozen_rcc_inspector_context_v2.py').read_bytes()).hexdigest()=='239400d5e338b7b2e84716b4b5ca56b6e0cc197a623bd0e97ea2eeeddec6319d'
V=O/('independent-receipted-'+sub['candidate'][:12]);V.mkdir(mode=0o700)
immutable_bytes(V/'structured.py',raw)
immutable_bytes(V/'raw-diff.patch',subprocess.check_output(['git','-C',str(src),'diff',case['base'],sub['candidate']]))
T=V/'scratch';T.mkdir(mode=0o777);T.chmod(0o777)
env={'PATH':str(P/'venv/bin')+':/usr/bin:/bin','PYTHONPATH':str(src/'factory/python'),
 'FORGE_REPO_ROOT':str(src),'FORGE_DATA_ROOT':str(P),'FORGE_STATE_DIR':str(T/'state'),
 'FORGE_EVENTS_DIR':str(T/'events'),'TMPDIR':str(T),'HOME':str(T),'LANG':'C.UTF-8',
 'F014_CONTEXT_SOURCE':str(src),'F014_CONTEXT_FROZEN':str(F/'frozen-original-swe1'),
 'PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','FORGE_FABRO_LIVE':'0'}
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[-4:]);os.nice(5)
resource.setrlimit(resource.RLIMIT_AS,(1536*1024**2,1536*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(120,120))
command=[str(P/'venv/bin/python'),'-m','pytest','-q','-p','no:cacheprovider',
 str(F/'test_frozen_rcc_inspector_context_v2.py'),str(src/'factory/python/tests/test_da014_settled_usage.py'),'--junitxml='+str(T/'pytest.xml')]
started=time.time()
r=isolation.execute('verifier',command,cwd=src,env=env,writable=[T],
 readable=[src,F/'test_frozen_rcc_inspector_context_v2.py',F/'frozen-original-swe1'],timeout=180)
(V/'pytest.log').write_bytes(r.stdout+r.stderr)
assert hashlib.sha256((src/rel).read_bytes()).hexdigest()==sha
result={'status':'PASS_FROZEN_CONTEXT_AND_SETTLED_USAGE' if r.returncode==0 else 'FAIL_FROZEN_SCOPE',
 'source_revision':case['base'],'source_job_id':j['job_id'],'source_native_run_id':j['run_id'],
 'candidate_commit':sub['candidate'],'submission_receipt_sha256':hashlib.sha256((M.case_dir(case['proposal_id'])/'submission-receipt.json').read_bytes()).hexdigest(),'cre_status':proposal['status'],'source_sha256':sha,'source_bytes':len(raw),'paths':paths,
 'source_submission_present':True,'original_job_state':j['state'],'completion_receipt_created':False,
 'operator_authored_code':False,'pytest_exit_code':r.returncode,'command':command,
 'started':started,'finished':time.time(),'backend':isolation.backend(),'model_requests':0,
 'gpu_exposed':False,'network':False}
immutable_json(V/'result.json',result);print(json.dumps(result));raise SystemExit(r.returncode)
