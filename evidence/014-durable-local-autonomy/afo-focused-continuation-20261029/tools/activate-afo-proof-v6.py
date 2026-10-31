"""Fenced exact-source activation; delegated signing and append-only mission window."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,time,xml.etree.ElementTree as ET
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';N=P/'deployment/qualification-focused-maintenance-c1f1378-v2';Q=N/'repo';O=P/'deployment/afo-repair-live-20261029-v6'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.afo import operations,authz,policy,mission_deadline
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import immutable_json,immutable_bytes,digest
from forge_factory.lrtx import stack
from forge_factory.common import utc_now
s=json.loads((O/'scope.json').read_text());assert time.time()<s['deadline_epoch']
assert digest(s)==json.loads((O/'owner-approval.json').read_text())['scope_sha256']
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
assert git(R,'rev-parse','HEAD')==s['previous_production_revision'] and not git(R,'status','--porcelain')
assert git(Q,'rev-parse','HEAD')==s['source_revision'] and not git(Q,'status','--porcelain')
prov=json.loads((N/'provenance.json').read_text());assert prov['source_revision']==s['source_revision'] and prov['source_clean_before'] and prov['source_clean_after'] and prov['pytest_exit_code']==0
suite=next(ET.parse(N/'scratch/pytest.xml').getroot().iter('testsuite'));assert suite.get('tests')=='9' and all(suite.get(k)=='0' for k in ('failures','errors','skipped'))
S=Store();I=operations.Intent();L=MissionLedger(S);settings=stack.settings(s['profile']);provider=stack.serving_instance(settings)
def quiet():
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
for label in ('primary','time','roles'):
 g=json.loads((O/(label+'-authorization.json')).read_text());assert authz.signature_valid(g,O/(label+'-authorization-message.bin.sig'),authz.ALLOWED_SIGNERS)
 assert g['policy_sha256']==s['policy_sha256'] and g['expires_utc']==s['deadline_utc']
quiet();assert I.read()['epoch']==44 and I.read()['mode']=='RUNNING';assert L.snapshot(s['mission_id'])==s['mission_before']
p=operations.synchronize(S,'pause',str(os.getuid()),'Active owner goal: qualified external controller bootstrap, then Qwen authors focused repair; disclosed fresh four-hour window with unchanged non-time history',expected_epoch=44,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()});assert p['epoch']==45
with I.lock():
 assert I.read()['epoch']==45 and I.read()['mode']=='PAUSED';quiet();assert L.snapshot(s['mission_id'])==s['mission_before']
 for u in ('forge-afo-watchdog-014-omniverse2.timer','forge-afo-watchdog-014-omniverse2.service',operations.UNIT):subprocess.run(['systemctl','--user','stop',u],check=True,timeout=45)
 assert operations.observed_unit().get('ActiveState') in ('inactive','failed')
 immutable_json(O/'database-backup.json',S.backup(O/'conductor-before.sqlite3'))
 subprocess.run(['git','-C',str(R),'fetch',str(Q),'HEAD'],check=True,capture_output=True)
 subprocess.run(['git','-C',str(R),'merge','--ff-only',s['source_revision']],check=True,capture_output=True)
 assert git(R,'rev-parse','HEAD')==s['source_revision'] and not git(R,'status','--porcelain')
 for label in ('primary','time'):
  g=json.loads((O/(label+'-authorization.json')).read_text());immutable_json(authz.AUTH_DIR/(g['authorization_id']+'.json'),g);immutable_bytes(authz.AUTH_DIR/g['signature_ref'],(O/(label+'-authorization-message.bin.sig')).read_bytes())
 target=Path(os.environ['FORGE_AFO_POLICY']);immutable_bytes(O/'policy.before',target.read_bytes())
 fd,name=tempfile.mkstemp(prefix='.afo-v6-',dir=target.parent)
 with os.fdopen(fd,'wb') as f:f.write((O/'proposed-policy.yaml').read_bytes());f.flush();os.fsync(f.fileno())
 os.chmod(name,0o600);os.replace(name,target)
 fd=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 eff=policy.load(log=False);assert eff.sha256==s['policy_sha256'] and eff.mode=='PILOT',eff.issues
 immutable_json(O/'deadline-extension-receipt.json',mission_deadline.extend(S,json.loads((O/'deadline-extension.json').read_text()),eff))
 after=L.snapshot(s['mission_id']);before=s['mission_before']
 for key in ('attempts','jobs','requests','tools','corrections','charged_tokens','usage_unknown','unique_executions'):assert after[key]==before[key]
 assert {k:v for k,v in after['limits'].items() if k!='deadline'}=={k:v for k,v in before['limits'].items() if k!='deadline'}
 for mid,snap in json.loads((O/'all-missions-before.json').read_text()).items():
  if mid!=s['mission_id']:assert L.snapshot(mid)==snap
 immutable_json(O/'mission-after-window.json',after)
 assert stack.serving_instance(settings)==provider;quiet()
r=operations.synchronize(S,'resume',str(os.getuid()),'Delegated signed Qwen repair continuation at qualified sourcec1f1378; one finite prospective four-hour scope, no old grant/job/counter reset',expected_epoch=45,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()});assert r['epoch']==46
immutable_json(O/'activation.json',{'status':'SIGNED_SOURCE_AND_WINDOW_ACTIVE_ENROLMENT_PENDING','operator_epoch':46,'source_revision':s['source_revision'],'provider_unchanged':stack.serving_instance(settings)==provider,'model_requests':0,'deadline_changed':True,'previous_window_preserved':True,'at':utc_now()})
print((O/'activation.json').read_text())
