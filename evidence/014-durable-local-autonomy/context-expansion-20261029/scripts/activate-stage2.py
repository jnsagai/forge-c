"""Install exactly approved signed scope, preserve mission, preflight, then resume serial execution."""
from pathlib import Path
import json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';D=P/'deployment'
N=D/'qualification-qm-demo-ctx262-9b4c390';O=D/'idr-m1-qm-demo-ctx262-9b4c390-20261029'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
os.environ.update(FORGE_REPO_ROOT=str(R),TMPDIR=str(N/'tmp'),PYTHONDONTWRITEBYTECODE='1')
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import authz,policy,operations
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.afo.overnight import provision_order
from forge_factory.afo.product_role_trial import preflight
from forge_factory.common import utc_now,sha256_file
from forge_factory.lrtx import stack
scope=json.loads((O/'scope.json').read_text());plan=json.loads((O/'plan.json').read_text())
assert digest(scope)=='71b48d33283655a68d9fc33dd65b750a6e1be1aa9bd81188a232d3e1a6ac5759'
assert time.time()<scope['limits_after']['deadline']
def git(root,*args,check=True):return subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,check=check,timeout=30)
assert git(R,'rev-parse','HEAD').stdout.strip()==scope['source_revision'] and not git(R,'status','--porcelain').stdout.strip()
S=Store();I=operations.Intent();L=MissionLedger(S)
def paused():
 st=I.read();assert st['mode']=='PAUSED' and st['epoch']==31
 assert not Executions(S).pending()
def history():
 with S.tx() as c: mids=[r[0] for r in c.execute('SELECT mission_id FROM afo_missions')]
 return {mid:L.snapshot(mid) for mid in mids}
before=json.loads((O/'history-before.json').read_text())
def preserved():
 h=history()
 for mid,snap in before.items():
  if mid!=scope['mission_id']:assert h[mid]==snap
 current=h[scope['mission_id']]
 for key in ('attempts','jobs','requests','tools','corrections','charged_tokens','usage_unknown','unique_executions','unbounded_historical_usage'):
  assert current[key]==before[scope['mission_id']][key]
 assert {k:v for k,v in current['limits'].items() if k!='deadline'}=={k:v for k,v in scope['limits_after'].items() if k!='deadline'}
 return current
