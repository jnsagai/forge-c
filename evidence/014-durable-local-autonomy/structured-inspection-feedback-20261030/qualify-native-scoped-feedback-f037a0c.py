"""Exact-source CPU-only qualification. An authenticated operator maintenance pause is a prerequisite."""
from pathlib import Path
import argparse,hashlib,json,os,resource,subprocess,sys,time
import xml.etree.ElementTree as ET
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';REV='f037a0cf1ccb8bdc035b0cc5348b3efe2b2aefc4'
N=P/'deployment/qualification-scoped-feedback-f037a0c-v1';B=P/'deployment/scoped-feedback-f037a0c-source.bundle'
parser=argparse.ArgumentParser();parser.add_argument('--check-only',action='store_true');args=parser.parse_args()
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.operations import Intent
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import immutable_json
from forge_factory.common import sha256_file
from forge_factory.reliability import isolation
intent=Intent().read()
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as store:
 busy=bool(Executions(store).pending())
 with store.tx() as c:
  busy=busy or bool(c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone())
  busy=busy or bool(c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone())
if busy or intent['mode']!='PAUSED':
 print(json.dumps({'status':'NOT_RUN_LIVE_WORK_OR_OPERATOR_MAINTENANCE_PAUSE_REQUIRED','source_revision':REV,'native_busy':busy,'operator_mode':intent['mode'],'model_requests':0,'deployment':False}));raise SystemExit(3)
if args.check_only:
 print(json.dumps({'status':'QUIESCENT_PAUSED_PRECONDITIONS_ONLY','source_revision':REV,'operator_epoch':intent['epoch'],'tests_run':False}));raise SystemExit(0)
assert isolation.backend()=='bubblewrap'
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
N.mkdir(mode=0o700);Q=N/'repo'
subprocess.run(['git','clone','--shared','--no-checkout',str(R),str(Q)],check=True,capture_output=True)
subprocess.run(['git','-C',str(Q),'fetch',str(B),'HEAD'],check=True,capture_output=True)
subprocess.run(['git','-C',str(Q),'checkout','--detach',REV],check=True,capture_output=True)
fixtures=[];vendor=[]
for example in ('examples/0009a-iwdg-ll','examples/0014d-st-cube-crc-idr-assisted'):
 ex=Path(example);spec=json.loads((R/ex/'workorder.json').read_text())
 for item in spec['inputs']:
  src=(R/ex/item['path']).resolve();dst=(Q/ex/item['path']).resolve();assert src.is_relative_to(R) and dst.is_relative_to(Q) and src.is_file()
  if dst.exists():continue
  assert subprocess.run(['git','-C',str(Q),'check-ignore','-q',str(dst.relative_to(Q))]).returncode==0
  dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(src.read_bytes());dst.chmod(0o444)
  fixtures.append({'path':str(dst.relative_to(Q)),'source_sha256':sha256_file(src),'copied_sha256':sha256_file(dst),'read_only':True})
 d=spec.get('delivery') or {};sources=([d['source']] if d.get('source') else [])+[x['source'] for x in d.get('dependencies',[]) if x.get('source')]
 for value in sources:
  p=Path(os.path.expandvars(value));assert p.is_dir() and p.resolve().is_relative_to((P/'inputs/st').resolve());vendor.append(p)
vendor=list(dict.fromkeys(vendor));immutable_json(N/'input-fixtures.json',{'copied_inputs':fixtures,'read_only_vendor_paths':[str(p) for p in vendor],'private_input_contents_published':False})
assert not subprocess.check_output(['git','-C',str(Q),'status','--porcelain'])
T=N/'scratch';T.mkdir(mode=0o777);T.chmod(0o777)
env={'PATH':':'.join(str(P/p) for p in ('venv/bin','toolchains/formal/bin','toolchains/LLVM-19.1.7-Linux-X64/bin','toolchains/plantuml'))+':/usr/bin:/bin','HOME':str(T),'TMPDIR':str(T),'LANG':'C.UTF-8','PYTHONPATH':str(Q/'factory/python'),'FORGE_REPO_ROOT':str(Q),'FORGE_DATA_ROOT':str(P),'FORGE_STATE_DIR':str(T/'state'),'FORGE_EVENTS_DIR':str(T/'events'),'FORGE_FABRO_LIVE':'0','PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','JAVA_TOOL_OPTIONS':'-Xms32m -Xmx384m -XX:CompressedClassSpaceSize=64m -XX:MaxMetaspaceSize=192m -XX:ReservedCodeCacheSize=64m -XX:ActiveProcessorCount=4'}
files=['test_lrtx_startup_refutation_scope.py','test_lrtx_complete_inspection_feedback.py','test_lrtx_open_point_provenance.py','test_lrtx_swe1.py','test_lrtx_p3.py','test_lrtx_v2_review.py','test_inspection_assessment_context.py','test_aspice_development.py']
command=[str(P/'venv/bin/python'),'-m','pytest','-vv','-p','no:cacheprovider','--rootdir',str(Q),*['factory/python/tests/'+p for p in files],'--junitxml='+str(T/'pytest.xml')]
passwd=N/'fixture-passwd';group=N/'fixture-group';passwd.write_text('root:x:0:0:root:/nonexistent:/usr/sbin/nologin\nforge-verifier:x:2001:2001:Qualification fixture:'+str(T)+':/usr/sbin/nologin\n');group.write_text('root:x:0:\nforge-verifier:x:2001:\n')
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[-4:]);os.nice(5);resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(360,360))
assert Intent().read()['mode']=='PAUSED' and Intent().read()['epoch']==intent['epoch']
argv=isolation.bubblewrap_argv('verifier',command,cwd=Q,env=env,writable=[T],readable=[Q,*vendor]);marker=argv.index('--chdir');argv[marker:marker]=['--ro-bind',str(passwd),'/etc/passwd','--ro-bind',str(group),'/etc/group']
started=time.time()
try:
 r=subprocess.run(argv,capture_output=True,timeout=600);code=r.returncode;output=r.stdout+r.stderr
except subprocess.TimeoutExpired as exc:
 code=124;output=(exc.stdout or b'')+(exc.stderr or b'')
(N/'pytest.log').write_bytes(output)
summary={}
if (T/'pytest.xml').exists():
 suite=next(ET.parse(T/'pytest.xml').getroot().iter('testsuite'));summary={k:int(suite.get(k)) for k in ('tests','failures','errors','skipped')}
out={'source_revision':REV,'source_clean_before':True,'source_clean_after':not subprocess.check_output(['git','-C',str(Q),'status','--porcelain']),'pytest_exit_code':code,'summary':summary,'command':command,'started':started,'finished':time.time(),'operator_epoch':intent['epoch'],'operator_intent_unchanged':Intent().read()['epoch']==intent['epoch'] and Intent().read()['mode']=='PAUSED','model_requests':0,'network':False,'gpu_exposed':False,'owner_identity_or_ssh_agent_exposed':False,'backend':isolation.backend(),'cpu_affinity':sorted(os.sched_getaffinity(0)),'address_space_limit_bytes':8*1024**3,'cpu_seconds_limit':360,'wall_seconds_limit':600,'bundle_sha256':sha256_file(B),'deployment':False,'automatic_pause_or_resume':False}
immutable_json(N/'provenance.json',out);print(json.dumps(out));raise SystemExit(code)
