from pathlib import Path
import json,os,subprocess,sys,time,xml.etree.ElementTree as ET
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';N=P/'deployment/qualification-commit-reconciliation-53e1234-v1';Q=N/'repo';O=P/'deployment/rcc-canonical-commit-reconciliation-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
os.environ['FORGE_REPO_ROOT']=str(Q);sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.afo import operations,authz,policy,maintainer as M
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.completion_receipt import Context
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.common import sha256_file,utc_now
s=json.loads((O/'scope.json').read_text());assert digest(s)=='a90483bdac34e445e72544fd6d92752af0c89e5114a351ae422ba1b97932870d'
assert json.loads((O/'owner-approval.json').read_text())['scope_sha256']==digest(s)
S=Store();I=operations.Intent();L=MissionLedger(S)
case=json.loads(Path(s['case_path']).read_text());d=Path(s['case_path']).parent
if (O/'reconciliation-receipt.json').exists():
 sub,receipt=M.submission(case,require_receipt=True);assert sub['candidate']==s['candidate_commit']
 print(json.dumps({'status':'EXISTING_RECOVERY_RECEIPT_NO_NEW_EFFECT','candidate':sub['candidate']}));raise SystemExit(0)
assert time.time()<s['expiry_epoch']
proof=json.loads((N/'provenance.json').read_text());assert proof['source_revision']==s['qualified_reconciler_revision'] and proof['pytest_exit_code']==0 and proof['source_clean_before'] and proof['source_clean_after']
suite=next(ET.parse(N/'scratch/pytest.xml').getroot().iter('testsuite'));assert suite.get('tests')=='83' and all(suite.get(k)=='0' for k in ('errors','failures','skipped'))
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
assert git(Q,'rev-parse','HEAD')==s['qualified_reconciler_revision'] and not git(Q,'status','--porcelain')
assert git(R,'rev-parse','HEAD')==s['runtime_revision'] and not git(R,'status','--porcelain')
g=json.loads((O/'authorization.json').read_text());assert authz.signature_valid(g,O/'authorization-message.bin.sig',authz.ALLOWED_SIGNERS)
assert g['signed_runbook_ref']=='maintenance-commit-reconciliation-014:'+digest(s)
args=json.loads((O/'model-request.json').read_text());assert digest(args)==s['original_model_request_sha256']
request={'case_sha256':s['case_sha256'],'summary':args['summary'],'reproducer':args['reproducer'],'signature':args['symptom_signature']};assert digest(request)==s['request_sha256']
before=json.loads((O/'all-missions-before.json').read_text())
with I.lock():
 assert I.read()['mode']=='PAUSED' and I.read()['epoch']==55
 assert operations.observed_unit()['ActiveState'] in ('inactive','failed')
 assert not Executions(S).pending()
 with S.tx() as c:
  j=json.loads(c.execute('SELECT record FROM afo_local_agent_jobs WHERE job_id=?',(s['job_id'],)).fetchone()[0]);assert j['state']=='RUNNING'
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
 Context.from_job(S,s['job_id'])
 for mid,record in before.items():assert L.snapshot(mid)==record
 assert sha256_file(Path(s['case_path']))==s['case_sha256']
 assert (d/'submission-intent.json').read_bytes()==(O/'original-submission-intent.json').read_bytes()
 assert git(Path(case['src']),'rev-parse','HEAD')==s['candidate_commit'] and not git(Path(case['src']),'status','--porcelain')
 immutable_json(O/'database-backup.json',S.backup(O/'conductor-before.sqlite3'))
 immutable_json(authz.AUTH_DIR/(g['authorization_id']+'.json'),g)
 immutable_bytes(authz.AUTH_DIR/g['signature_ref'],(O/'authorization-message.bin.sig').read_bytes())
 eff=policy.load(log=False);assert eff.sha256==s['policy_sha256']
 allowed=authz.verify(g,policy_sha256=eff.sha256,mode=eff.mode,action='recover_workorder',request={'order_id':s['request_id'],'driver_class':'LL','model':j['model']})
 assert allowed.allow,allowed
 sub=M.submit(case,args['summary'],args['reproducer'],args['symptom_signature'])
 assert sub['candidate']==s['candidate_commit'] and not sub['veto']
 assert M.submission(case,require_receipt=True)[0]==sub
 assert git(Path(case['src']),'rev-parse','HEAD')==s['candidate_commit']
 assert (d/'submission-intent.json').read_bytes()==(O/'original-submission-intent.json').read_bytes()
 assert sha256_file(Path(s['case_path']))==s['case_sha256']
 assert git(R,'rev-parse','HEAD')==s['runtime_revision'] and not git(R,'status','--porcelain')
 for mid,record in before.items():assert L.snapshot(mid)==record
 result={'status':'EXISTING_MODEL_COMMIT_RECEIPT_RECONCILED','scope_sha256':digest(s),'candidate_commit':sub['candidate'],'submission_receipt_sha256':sha256_file(d/'submission-receipt.json'),'original_intent_byte_identical':True,'candidate_commit_unchanged':True,'case_unchanged':True,'mission_histories_unchanged':True,'new_commits':0,'new_model_requests':0,'runtime_source_deployed':False,'qualified_administrative_kernel':s['qualified_reconciler_revision'],'engineering_code_authorship':'QWEN','external_administrative_bootstrap':True,'independent_quality':'NOT_YET_REVIEWED','at':utc_now()}
 immutable_json(O/'reconciliation-receipt.json',result)
 print(json.dumps(result))
