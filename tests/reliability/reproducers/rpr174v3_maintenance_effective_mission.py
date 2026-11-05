"""Independent real TEST-signed time amendment to the existing maintenance guard.
Generic job/origin authorization and source-identity metadata are fixture leaves.
Actual candidate import is independently pinned by the CRE runner. Real control
crypto/profile/intent/ledger/amendment checks and the target guard execute normally.
No model, GPU, live factory or owner key is used. Private NSS metadata preserves the
verifier UID and allows OpenSSH TEST signing without changing host accounts.
"""
import copy,datetime,hashlib,json,os,subprocess,tempfile,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from forge_factory import workorder
from forge_factory.afo import authz,line_recovery_control as CONTROL,line_maintenance_coordinator as M,mission_deadline as DEADLINE
from forge_factory.afo.queue import Store
from forge_factory.afo.operations import Intent
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.durable import Refused,digest,immutable_json
from forge_factory.lrtx.profile import load


SIG='maintenance review rejects an owner-signed effective mission deadline amendment'

def scenario():
 with tempfile.TemporaryDirectory(prefix='private-M7-renewal-') as temporary:
  root=Path(temporary);state=root/'state';os.environ['FORGE_STATE_DIR']=str(state);os.environ.pop('FORGE_DURABLE_AUTONOMY',None)
  store=Store(state/'supervisor/line-queue.sqlite3');ledger=MissionLedger(store);private=root/'private-intent';private.mkdir(mode=0o700);intent=Intent(private/'intent.json');record=intent.set('RUNNING',actor='TEST_FIXTURE_ONLY',reason='Private maintainer counterexample',initialize=True)
  os.environ['FORGE_OPERATIONS_INTENT']=str(intent.path)
  repo=root/'envelope-input';(repo/'afo-manifests').mkdir(parents=True);manifest=repo/'afo-manifests/m.json';manifest.write_text('{"example":"private-counterexample"}')
  env={'schema_version':'1.0','request_id':'WO-F014-SWE6-AFOQUAL-20261104-L99','tenant_scope':'line-local','manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'input_manifest_ref':'afo-manifests/m.json','approved_by':'TEST_FIXTURE_ONLY','authorization_ref':'TEST-CONTROL','driver_class':'STM32N6_CRC_HAL','target':'private-fixture','safety_scope':'TEST_ONLY','model_profile':'local-rtx-v2-omniverse2-ornith-think-afo-finite-review-20261104','submitted_utc':'2026-11-05T00:00:00Z','priority':'NORMAL'}
  oid,_=store.submit(env,repo=repo,max_queued=10)
  limits=dict(max_attempts=4,max_jobs=4,max_requests=32,max_tokens=8388608,max_tools=256,max_corrections=4,deadline=time.time()+600)
  ledger.register('original-mission','original-lineage',limits,'TEST-CONTROL',authorize=lambda *_:True);ledger.link('original-mission',oid);ledger.execution('original-mission','retained-old-product','PRODUCT',reserved_tokens=1048576)
  before=ledger.snapshot('original-mission')
  with store.tx() as c:original_base=c.execute('SELECT record FROM afo_missions').fetchone()[0]
  profile=load(env['model_profile']);revision={'commit':'a'*40,'dirty':False,'basis':'ISOLATED_SOURCE_IDENTITY_FIXTURE'}
  eff=SimpleNamespace(mode='PILOT',sha256='c'*64,get=lambda key,default=None:{'authorization_ref':'TEST-CONTROL','maintenance.enable_factory_maintainer':True,'budgets.max_order_wall_seconds':1800}.get(key,default))
  auth=root/'TEST_AUTHORITY_ONLY';auth.mkdir(mode=0o700);key=root/'GENERATED_TEST_KEY_NOT_OWNER';subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(key)],check=True)
  signers=root/'TEST_SIGNERS';signers.write_text('FixtureOwner namespaces="'+authz.NAMESPACE+'" '+key.with_suffix('.pub').read_text())
  def grant(aid,signed):
   g=dict(schema_version='1.0',authorization_id=aid,approver='FixtureOwner',approval_evidence_ref='PRIVATE_TEST_ONLY_NOT_OWNER_AUTHORITY',issued_utc=datetime.datetime.fromtimestamp(time.time()-5,datetime.UTC).isoformat(),expires_utc=datetime.datetime.fromtimestamp(time.time()+1800,datetime.UTC).isoformat(),policy_sha256=eff.sha256,mode='PILOT',allowed_actions=['recover_workorder'],scope={'order_ids':[env['request_id']],'driver_classes':[env['driver_class']],'models':[env['model_profile']]},signature_ref=aid+'.sig',signed_runbook_ref=signed)
   p=auth/(aid+'.json');p.write_text(json.dumps(g));msg=root/'TEST_MSG';msg.write_bytes(authz.message(g));sig=msg.with_suffix('.sig')
   if sig.exists():sig.unlink()
   subprocess.run(['ssh-keygen','-Y','sign','-f',str(key),'-n',authz.NAMESPACE,str(msg)],check=True,capture_output=True);(auth/g['signature_ref']).write_bytes(sig.read_bytes());return g
  def make_control(limits,tag):
   ctl={'schema':CONTROL.SCHEMA,'source_revision':revision['commit'],'policy_sha256':eff.sha256,'authorization_ref':'TEST-CONTROL','profile':profile['id'],'profile_sha256':profile['_sha256'],'operations_intent':str(intent.path),'mission':{'mission_id':'original-mission','lineage':'original-lineage','limits':copy.deepcopy(limits)},'role_capabilities':{},'product_role_trial':None}
   p=root/(tag+'-control.json');immutable_json(p,ctl);return ctl,{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
  case=root/'case.json';case.write_text('{"private":"immutable-case"}');jobbase={'state':'SUCCEEDED','role':M.ROLE,'durable_native':'maintenance-1','line_origin':{'campaign_path':'private-authorized-origin-fixture'},'model':env['model_profile'],'policy_sha256':eff.sha256,'deadline_epoch':time.time()+1500,'order_id':oid,'mission_id':'original-mission','profile':profile['id'],'profile_sha256':profile['_sha256'],'factory_revision':revision,'operations_epoch':record['epoch'],'native_context':{'FORGE_OPERATIONS_INTENT':str(intent.path),'FORGE_AFO_QUEUE_SCOPE':'line-local'},'case':str(case),'case_sha256':hashlib.sha256(case.read_bytes()).hexdigest()}
  def save_job(n,ref):
   j={**copy.deepcopy(jobbase),'job_id':'afo-agent-'+str(n)*24,'attempt_id':'private-attempt-'+str(n),'line_role_authority_ref':ref}
   with store.tx() as c:c.execute('INSERT INTO afo_local_agent_jobs VALUES (?,?,?,?,?,?)',(j['job_id'],oid,j['attempt_id'],M.ROLE,j['state'],json.dumps(j)))
   return j
  with patch.object(workorder,'factory_revision',return_value=revision),patch.object(authz,'AUTH_DIR',auth),patch.object(authz,'ALLOWED_SIGNERS',signers),patch.object(M.L,'authorized_job',return_value=True),patch.object(M.line_recovery,'valid_job',return_value=True):
   first,ref=make_control(limits,'initial');grant('TEST-CONTROL','line-recovery-014:'+digest(first));j1=save_job(1,ref)
   assert CONTROL.configuration(ref,eff,request=env and M.L.request_for(store.order(oid)))==first
   assert CONTROL.require_job_binding(j1,first,store=store)
   M._authorized(store,j1,eff)
   doc={'schema':DEADLINE.SCHEMA,'mission_id':'original-mission','snapshot_sha256':digest(ledger.snapshot('original-mission')),'deadline_epoch':time.time()+1200,'authorization_ref':'TEST-TIME-EXTENSION','request':M.L.request_for(store.order(oid)),'reason':'Normal TEST-signed time-only amendment on existing private mission'}
   grant('TEST-TIME-EXTENSION','mission-deadline-extension-014:'+digest(doc));DEADLINE.extend(store,doc,eff)
   amended=ledger.snapshot('original-mission');current,ref2=make_control(amended['limits'],'renewed');grant('TEST-CONTROL','line-recovery-014:'+digest(current));j2=save_job(2,ref2)
   assert CONTROL.configuration(ref2,eff,request=M.L.request_for(store.order(oid)))==current
   assert CONTROL.require_job_binding(j2,current,store=store)
   try:M._authorized(store,j2,eff)
   except Refused as exc:
    assert exc.code=='LINE_MAINTENANCE_CONTROL_MISSION_OR_INTENT_CHANGED';code=exc.code
   else:code='ACCEPTED'
   with store.tx() as c:assert c.execute('SELECT record FROM afo_missions').fetchone()[0]==original_base
   after=ledger.snapshot('original-mission')
   assert all(after[k]==before[k] for k in ('attempts','jobs','requests','tools','corrections','charged_tokens','usage_unknown','unique_executions'))
   if code != 'ACCEPTED':
    print('SYMPTOM_PRESENT:'+SIG)
    return 1
   for n,fault in enumerate(('stale','cap','lineage','authority'),3):
    bad=copy.deepcopy(current)
    if fault=='stale':bad['mission']['limits']=copy.deepcopy(limits)
    elif fault=='cap':bad['mission']['limits']['max_attempts']+=1
    elif fault=='lineage':bad['mission']['lineage']='foreign-lineage'
    else:bad['authorization_ref']='FOREIGN-CONTROL'
    path=root/('negative-'+fault+'.json');immutable_json(path,bad)
    grant(bad['authorization_ref'],'line-recovery-014:'+digest(bad))
    refbad={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    negative=save_job(n,refbad)
    negative_eff=SimpleNamespace(mode=eff.mode,sha256=eff.sha256,get=lambda key,default=None: bad['authorization_ref'] if key=='authorization_ref' else eff.get(key,default))
    assert CONTROL.configuration(refbad,negative_eff,request=M.L.request_for(store.order(oid)))==bad
    try:M._authorized(store,negative,negative_eff)
    except Refused as exc:assert exc.code=='LINE_MAINTENANCE_CONTROL_MISSION_OR_INTENT_CHANGED',(fault,exc.code)
    else:raise AssertionError('NEGATIVE_CONTROL_ACCEPTED:'+fault)
   assert ledger.snapshot('original-mission')==amended
   with store.tx() as c:assert c.execute('SELECT record FROM afo_missions').fetchone()[0]==original_base
   print('SYMPTOM_ABSENT')
   return 0

def main():
 import pwd,sys
 try:pwd.getpwuid(os.getuid())
 except KeyError:
  from forge_factory.common import REPO_ROOT,data_root
  from forge_factory.reliability import isolation
  with tempfile.TemporaryDirectory(prefix='rpr174-private-nss-') as td:
   root=Path(td);passwd=root/'passwd'
   passwd.write_text(Path('/etc/passwd').read_text()+f'isolated-test-verifier:x:{os.getuid()}:{os.getgid()}:TEST:/tmp:/bin/sh\n')
   env={'PATH':'/usr/bin:/bin','FORGE_REPO_ROOT':str(REPO_ROOT),'FORGE_DATA_ROOT':str(data_root()),'PYTHONPATH':str(REPO_ROOT/'factory/python')}
   args=isolation.bubblewrap_argv('verifier',[sys.executable,str(Path(__file__).resolve())],cwd=REPO_ROOT,env=env,writable=[root],readable=[Path(__file__).resolve()])
   at=args.index('--chdir');args[at:at]=['--ro-bind',str(passwd),'/etc/passwd']
   ran=subprocess.run(args,capture_output=True,text=True,timeout=60)
   sys.stdout.write(ran.stdout);sys.stderr.write(ran.stderr)
   return ran.returncode
 return scenario()

if __name__=='__main__':
 raise SystemExit(main())
