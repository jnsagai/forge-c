"""Exact SDK contract tests, only after inference and existing verification resources are quiet."""
from pathlib import Path
import hashlib,json,os,resource,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';N=P/'deployment/qualification-commit-reconciliation-53e1234-v1';REV='53e1234709eeaea91aaf681d1d5068659c85762a'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.operations import Intent
from forge_factory.reliability import isolation
assert Intent().read()['mode']=='PAUSED' and Intent().read()['epoch']==55
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as db:
 with db.tx() as c:
  busy=c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchall()
  verify=c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchall()
  if busy or verify:print(json.dumps({'status':'NOT_READY_EXISTING_WORKER_LIVE','model_requests':0}));raise SystemExit(3)
N.mkdir(mode=0o700);Q=N/'repo';B=P/'deployment/commit-reconciliation-53e1234-source.bundle'
subprocess.run(['git','clone','--shared','--no-checkout',str(R),str(Q)],capture_output=True,check=True)
subprocess.run(['git','-C',str(Q),'fetch',str(B),'HEAD'],capture_output=True,check=True)
subprocess.run(['git','-C',str(Q),'checkout','--detach',REV],capture_output=True,check=True)
assert not subprocess.check_output(['git','-C',str(Q),'status','--porcelain'])
T=N/'scratch';T.mkdir(mode=0o777);T.chmod(0o777)
env={'PATH':str(P/'venv/bin')+':/usr/bin:/bin','HOME':str(T),'TMPDIR':str(T),'LANG':'C.UTF-8','PYTHONPATH':str(Q/'factory/python'),'FORGE_REPO_ROOT':str(Q),'FORGE_DATA_ROOT':str(P),'FORGE_STATE_DIR':str(T/'state'),'FORGE_EVENTS_DIR':str(T/'events'),'FORGE_FABRO_LIVE':'0','PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'}
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[-4:]);os.nice(5)
command=[str(P/'venv/bin/python'),'-m','pytest','-vv','-p','no:cacheprovider','--rootdir',str(Q),'factory/python/tests/test_afo_commit_reconciliation.py','factory/python/tests/test_afo_source_edits.py','factory/python/tests/test_afo_m5_maintainer.py','factory/python/tests/test_afo_maintenance_rework.py','factory/python/tests/test_afo_retained_work_unit.py','factory/python/tests/test_afo_review_disposition.py','factory/python/tests/test_mcp_input_schema_metadata.py','-k','not test_candidate_tests_run_as_sandbox_uid_without_credentials_or_network','--junitxml='+str(T/'pytest.xml')]
resource.setrlimit(resource.RLIMIT_AS,(1536*1024**2,1536*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(240,240))
start=time.time()
try:
 assert isolation.backend()=='bubblewrap'
 passwd=N/'fixture-passwd';group=N/'fixture-group'
 passwd.write_text('root:x:0:0:root:/nonexistent:/usr/sbin/nologin\nforge-verifier:x:2001:2001:Qualification fixture:'+str(T)+':/usr/sbin/nologin\n')
 group.write_text('root:x:0:\nforge-verifier:x:2001:\n')
 argv=isolation.bubblewrap_argv('verifier',command,cwd=Q,env=env,writable=[T],readable=[Q])
 marker=argv.index('--chdir')
 argv[marker:marker]=['--ro-bind',str(passwd),'/etc/passwd','--ro-bind',str(group),'/etc/group']
 r=subprocess.run(argv,capture_output=True,timeout=480)
except subprocess.TimeoutExpired as exc:
 (N/'pytest.log').write_bytes((exc.stdout or b'')+(exc.stderr or b''))
 (N/'timeout.json').write_text(json.dumps({'status':'FAILED_TIMEOUT','source_revision':REV,'wall_seconds':480,'model_requests':0,'partial_output_preserved':True}))
 print(json.dumps({'status':'FAILED_TIMEOUT','source_revision':REV,'wall_seconds':480,'model_requests':0}));raise SystemExit(2)
(N/'pytest.log').write_bytes(r.stdout+r.stderr)
report={'source_revision':REV,'source_clean_before':True,'source_clean_after':not subprocess.check_output(['git','-C',str(Q),'status','--porcelain']),'pytest_exit_code':r.returncode,'command':command,'started':start,'finished':time.time(),'model_requests':0,'gpu_devices_exposed':False,'network':False,'cpu_affinity':sorted(os.sched_getaffinity(0)),'address_space_limit_bytes':1536*1024**2,'cpu_seconds_limit':240,'backend':isolation.backend(),'bundle_sha256':hashlib.sha256(B.read_bytes()).hexdigest(),'production_changed':False,'qualification_passwd_fixture':{'uid':2001,'gid':2001,'passwd_sha256':hashlib.sha256(passwd.read_bytes()).hexdigest(),'group_sha256':hashlib.sha256(group.read_bytes()).hexdigest()},'owner_identity_or_ssh_agent_exposed':False};(N/'provenance.json').write_text(json.dumps(report,indent=2));print(json.dumps(report));raise SystemExit(r.returncode)
