"""Activate exact signed trial policy; preserve loaded inference and all accounting."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/afo-repair-live-20261029-v5'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations,authz,policy
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import immutable_json,immutable_bytes,digest
from forge_factory.lrtx import stack
from forge_factory.common import utc_now
s=json.loads((O/'scope.json').read_text());assert time.time()<s['deadline_epoch']
assert digest(s)==json.loads((O/'owner-approval.json').read_text())['scope_sha256']
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==s['source_revision']
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
S=Store();I=operations.Intent();L=MissionLedger(S);settings=stack.settings(s['profile']);provider=stack.serving_instance(settings)
def quiet():
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
 assert L.snapshot(s['mission_id'])==s['mission_before']
for label in ('primary','roles'):
 g=json.loads((O/(label+'-authorization.json')).read_text());assert authz.signature_valid(g,O/(label+'-authorization-message.bin.sig'),authz.ALLOWED_SIGNERS)
 assert g['policy_sha256']==s['policy_sha256'] and g['expires_utc']==s['deadline_utc']
quiet();assert I.read()['epoch']==42 and I.read()['mode']=='RUNNING'
p=operations.synchronize(S,'pause',str(os.getuid()),'Owner goal: prove AFO with exact Qwen trial and independent verifier; same finite mission deadline/history',expected_epoch=42,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()});assert p['epoch']==43
with I.lock():
 assert I.read()['epoch']==43 and I.read()['mode']=='PAUSED';quiet()
 for u in ('forge-afo-watchdog-014-omniverse2.timer','forge-afo-watchdog-014-omniverse2.service',operations.UNIT):
  subprocess.run(['systemctl','--user','stop',u],check=True,timeout=45)
 assert operations.observed_unit().get('ActiveState') in ('inactive','failed')
 immutable_json(O/'database-backup.json',S.backup(O/'conductor-before.sqlite3'))
 g=json.loads((O/'primary-authorization.json').read_text());immutable_json(authz.AUTH_DIR/(g['authorization_id']+'.json'),g);immutable_bytes(authz.AUTH_DIR/g['signature_ref'],(O/'primary-authorization-message.bin.sig').read_bytes())
 target=Path(os.environ['FORGE_AFO_POLICY']);immutable_bytes(O/'policy.before',target.read_bytes())
 fd,name=tempfile.mkstemp(prefix='.proof-v3-',dir=target.parent)
 with os.fdopen(fd,'wb') as f:f.write((O/'proposed-policy.yaml').read_bytes());f.flush();os.fsync(f.fileno())
 os.chmod(name,0o600);os.replace(name,target)
 fd=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 eff=policy.load(log=False);assert eff.sha256==s['policy_sha256'] and eff.mode=='PILOT',eff.issues
 assert stack.serving_instance(settings)==provider;quiet()
r=operations.synchronize(S,'resume',str(os.getuid()),'Signed source-bound Qwen maintenance trial prepared; preserve provider, histories and22:25:58UTC expiry',expected_epoch=43,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()});assert r['epoch']==44
immutable_json(O/'activation.json',{'status':'SIGNED_TRIAL_POLICY_ACTIVE_ENROLMENT_PENDING','operator_epoch':44,'source_revision':s['source_revision'],'provider_unchanged':stack.serving_instance(settings)==provider,'model_requests':0,'deadline_changed':False,'at':utc_now()})
print((O/'activation.json').read_text())
