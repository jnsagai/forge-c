"""Owner-authorized prefix-only correction; existing independent CRE gates remain authoritative."""
from pathlib import Path
import copy,json,os,resource,signal,subprocess,sys,time,xml.etree.ElementTree as ET
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';N=P/'deployment/qualification-maintenance-binding-5a28820-v1';Q=N/'repo';O=P/'deployment/rcc-signature-binding-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
os.environ['FORGE_REPO_ROOT']=str(Q);sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.afo import operations,authz,policy,maintainer as M,maintenance_binding as B
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.completion_receipt import Context
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.common import sha256_file,utc_now
from forge_factory.reliability import isolation
from forge_factory.reliability.store import CREStore
from forge_factory.reliability.policy import load as cre_policy
s=json.loads((O/'scope.json').read_text());assert digest(s)=='362cc3f0529921f4b9fad691a2adf7eaf0bb25ff884c69ff86721ef188f793b0'
assert json.loads((O/'owner-approval.json').read_text())['scope_sha256']==digest(s)
S=Store();I=operations.Intent();L=MissionLedger(S)
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
def fence():
 if time.time()>=s['expiry_epoch'] or I.read()['mode']!='RUNNING' or I.read()['epoch']!=s['operator_epoch'] or Executions(S).pending():return False
 with S.tx() as c:
  return not any((c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone(),c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone(),c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()))
assert fence()
proof=json.loads((N/'provenance.json').read_text());assert proof['source_revision']==s['qualified_kernel_revision'] and proof['pytest_exit_code']==0 and proof['source_clean_before'] and proof['source_clean_after']
suite=next(ET.parse(N/'scratch/pytest.xml').getroot().iter('testsuite'));assert suite.get('tests')=='96' and all(suite.get(k)=='0' for k in ('errors','failures','skipped'))
assert git(Q,'rev-parse','HEAD')==s['qualified_kernel_revision'] and not git(Q,'status','--porcelain')
assert git(R,'rev-parse','HEAD')==s['runtime_revision'] and not git(R,'status','--porcelain')
assert isolation.backend() in ('bubblewrap','podman'), 'INDEPENDENT_OS_ISOLATION_REQUIRED'
g=json.loads((O/'authorization.json').read_text());assert authz.signature_valid(g,O/'authorization-message.bin.sig',authz.ALLOWED_SIGNERS)
assert g['signed_runbook_ref']=='maintenance-signature-binding-014:'+digest(s)
with S.tx() as c:j=json.loads(c.execute('SELECT record FROM afo_local_agent_jobs WHERE job_id=?',(s['job_id'],)).fetchone()[0])
Context.from_job(S,j['job_id']);case=json.loads(Path(j['case']).read_text());sub,receipt=M.submission(case,require_receipt=True)
assert sub['candidate']==s['candidate'] and sha256_file(Path(j['case']))==s['case_sha256'] and digest(receipt)==s['original_receipt_sha256']
assert digest(json.loads(Path(sub['staged']['manifest']).read_text()))==s['original_manifest_sha256']
before=json.loads((O/'all-missions-after.json').read_text())
eff=policy.load(log=False);assert eff.sha256==s['policy_sha256']

# Qualification runner bootstrap: expose installed pinned toolchains, bound Java reservations.
os.environ['PATH']=str(P/'toolchains/formal/bin')+':'+str(P/'toolchains/LLVM-19.1.7-Linux-X64/bin')+':'+str(P/'toolchains/plantuml')+':'+str(P/'venv/bin')+':/usr/bin:/bin'
os.environ['JAVA_TOOL_OPTIONS']='-Xms32m -Xmx384m -XX:CompressedClassSpaceSize=64m -XX:MaxMetaspaceSize=192m -XX:ReservedCodeCacheSize=64m -XX:ActiveProcessorCount=4'
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
assert fence()
for mid,record in before.items():assert L.snapshot(mid)==record
ref=json.loads((O/'binding-reference.json').read_text())
bound=B.bound_submission(S,case,sub,ref)
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[-4:]);os.nice(5)
resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(720,720))
def timeout(*_):raise TimeoutError('BOUNDED_OWNER_CRE_REQUALIFICATION_TIMEOUT')
signal.signal(signal.SIGALRM,timeout);signal.alarm(min(1200,max(1,int(s['expiry_epoch']-time.time()))))
from forge_factory.reliability import reproduce as RR
reps,issues=RR.load_manifest();assert not issues
ids=['RPR-004','RPR-015','RPR-018','RPR-032','RPR-060','RPR-064','RPR-065','RPR-067']
C=CREStore();cp=cre_policy()
with RR.WorktreePool(R) as pool:runs=RR.run_many(C,cp,ids,case['base'],'BASELINE',pool,reps)
immutable_json(O/'environment-baseline-recheck.json',{'runs':runs,'path':os.environ['PATH'],'java_options':os.environ['JAVA_TOOL_OPTIONS'],'address_space_limit_bytes':8*1024**3,'at':utc_now()})
print(json.dumps({'status':'BASELINE_ENVIRONMENT_RECHECK','runs':[{k:r[k] for k in ('run_id','reproducer_id','verdict')} for r in runs]}),flush=True)
assert all(r['verdict']=='SYMPTOM_ABSENT' for r in runs),'BASELINE_PREREQUISITES_STILL_FAIL'
assert fence()
triage=M.triage(case,bound,C,cp);assert triage['ok'],triage
decision=M.evaluate(case,bound,C,cp)
outcome={'ELIGIBLE_FOR_OFFLINE_REVIEW':'ELIGIBLE_FOR_OFFLINE_REVIEW','INCONCLUSIVE':'INCONCLUSIVE'}.get(decision['decision'],'REJECTED')
assert decision['allowed_auto_deployment'] is False
result=M.record(S,case,bound,outcome,outcome,capa_id=triage['capa_id'],promotion_id=decision['decision_id'],tests_ref='owner-environment-requalification:'+digest(s),evidence=['administrative-binding:'+ref['binding_id'],'promotion-decision:'+decision['decision_id'],'reproducer-run:'+triage['baseline_run']['run_id'],'qualification-environment:installed-pinned-toolchains-bounded-java'])
signal.alarm(0)
assert fence()
for mid,record in before.items():assert L.snapshot(mid)==record
assert M.submission(case,require_receipt=True)==(sub,receipt)
immutable_json(O/'environment-requalification-decision.json',decision)
immutable_json(O/'environment-requalification-result.json',{'status':'EXISTING_BOUND_CANDIDATE_REQUALIFIED','proposal':result,'new_model_requests':0,'new_engineering_attempts':0,'new_protocol_corrections':0,'mission_histories_unchanged':True,'runtime_source_deployed':False,'at':utc_now()})
print(json.dumps({'status':'EXISTING_BOUND_CANDIDATE_REQUALIFIED','outcome':outcome,'decision_id':decision['decision_id'],'gates':decision['hard_gates']}),flush=True)
