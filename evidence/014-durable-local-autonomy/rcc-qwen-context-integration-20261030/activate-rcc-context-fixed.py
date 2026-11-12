"""Activate the exact qualified Qwen repair; keep provider, mission counters and deadline unchanged."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,time,xml.etree.ElementTree as ET
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';N=P/'deployment/qualification-integrated-qwen-e21aa74-v1';Q=N/'repo';O=P/'deployment/aspice-rcc-context-fixed-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
os.environ['FORGE_REPO_ROOT']=str(Q);sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.afo import operations,authz,policy
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.common import utc_now
from forge_factory.lrtx import stack
s=json.loads((O/'scope.json').read_text());assert digest(s)=='df87551ec7ad82c1b0e7bcabad40da9162157d2c68a6bc98db99eff71b7a7065'
assert time.time()<s['deadline_epoch'] and json.loads((O/'owner-approval.json').read_text())['scope_sha256']==digest(s)
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
assert git(R,'rev-parse','HEAD')==s['previous_production_revision'] and not git(R,'status','--porcelain')
assert git(Q,'rev-parse','HEAD')==s['source_revision'] and not git(Q,'status','--porcelain')
proof=json.loads((N/'qualification-complete.json').read_text());assert proof['source_revision']==s['source_revision'] and proof['pytest_exit_code']==0 and proof['source_clean_before'] and proof['source_clean_after']
suite=next(ET.parse(N/'scratch/pytest.xml').getroot().iter('testsuite'));assert suite.get('tests')=='125' and suite.get('errors')=='1' and suite.get('failures')==suite.get('skipped')=='0'
from forge_factory.common import sha256_file
assert proof['initial_cohort']['xml_sha256']==sha256_file(N/'scratch/pytest.xml') and proof['initial_cohort']['provenance_sha256']==sha256_file(N/'provenance.json')
second=N/'private-input-fixture-recheck-v4/scratch/pytest.xml';recheck=next(ET.parse(second).getroot().iter('testsuite'))
assert recheck.get('tests')=='1' and all(recheck.get(k)=='0' for k in ('errors','failures','skipped')) and proof['affected_test_recheck']['xml_sha256']==sha256_file(second)
assert proof['unique_tests_passed']==125 and proof['initial_error_retained'] and proof['unchanged_test_source']
local=json.loads((O/'local-qualification.json').read_text());assert local['source_revision']==s['source_revision'] and local['tests']>=100 and local['failures']==local['errors']==local['skipped']==0
for label in ('primary','roles'):
 g=json.loads((O/(label+'-authorization.json')).read_text());assert authz.signature_valid(g,O/(label+'-authorization-message.bin.sig'),authz.ALLOWED_SIGNERS)
 assert g['policy_sha256']==s['policy_sha256'] and g['expires_utc']==s['deadline_utc']
S=Store();I=operations.Intent();L=MissionLedger(S);settings=stack.settings(s['profile']);provider=stack.serving_instance(settings)
before=json.loads((O/'all-missions-before.json').read_text())
def quiet():
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
 for mid,record in before.items():assert L.snapshot(mid)==record
quiet();assert I.read()['mode']=='RUNNING' and I.read()['epoch']==56
operations.synchronize(S,'pause',str(os.getuid()),'Standing delegated approval: independently eligible Qwen inspector-context repair, exact integrated e21aa74 qualification; same mission/caps/deadline',expected_epoch=56,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
with I.lock():
 assert I.read()['mode']=='PAUSED' and I.read()['epoch']==57;quiet()
 for unit in ('forge-qwen-mission-recorder.service','forge-afo-watchdog-014-omniverse2.timer','forge-afo-watchdog-014-omniverse2.service',operations.UNIT):subprocess.run(['systemctl','--user','stop',unit],check=True,timeout=45)
 immutable_json(O/'database-backup.json',S.backup(O/'conductor-before.sqlite3'))
 subprocess.run(['git','-C',str(R),'fetch',str(Q),'HEAD'],capture_output=True,check=True)
 subprocess.run(['git','-C',str(R),'merge','--ff-only',s['source_revision']],capture_output=True,check=True)
 assert git(R,'rev-parse','HEAD')==s['source_revision'] and not git(R,'status','--porcelain')
 for label in ('primary','roles'):
  g=json.loads((O/(label+'-authorization.json')).read_text());immutable_json(authz.AUTH_DIR/(g['authorization_id']+'.json'),g);immutable_bytes(authz.AUTH_DIR/g['signature_ref'],(O/(label+'-authorization-message.bin.sig')).read_bytes())
 target=Path(os.environ['FORGE_AFO_POLICY']);immutable_bytes(O/'policy-before.yaml',target.read_bytes());assert digest(__import__('yaml').safe_load(target.read_text()))==s['policy_before_sha256']
 fd,name=tempfile.mkstemp(prefix='.verified-qwen-',dir=target.parent)
 with os.fdopen(fd,'wb') as f:f.write((O/'proposed-policy.yaml').read_bytes());f.flush();os.fsync(f.fileno())
 os.chmod(name,0o600);os.replace(name,target)
 fd=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 eff=policy.load(log=False);assert eff.mode=='PILOT' and eff.sha256==s['policy_sha256'],eff.issues
 assert stack.serving_instance(settings)==provider;quiet()
resumed=operations.synchronize(S,'resume',str(os.getuid()),'Exact qualified Qwen repair active; same08:11:56UTC mission and finite limits; LL intake follows, HAL waits for verified LL',expected_epoch=57,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()});assert resumed['epoch']==58
with I.lock():
 assert I.read()['mode']=='RUNNING' and I.read()['epoch']==58;quiet()
 subprocess.run(['systemctl','--user','--no-block','start',operations.UNIT,'forge-afo-watchdog-014-omniverse2.timer'],check=True,timeout=20)
 immutable_json(O/'activation.json',{'status':'EXACT_QUALIFIED_QWEN_REPAIR_ACTIVE_NO_PRODUCT_INTAKE_YET','source_revision':s['source_revision'],'operator_epoch':58,'provider_unchanged':True,'all_mission_histories_preserved':True,'deadline_utc':s['deadline_utc'],'native_unique_tests_passed':proof['unique_tests_passed'],'initial_private_fixture_error_retained':True,'local_tests':local['tests'],'model_requests':0,'at':utc_now()})
print((O/'activation.json').read_text())
