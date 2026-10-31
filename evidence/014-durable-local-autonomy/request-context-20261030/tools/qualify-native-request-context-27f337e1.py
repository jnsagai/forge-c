"""Exact-source CPU-only qualification. Owner expected intent must remain unchanged; running mode is CPU-only in a separate sandbox; this worker never resumes the factory."""
from pathlib import Path
import argparse,hashlib,json,os,resource,subprocess,sys,time
import xml.etree.ElementTree as ET
def run_fenced(argv, log_path, read_intent, expected_epoch, *, timeout_s=600, poll_s=0.5, expected_mode="PAUSED"):
    """One owned verifier process group; cancel on newer operator intent."""
    import signal
    reason = None
    deadline = time.monotonic() + timeout_s
    with log_path.open("wb") as log:
        child = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        while child.poll() is None:
            try:
                current = read_intent()
            except Exception:
                reason = "OPERATOR_INTENT_UNOBSERVABLE"
                break
            if current["mode"] != expected_mode or current["epoch"] != expected_epoch:
                reason = "OPERATOR_INTENT_SUPERSEDED"
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                reason = "VERIFIER_WALL_TIMEOUT"
                break
            time.sleep(min(poll_s, remaining))
        if reason:
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait(timeout=5)
        else:
            child.wait()
    return {"code": 125 if reason in ("OPERATOR_INTENT_SUPERSEDED", "OPERATOR_INTENT_UNOBSERVABLE") else 124 if reason else child.returncode,
            "termination_reason": reason, "child_pid": child.pid}

P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';REV='27f337e149373b0547b159fcdf880ae025fab920'
B=P/'deployment/request-context-27f337e1.bundle'
parser=argparse.ArgumentParser();parser.add_argument('--while-running',action='store_true');parser.add_argument('--check-only',action='store_true');parser.add_argument('--cohort',choices=('context',),default='context');parser.add_argument('--expected-epoch',type=int,required=True);args=parser.parse_args()
N=P/('deployment/qualification-request-context-27f337e1-epoch'+str(args.expected_epoch)+'-v1')
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
expected_mode='RUNNING' if args.while_running else 'PAUSED'
if (busy and not args.while_running) or intent['mode']!=expected_mode or intent['epoch']!=args.expected_epoch:
 print(json.dumps({'status':'NOT_RUN_QUIESCENT_PAUSED_EXPECTED_EPOCH_REQUIRED','source_revision':REV,'native_busy':busy,'operator_mode':intent['mode'],'operator_epoch':intent['epoch'],'expected_epoch':args.expected_epoch,'model_requests':0,'deployment':False}));raise SystemExit(3)
if args.check_only:
 print(json.dumps({'status':'QUIESCENT_PAUSED_EXPECTED_EPOCH_PRECONDITIONS_ONLY','source_revision':REV,'operator_epoch':intent['epoch'],'tests_run':False}));raise SystemExit(0)
