from pathlib import Path
import os,sys,json,subprocess,shlex,time
import yaml
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';D=P/'deployment';O=D/'aspice-window-20261028'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#'):
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import authz,policy,operations
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import immutable_json,digest
from forge_factory.common import canonical_json,sha256_bytes,utc_now
from forge_factory.lrtx import stack
scope=json.loads((O/'scope.json').read_text());plan=json.loads((O/'plan.json').read_text())
assert digest(scope)=='cef1df07c885ae4b35d823bb04fe803a7fa3b38d7e04010728408ff23ff3f26b'
assert time.time()<scope['deadline_epoch']
candidate=scope['source_revision'];assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==candidate
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'],text=True).strip()
S=Store();L=MissionLedger(S);I=operations.Intent()
proposed=yaml.safe_load((O/'proposed-policy.yaml').read_text())
assert sha256_bytes(canonical_json(proposed))==scope['policy_sha256']
assert not policy.schema_errors(proposed) and not policy.floor_violations(proposed)
request={'order_id':scope['envelope']['request_id'],'driver_class':'LL','model':scope['envelope']['model_profile']}
grants={}
for label,aid in [('primary','AUTH-014-Q38-ASPICE-CONTINUATION-20261028-V1'),('roles','AUTH-014-Q38-ASPICE-ROLES-20261028-V1')]:
 g=json.loads((authz.AUTH_DIR/(aid+'.json')).read_text())
 assert g['approval_evidence_ref']=='owner-aspice-scope:'+digest(scope)
 assert g['expires_utc']==scope['deadline_utc']
 sig=(O/(label+'-authorization-message.bin.sig')).read_bytes()
 dest=authz.AUTH_DIR/(aid+'.sig')
 fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o400)
 with os.fdopen(fd,'wb') as f:f.write(sig);f.flush();os.fsync(f.fileno())
 decision=authz.verify(g,policy_sha256=scope['policy_sha256'],mode='PILOT',action='recover_workorder',request=request)
 assert decision.allow,decision
 grants[label]=g
assert grants['primary']['signed_runbook_ref']=='factory-revision:'+candidate
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
oldplan=json.loads((D/'e2e-window-20261028-v3/plan.json').read_text());oldrepo=Path(oldplan['progress_repo'])
out=Path(plan['progress_repo']);out.mkdir(mode=0o700)
git(out,'init','-b',plan['progress_branch']);git(out,'config','user.name','Forge-C Mission Recorder')
git(out,'config','user.email','forge-c-mission@localhost');git(out,'remote','add','origin',git(oldrepo,'remote','get-url','origin'))
ssh=subprocess.run(['git','-C',str(oldrepo),'config','--get','core.sshCommand'],capture_output=True,text=True)
if ssh.returncode==0:git(out,'config','core.sshCommand',ssh.stdout.strip())
with I.lock():
 state=I.read();assert state['mode']=='PAUSED' and state['epoch']==15
 assert not Executions(S).pending()
 before=L.snapshot(scope['mission_id']);assert before==scope['mission_before']
 with S.tx() as c:
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
 path=Path(os.environ['FORGE_AFO_POLICY']);tmp=path.with_name(path.name+'.aspice-next')
 fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as f:f.write((O/'proposed-policy.yaml').read_bytes());f.flush();os.fsync(f.fileno())
 os.replace(tmp,path);parent=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(parent)
 finally:os.close(parent)
 eff=policy.load(log=False);assert eff.sha256==scope['policy_sha256']
 # Link BEFORE visibility. This is an authenticated operator continuation of the
 # existing immutable mission, not register() with a new grant or larger limits.
 for action in ['submit_workorder','launch_workorder','recover_workorder']:
  check=authz.verify(grants['primary'],policy_sha256=eff.sha256,mode='PILOT',action=action,request=request);assert check.allow
 L.link(scope['mission_id'],scope['order_id'],continuation_of=scope['parent_order_id'])
 from forge_factory.afo.cli import approve
 oid,created=S.submit(scope['envelope'],repo=R,max_queued=int(eff.get('queue.max_queued_orders')),approve=lambda e:approve(e,eff))
 assert created and oid==scope['order_id'];assert L.snapshot(scope['mission_id'])==before
 unit=Path.home()/'.config/systemd/user/forge-qwen-golive-20261028.service'
 raw=unit.read_bytes();(O/'recorder-unit-before').write_bytes(raw)
 oldpath=Path(shlex.split(next(x for x in raw.decode().splitlines() if x.startswith('ExecStart=')).split('=',1)[1])[-1])
 changed=raw.replace(str(oldpath).encode(),str(O/'plan.json').encode());assert changed!=raw
 tmp=unit.with_name(unit.name+'.aspice-next')
 fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as f:f.write(changed);f.flush();os.fsync(f.fileno())
 os.replace(tmp,unit);subprocess.run(['systemctl','--user','daemon-reload'],check=True,timeout=20)
state=operations.synchronize(S,'resume',str(os.getuid()),'Run owner ASPICE-only CRC continuation within unchanged cumulative mission allowance and deadline',
 expected_epoch=15,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
assert state['epoch']==16
settings=stack.settings(scope['profile'])
assert settings['profile']['_sha256']==scope['profile_sha256']
health=stack.start(settings,recovery=True);assert all(health['health'].get(k) is True for k in ['fabro','gateway','ollama'])
with I.lock():
 state=I.read();assert state['epoch']==16 and state['mode']=='RUNNING'
 immutable_json(O/'api-bridge.json',stack.expose_api(settings,32491))
# Keep admission stopped until the real namespace/model/MCP/graph preflight completes.
result={'status':'ASPICE_SIGNED_SCOPE_AND_PROVIDER_ACTIVATED_ADMISSION_WAITING_PREFLIGHT',
 'source_revision':candidate,'scope_sha256':digest(scope),'operator_epoch':16,'profile_sha256':scope['profile_sha256'],
 'order_id':oid,'mission_id':scope['mission_id'],'deadline_utc':scope['deadline_utc'],
 'prior_mission_tokens_preserved':before['charged_tokens'],'mission_limits_unchanged':True,'health':health['health'],
 'inference_requests_created_by_activation':0,'role_qualification':'NOT_ESTABLISHED','safety_approval':None,
 'assessed_aspice_compliance':None,'original_policy_restore_at_expiry_required':True}
immutable_json(O/'activation.json',result);print(json.dumps(result))
