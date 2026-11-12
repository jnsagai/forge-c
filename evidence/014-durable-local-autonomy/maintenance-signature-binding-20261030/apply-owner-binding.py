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
before=json.loads((O/'all-missions-before.json').read_text())
eff=policy.load(log=False);assert eff.sha256==s['policy_sha256']
with I.lock():
 assert fence()
 if not (O/'binding-reference.json').exists():
  assert S.proposal(case['proposal_id'])['record_sha256']==s['source_proposal_record_sha256']
  for mid,record in before.items():assert L.snapshot(mid)==record
  immutable_json(O/'database-backup.json',S.backup(O/'conductor-before.sqlite3'))
 immutable_json(authz.AUTH_DIR/(g['authorization_id']+'.json'),g)
 immutable_bytes(authz.AUTH_DIR/g['signature_ref'],(O/'authorization-message.bin.sig').read_bytes())
 allowed=authz.verify(g,policy_sha256=eff.sha256,mode=eff.mode,action='recover_workorder',request={'order_id':s['request_id'],'driver_class':'LL','model':j['model']});assert allowed.allow,allowed
 ref=B.prepare(S,j,eff,verification_fence=fence);immutable_json(O/'binding-reference.json',ref)
print(json.dumps({'status':'PREFIX_BINDING_READY_RUNNING_UNCHANGED_CRE','binding_id':ref['binding_id'],'at':utc_now()}),flush=True)
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[-4:]);os.nice(5)
resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(720,720))
def timeout(*_):raise TimeoutError('BOUNDED_OWNER_CRE_TIMEOUT')
signal.signal(signal.SIGALRM,timeout);signal.alarm(min(1200,max(1,int(s['expiry_epoch']-time.time()))))
result=M.process(S,case['proposal_id'],CREStore(),cre_policy(),binding_ref=ref,tests_ref='owner-scoped-prefix-binding:'+digest(s))
signal.alarm(0)
assert fence(), 'NEWER_OPERATOR_INTENT_OR_LIVENESS_NO_DEPLOYMENT_ALLOWED'
after={mid:L.snapshot(mid) for mid in before};expected=copy.deepcopy(before);expected[s['mission_id']]['corrections']+=1
assert after==expected,'UNEXPECTED_MISSION_ACCOUNTING_CHANGE'
assert sha256_file(Path(j['case']))==s['case_sha256'] and M.submission(case,require_receipt=True)==(sub,receipt)
assert git(R,'rev-parse','HEAD')==s['runtime_revision'] and not git(R,'status','--porcelain')
immutable_json(O/'all-missions-after.json',after)
out={'status':'PREFIX_ONLY_CORRECTION_INDEPENDENTLY_EVALUATED','scope_sha256':digest(s),'binding_id':ref['binding_id'],'candidate':sub['candidate'],'proposal':result,'qualified_kernel_revision':s['qualified_kernel_revision'],'external_administrative_bootstrap':True,'engineering_source_and_proof_unchanged':True,'raw_case_manifest_receipt_unchanged':True,'mission_change':'ONE_EXISTING_CORRECTION_ONLY','new_engineering_attempts':0,'new_model_requests':0,'runtime_source_deployed':False,'at':utc_now()}
immutable_json(O/'evaluation-result.json',out);print(json.dumps(out),flush=True)