assert isolation.backend()=='bubblewrap'
# Real RAM is bounded by the owner-created systemd scope. Renode/.NET needs
# a larger finite virtual-address reservation than its actual working set.
unit='forge-qual-request-context-27f337e1-'+str(args.expected_epoch)+'.scope'
limits=subprocess.check_output(['systemctl','--user','show',unit,'-p','MemoryMax,MemorySwapMax,CPUQuotaPerSecUSec'],text=True)
assert 'MemoryMax=8589934592' in limits and 'MemorySwapMax=0' in limits
assert unit in Path('/proc/self/cgroup').read_text()
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
N.mkdir(mode=0o700);Q=N/'repo'
subprocess.run(['git','clone','--shared','--no-checkout',str(R),str(Q)],check=True,capture_output=True)
subprocess.run(['git','-C',str(Q),'fetch',str(B),'HEAD'],check=True,capture_output=True)
subprocess.run(['git','-C',str(Q),'checkout','--detach',REV],check=True,capture_output=True)
fixtures=[];vendor=[]
for example in ('examples/0009a-iwdg-ll','examples/0002a-arm_55_rcc_ll','examples/0002b-arm_55_rcc_hal','examples/0014d-st-cube-crc-idr-assisted','examples/0014f-st-cube-crc-idr-qm'):
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
E=N/'receipts';E.mkdir(mode=0o777);E.chmod(0o777)
fabro=Path(os.environ.get('FORGE_FABRO_BIN',str(P/'bin/fabro')));assert fabro.is_file()
env={'FORGE_FABRO_BIN':str(fabro),'PATH':':'.join(str(P/p) for p in ('venv/bin','toolchains/formal/bin','toolchains/LLVM-19.1.7-Linux-X64/bin','toolchains/plantuml'))+':/usr/bin:/bin','HOME':str(T),'TMPDIR':str(T),'LANG':'C.UTF-8','PYTHONPATH':str(Q/'factory/python'),'FORGE_REPO_ROOT':str(Q),'FORGE_DATA_ROOT':str(P),'FORGE_STATE_DIR':str(T/'state'),'FORGE_EVENTS_DIR':str(T/'events'),'FORGE_FABRO_LIVE':'0','PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','JAVA_TOOL_OPTIONS':'-Xms32m -Xmx384m -XX:CompressedClassSpaceSize=64m -XX:MaxMetaspaceSize=192m -XX:ReservedCodeCacheSize=64m -XX:ActiveProcessorCount=4'}
files=['test_lrtx_native_request_measurement.py','test_lrtx_review_source_capacity.py','test_da014_workflow_capacity.py','test_da014_role_reasoning.py','test_da014_integration.py','test_lrtx_scope_section_inventory.py','test_lrtx_coherent_obligations.py','test_lrtx_swe1.py','test_da014_product_role_trial.py','test_da014_wal_session.py','test_afo_m2_queue.py','test_afo_m1_services.py','test_afo_m6_operations.py','test_da014_non_thinking.py','test_reasoning_comparison_preparation.py','test_mtp_comparison_preparation.py','test_da014_configuration_comparison.py','test_da014_qualification.py','test_da014_qualification_inputs.py','test_lrtx_profile.py','test_llm_gateway.py','test_da014_llama_server.py','test_da014_diagnosis_context_contract.py','test_da014_two_step.py','test_da014_qualification_reservations.py','test_da014_proposal_diagnostics.py','test_da014_role_envelopes.py','test_da014_protocol_faults.py','test_afo_local_autonomy.py']
command=[str(P/'venv/bin/python'),'-m','pytest','-vv','-p','no:cacheprovider','--rootdir',str(Q),*['factory/python/tests/'+p for p in files],'--junitxml='+str(T/'pytest.xml')]
passwd=N/'fixture-passwd';group=N/'fixture-group';passwd.write_text('root:x:0:0:root:/nonexistent:/usr/sbin/nologin\nforge-verifier:x:2001:2001:Qualification fixture:'+str(T)+':/usr/sbin/nologin\n');group.write_text('root:x:0:\nforge-verifier:x:2001:\n')
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[-4:]);os.nice(5);resource.setrlimit(resource.RLIMIT_AS,(96*1024**3,96*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(1800,1800))
assert Intent().read()['mode']==expected_mode and Intent().read()['epoch']==intent['epoch']
argv=isolation.bubblewrap_argv('verifier',command,cwd=Q,env=env,writable=[T,E],readable=[Q,*vendor,fabro,P/'ollama-0.34.0/bin/ollama',R/'.git/objects']);marker=argv.index('--chdir');argv[marker:marker]=['--ro-bind',str(passwd),'/etc/passwd','--ro-bind',str(group),'/etc/group']
# RAM scratch accelerates fixtures only. Copy the real JUnit back before sandbox exit.
copy_wrapper="import os,subprocess,sys,shutil; from pathlib import Path; p=Path('/tmp/forge-runtime'); p.mkdir(mode=0o700); os.environ['XDG_RUNTIME_DIR']=str(p); r=subprocess.call(sys.argv[3:]); p=Path(sys.argv[1]); shutil.copyfile(p,sys.argv[2]) if p.is_file() else None; sys.exit(r)"
command=[str(P/'venv/bin/python'),'-c',copy_wrapper,str(T/'pytest.xml'),str(E/'pytest.xml'),*command]
argv=isolation.bubblewrap_argv('verifier',command,cwd=Q,env=env,writable=[T,E],readable=[Q,*vendor,fabro,P/'ollama-0.34.0/bin/ollama',R/'.git/objects'])
marker=argv.index('--chdir');argv[marker:marker]=['--ro-bind',str(passwd),'/etc/passwd','--ro-bind',str(group),'/etc/group']
marker=next(i for i,x in enumerate(argv[:-2]) if x=='--bind' and argv[i+1]==str(T) and argv[i+2]==str(T));argv[marker:marker+3]=['--perms','0777','--tmpfs',str(T)]
started=time.time()
run=run_fenced(argv,N/'pytest.log',Intent().read,intent['epoch'],expected_mode=expected_mode)
code=run['code']
summary={}
if (E/'pytest.xml').exists():
 suite=next(ET.parse(E/'pytest.xml').getroot().iter('testsuite'));summary={k:int(suite.get(k)) for k in ('tests','failures','errors','skipped')}
out={'source_revision':REV,'qualification_mode':'BOUNDED_CPU_ONLY_PARALLEL_TO_PRODUCT' if args.while_running else 'QUIESCENT_PAUSED','production_native_busy_at_start':busy,'source_clean_before':True,'source_clean_after':not subprocess.check_output(['git','-C',str(Q),'status','--porcelain']),'pytest_exit_code':code,'summary':summary,'command':command,'started':started,'finished':time.time(),'operator_epoch':intent['epoch'],'operator_intent_unchanged':Intent().read()['epoch']==intent['epoch'] and Intent().read()['mode']==expected_mode,'model_requests':0,'network':False,'gpu_exposed':False,'owner_identity_or_ssh_agent_exposed':False,'backend':isolation.backend(),'cpu_affinity':sorted(os.sched_getaffinity(0)),'address_space_limit_bytes':96*1024**3,'physical_memory_limit_bytes':8*1024**3,'swap_limit_bytes':0,'cgroup_limits':limits,'cgroup_unit':unit,'cpu_seconds_limit':1800,'wall_seconds_limit':600,'bundle_sha256':sha256_file(B),'temporary_fixture_storage':'RAM_TMPFS_CGROUP_BOUNDED','persisted_receipts':str(E),'deployment':False,'automatic_pause_or_resume':False,'termination_reason':run['termination_reason'],'runner_sha256':sha256_file(Path(__file__))}
immutable_json(N/'provenance.json',out);print(json.dumps(out));raise SystemExit(code)
