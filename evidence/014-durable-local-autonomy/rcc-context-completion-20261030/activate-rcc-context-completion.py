from pathlib import Path
import json,os,subprocess,sys,tempfile,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/rcc-context-completion-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations,authz,policy
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.lrtx import stack
from forge_factory.common import utc_now
s=json.loads((O/'scope.json').read_text());assert digest(s)=='858bd287930424bbbb9b9cc2879641a8aa4221d4135377dd9be30d15c39228bf'
assert time.time()<s['deadline_epoch']
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==s['previous_production_revision']
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
S=Store();I=operations.Intent();L=MissionLedger(S);settings=stack.settings(s['profile']);provider=stack.serving_instance(settings)
before=json.loads((O/'all-missions-before.json').read_text())
def quiet():
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
 for mid,record in before.items():assert L.snapshot(mid)==record
for label in ('primary','roles'):
 g=json.loads((O/(label+'-authorization.json')).read_text())
 assert authz.signature_valid(g,O/(label+'-authorization-message.bin.sig'),authz.ALLOWED_SIGNERS)
 assert g['policy_sha256']==s['policy_sha256'] and g['expires_utc']==s['deadline_utc']
N=P/'deployment/qualification-source-edits-ab46545-v1';Q=N/'repo'
proof=json.loads((N/'provenance.json').read_text())
assert proof['source_revision']==s['source_revision'] and proof['pytest_exit_code']==0 and proof['source_clean_before'] and proof['source_clean_after']
import xml.etree.ElementTree as ET
suite=next(ET.parse(N/'scratch/pytest.xml').getroot().iter('testsuite'))
assert int(suite.get('tests'))>=60 and all(suite.get(k)=='0' for k in ('errors','failures','skipped'))
assert time.time()<s['enrolment_latest_epoch']
quiet();assert I.read()['mode']=='RUNNING' and I.read()['epoch']==52
operations.synchronize(S,'pause',str(os.getuid()),'Same-mission current RCC inspector-context repair; activate qualified bounded source edit MCP; no model/deadline/counter reset',expected_epoch=52,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
with I.lock():
 assert I.read()['mode']=='PAUSED' and I.read()['epoch']==53;quiet()
 for unit in ('forge-afo-watchdog-014-omniverse2.timer','forge-afo-watchdog-014-omniverse2.service',operations.UNIT):
  subprocess.run(['systemctl','--user','stop',unit],check=True,timeout=45)
 immutable_json(O/'database-backup.json',S.backup(O/'conductor-before.sqlite3'))
 subprocess.run(['git','-C',str(R),'fetch',str(Q),'HEAD'],capture_output=True,check=True)
 subprocess.run(['git','-C',str(R),'merge','--ff-only',s['source_revision']],capture_output=True,check=True)
 assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==s['source_revision']
 assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
 g=json.loads((O/'primary-authorization.json').read_text())
 immutable_json(authz.AUTH_DIR/(g['authorization_id']+'.json'),g)
 immutable_bytes(authz.AUTH_DIR/g['signature_ref'],(O/'primary-authorization-message.bin.sig').read_bytes())
 target=Path(os.environ['FORGE_AFO_POLICY']);immutable_bytes(O/'policy-before.yaml',target.read_bytes())
 assert digest(__import__('yaml').safe_load(target.read_text()))==s['policy_before_sha256']
 fd,name=tempfile.mkstemp(prefix='.rcc-context-',dir=target.parent)
 with os.fdopen(fd,'wb') as f:f.write((O/'proposed-policy.yaml').read_bytes());f.flush();os.fsync(f.fileno())
 os.chmod(name,0o600);os.replace(name,target)
 fd=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 eff=policy.load(log=False);assert eff.mode=='PILOT' and eff.sha256==s['policy_sha256'],eff.issues
 assert stack.serving_instance(settings)==provider;quiet()
operations.synchronize(S,'resume',str(os.getuid()),'Exact signed Qwen current-defect maintenance scope; original08:11:56UTC and budgets preserved; one-shot enrollment pending',expected_epoch=53,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
immutable_json(O/'activation.json',{'status':'POLICY_ACTIVE_ONE_SHOT_ENROLMENT_PENDING','operator_epoch':54,
 'source_revision':s['source_revision'],'provider_unchanged':True,'mission_history_preserved':True,
 'deadline_unchanged':s['deadline_utc'],'model_requests':0,'at':utc_now()})
print((O/'activation.json').read_text())