with I.lock():
 paused();assert digest(L.snapshot(scope['mission_id']))==scope['mission_snapshot_sha256']
 settings=stack.settings(scope['profile']);assert settings['profile']['_sha256']==scope['profile_sha256']
 assert os.environ['FORGE_OPERATIONS_PROFILE']==scope['profile']
 for label in ('primary','roles'):
  grant=json.loads((O/(label+'-authorization.json')).read_text())
  immutable_json(authz.AUTH_DIR/(grant['authorization_id']+'.json'),grant)
  immutable_bytes(authz.AUTH_DIR/grant['signature_ref'],(O/(label+'-authorization-message.bin.sig')).read_bytes())
  check=authz.verify(grant,policy_sha256=scope['policy_sha256'],mode='PILOT',action='recover_workorder',
   request={'order_id':scope['request_id'],'driver_class':'LL','model':scope['model']})
  assert check.allow,check
 proposed=json.loads((O/'policy.json').read_text());assert digest(proposed)==scope['policy_sha256']
 assert not policy.schema_errors(proposed) and not policy.floor_violations(proposed)
 target=Path(os.environ['FORGE_AFO_POLICY']);immutable_bytes(O/'policy-before.yaml',target.read_bytes())
 temp=target.with_name(target.name+'.qm-5b-next')
 fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as f:f.write((O/'proposed-policy.yaml').read_bytes());f.flush();os.fsync(f.fileno())
 os.replace(temp,target)
 fd=os.open(target.parent,os.O_RDONLY|os.O_DIRECTORY)
 try:os.fsync(fd)
 finally:os.close(fd)
 eff=policy.load(log=False);assert eff.mode=='PILOT' and eff.sha256==scope['policy_sha256'],eff.issues
 assert L.snapshot(scope['mission_id'])==scope['mission_before']  # Existing signed window; no time change.
 preserved()
 immutable_json(P/'state'/scope['trial_ref']['path'],json.loads((O/'trial.json').read_text()))
 launch=json.loads((O/'launch.json').read_text());env=plan['orders'][0]['envelope']
 immutable_bytes(R/env['input_manifest_ref'],(O/'launch.json').read_bytes())
 assert sha256_file(R/env['input_manifest_ref'])==env['manifest_sha256']
 provision_order(S,plan['orders'][0],eff,scope['limits_after']['deadline'])
 assert S.order(scope['new_order_id'])['state']=='QUEUED' and not S.attempts(scope['new_order_id'])
 captures=N/'role-context-preflight-high-v1'
 result=json.loads((captures/'result.json').read_text());requests=json.loads((captures/'structured-requests.json').read_text())
 for row in result['captures']:
  if row['role']!='swe1-author':
   requests.append({'role':row['role'],'body':json.loads((captures/f"request-{row['index']:03d}.json").read_text())})
 immutable_json(O/'requests.json',requests)
 job=dict(order_id=scope['new_order_id'],model=scope['model'],profile=scope['profile'],model_digest=scope['model_digest'],
  precision='Q8_0',factory_revision={'commit':scope['source_revision'],'dirty':False},product_role_trial=scope['trial_ref'])
 ws=captures/'stack/state/workorders/WO-AFO-774900b297bdde37-a1/workspace'
 report=preflight(ws,job,requests);immutable_json(O/'role-preflight.json',report)
 assert report['status']=='PASS_STATIC_ADMISSION',[(r['role'],r['status'],r.get('reason')) for r in report['rows'] if r['status'] not in ('PASS_STATIC_ADMISSION','NO_INFERENCE_IMPORTED_REQUIREMENTS')]
 immutable_json(O/'preflight-pass.json',{'source_revision':scope['source_revision'],'rows':len(report['rows']),
  'maximum_conservative_reservation':max(r.get('conservative_reservation',0) for r in report['rows']),
  'model_requests':0,'at':utc_now()})
 preserved()
 (P/'fabro/settings.toml').write_text(stack.fabro_config(settings))
 out=Path(plan['progress_repo']);out.mkdir(mode=0o700)
 oldplan=json.loads((D/'idr-m1-qm-demo-15b0fa5-20261029/plan.json').read_text());oldrepo=Path(oldplan['progress_repo'])
 git(out,'init','-b',plan['progress_branch']);git(out,'config','user.name','Forge-C Mission Recorder')
 git(out,'config','user.email','forge-c-mission@localhost')
 git(out,'remote','add','origin',git(oldrepo,'remote','get-url','origin').stdout.strip())
 command=git(oldrepo,'config','--get','core.sshCommand',check=False)
 if command.returncode==0:git(out,'config','core.sshCommand',command.stdout.strip())
 unit=Path.home()/'.config/systemd/user/forge-idr-m1-20261028.service'
 immutable_bytes(O/'recorder-unit-before.txt',unit.read_bytes())
 raw=unit.read_text()
 assert str(D/'idr-m1-qm-demo-15b0fa5-20261029/plan.json') in raw
 unit.write_text(raw.replace(str(D/'idr-m1-qm-demo-15b0fa5-20261029/plan.json'),str(O/'plan.json')).replace(scope['previous_profile'],scope['profile']))
 subprocess.run(['systemctl','--user','daemon-reload'],check=True,timeout=20)
 print(json.dumps({'status':'SIGNED_SCOPE_AND_COMPLETE_ROLE_PREFLIGHT_PASS','source_revision':scope['source_revision'],
  'rows':len(report['rows']),'operator_epoch':31,'model_requests':0}),flush=True)
resumed=operations.synchronize(S,'resume',str(os.getuid()),'Owner-approved exact QM larger-context 9b4c390 Qwen M1 continuation to 18:05 UTC',
 expected_epoch=31,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
assert resumed['epoch']==32
health=stack.start(settings,recovery=True)
for _ in range(6):
 if all(health['health'].get(k) is True for k in ('fabro','gateway','ollama','llama_server')):break
 time.sleep(5);health=stack.start(settings,recovery=True)
assert all(health['health'].get(k) is True for k in ('fabro','gateway','ollama','llama_server')),health['health']
with I.lock():
 assert I.read()['mode']=='RUNNING' and I.read()['epoch']==32
 assert not Executions(S).pending()
 preserved()
 immutable_json(O/'provider-ready.json',{'health':health['health'],'profile_sha256':health['profile_sha256'],
  'serving_instance':health['serving_instance'],'at':utc_now(),'generation_requests':0})
 subprocess.run(['systemctl','--user','--no-block','start','forge-conductor-local-omniverse2.service',
  'forge-afo-watchdog-014-omniverse2.timer','forge-idr-m1-20261028.service'],check=True,timeout=20)
 record={'status':'QWEN_M1_CONTINUATION_ADMISSION_STARTED','source_revision':scope['source_revision'],
  'operator_epoch':32,'scope_sha256':digest(scope),'order_id':scope['new_order_id'],'mission_id':scope['mission_id'],
  'deadline_utc':scope['deadline_utc'],'history_preserved':True,'inference_concurrency':1,
  'health':health['health'],'model_capability':'NOT_ESTABLISHED','product_acceptance':'NOT_ESTABLISHED',
  'progress_branch':plan['progress_branch'],'at':utc_now()}
 immutable_json(O/'activation.json',record);print(json.dumps(record),flush=True)
