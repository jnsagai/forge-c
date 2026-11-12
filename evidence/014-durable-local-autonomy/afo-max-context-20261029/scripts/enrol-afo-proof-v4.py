"""One-shot authenticated role-only admission through existing AFO primitives; no new scheduler."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/afo-repair-live-20261029-v4'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import authz,authority,contracts,operations,policy,maintainer,scheduler,local_agent
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.common import utc_now,sha256_file,state_dir
from forge_factory.lrtx import stack
from forge_factory.lrtx.profile import load
from forge_factory.registry.agents import preflight as agent_preflight
from forge_factory.mcp.preflight import preflight as mcp_preflight
from forge_factory.afo.product_role_trial import authorized as trial_authorized
scope=json.loads((O/'scope.json').read_text())
settings=stack.settings(scope['profile'])
assert os.readlink('/proc/self/ns/net')==json.loads((P/'run/services.json').read_text())['netns'], 'NATIVE_NETWORK_NAMESPACE_REQUIRED'
os.environ.update(stack.envmap(settings))
os.environ.setdefault('XDG_RUNTIME_DIR','/run/user/1000')
os.environ.setdefault('DBUS_SESSION_BUS_ADDRESS','unix:path=/run/user/1000/bus')
S=Store();I=operations.Intent();L=MissionLedger(S)
assert time.time()<scope['deadline_epoch']
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==scope['source_revision']
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'],text=True).strip()
observed=operations.observed_unit()
assert observed.get('ActiveState') in ('inactive','failed'),observed
eff=policy.load(log=False);assert eff.mode=='PILOT' and eff.sha256==scope['policy_sha256']
prof=load(scope['profile']);assert prof['_sha256']==scope['profile_sha256'] and not prof.get('development_execution_policy')
assert agent_preflight(['afo-factory-maintainer'],include_afo=True)['status']=='PASS'
assert mcp_preflight(['afo-factory-maintainer'],include_afo=True)['status']=='PASS'
trial=json.loads((O/'trial.json').read_text());ref=json.loads((O/'trial-ref.json').read_text())
env=json.loads((O/'envelope.json').read_text());contracts.require('work-order',env)
for action in ('submit_workorder','launch_workorder','recover_workorder'):
    decision=authority.decide(action,{'order_id':scope['request_id'],'driver_class':'LL','model':scope['model']},afo=eff)
    assert decision.allow,decision
g=json.loads((O/'roles-authorization.json').read_text())
assert authz.signature_valid(g,O/'roles-authorization-message.bin.sig',authz.ALLOWED_SIGNERS)
assert g['signed_runbook_ref']=='qualification-product-014:'+digest(trial)
with S.tx() as c:
    held=c.execute('SELECT expires_epoch FROM afo_leases WHERE scope=?',(scheduler.SCOPE,)).fetchone()
    assert not held or held[0]<=time.time(), 'SCHEDULER_LEASE_NOT_EXPIRED'
with I.lock():
    intent=I.read();assert intent['mode']=='RUNNING' and intent['epoch']==42
    assert not Executions(S).pending()
    with S.tx() as c:
        assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
        assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
    immutable_json(authz.AUTH_DIR/(g['authorization_id']+'.json'),g)
    immutable_bytes(authz.AUTH_DIR/g['signature_ref'],(O/'roles-authorization-message.bin.sig').read_bytes())
    check=authz.verify(g,policy_sha256=eff.sha256,mode=eff.mode,action='recover_workorder',
      request={'order_id':scope['request_id'],'driver_class':'LL','model':scope['model']})
    assert check.allow,check
    immutable_json(state_dir()/ref['path'],trial)
    old=S.order(scope['continuation_of']);assert old['state']=='WAITING_EXTERNAL_CHANGE'
    execution=Executions(S).get('afo-agent-5a107cd9d6c49697708b45a0')
    assert execution['execution_liveness']=='QUIESCENT' and execution['resource_lease']=='RELEASED' and execution['task_outcome']=='FAILED_PROTOCOL'
    with S.tx() as c:
        refusals=[json.loads(r[0]) for r in c.execute("SELECT record FROM afo_execution_evidence WHERE job_id=? AND kind LIKE 'REQUEST_REFUSAL:%'",('afo-agent-5a107cd9d6c49697708b45a0',))]
    assert refusals and all(r['code']=='CAPABILITY_LIMIT' and r['measurement']['input_tokens']==89824 and r['output_cap']==49152 and r['upstream_called'] is False for r in refusals)
    S.transition(old['order_id'],'BLOCKED','Actual V3 Qwen request refused: complete serialized89824+49152 exceeds131072; no candidate, execution independently quiescent',terminal_reason='SERIALIZED_CONTEXT_CAPABILITY_LIMIT_NO_CANDIDATE')
    assert L.snapshot(scope['mission_id'])==json.loads((O/'mission-before.json').read_text())
    L.link(scope['mission_id'],scope['new_order_id'],continuation_of=scope['continuation_of'])
    oid,created=S.submit(env,repo=O,max_queued=int(eff.get('queue.max_queued_orders')),
        approve=lambda _: (authority.decide('submit_workorder',{'order_id':scope['request_id'],'driver_class':'LL','model':scope['model']},afo=eff).allow,'SIGNED_SCOPED_OWNER_TRIAL'))
    assert oid==scope['new_order_id']
    job_identity={'order_id':oid,'profile':scope['profile'],'model':scope['model'],
      'model_digest':scope['model_digest'],'precision':'Q8_0','factory_revision':{'commit':scope['source_revision'],'dirty':False}}
    trial_authorized(ref,job_identity,eff)
    preflight=scheduler.preflight(S.order(oid),eff,S)
    assert not preflight,preflight
    lease=S.acquire_lease(scheduler.SCOPE,'owner-afo-repair-enrolment',15)
    assert lease is not None,'SCHEDULER_LEASE_STILL_OWNED'
    assert S.order(oid)['state']=='QUEUED'
    aid=S.admit(oid,epoch=lease,scope=scheduler.SCOPE,policy_sha256=eff.sha256,
        authorization_id=scope['primary_authorization'],max_concurrent=1,qualification_ref='qualification-014:'+digest(scope))
    wo='WO-'+aid.upper();ws=state_dir()/'workorders'/wo/'workspace';ws.mkdir(parents=True,mode=0o700)
    local={'id':prof['id'],'version':prof['version'],'config':prof['_path'],'config_sha256':prof['_sha256']}
    man={'work_order':wo,'local_profile':local,'purpose':'QM','layer':'LL','evaluation_holdout':True,
      'source_kind':'HISTORICAL_REAL_FAILURE_REPLAY_NOT_A_NEW_OUTAGE','no_product_launch':True,
      'mission_id':scope['mission_id'],'controller_revision':scope['source_revision'],'scope_sha256':digest(scope)}
    immutable_json(ws/'.forge-run/manifest.json',man)
    immutable_json(ws/'.forge-run/model-profile.json',{'default':scope['model']})
    S.attempt_transition(aid,'CANCELLED',workspace_ref='workorder:'+wo,factory_revision=scope['source_revision'],
      exit_status='ROLE_ONLY_QUALIFICATION_NO_PRODUCT_LAUNCH',finished_utc=utc_now())
    S.transition(oid,'RUNNING','Owner-authorized historical factory maintenance qualification; no product run')
    S.transition(oid,'WAITING_EXTERNAL_CHANGE','Controlled historical FACTORY_CODE_DEFECT replay',terminal_reason='HISTORICAL_FACTORY_CODE_DEFECT_REPLAY')
    neutral=P/'deployment/afo-repair-trial-20261029-v2/model-input'
    facts=json.loads((neutral/'incident.json').read_text())
    incident={'order_id':oid,'origin':facts['origin'],'source_order_id':facts['source_order_id'],
      'phase':'SWE.3','error_code':'PLANTUML_NOT_AVAILABLE','finding':facts['observed_finding'],
      'observed_environment':json.dumps(facts['environment_facts'],sort_keys=True),
      'candidate_file':facts['candidate_file'],'engineering_obligation':facts['engineering_obligation'],
      'trial_patch_scope':'; '.join(scope['allowed_patch_paths']),
      'incident_sha256':sha256_file(neutral/'incident.json'),
      'inspection_evidence_sha256':sha256_file(neutral/'source-evidence/frozen-swe3-transfer.json'),
      'environment_evidence_sha256':sha256_file(neutral/'source-evidence/actual-mcp-environment.json')}
    incident.update(json.loads((O/'incident-catalog-fields.json').read_text()))
    assert all(len(str(v))<=400 for v in incident.values())
    pid='mnt-'+oid.removeprefix('afo-')[:16]+'-a1'
    case=maintainer.prepare(pid,scope['repair_baseline_revision'],incident,repo=R)
    immutable_json(O/'enrolment.json',{'status':'AFO_MAINTENANCE_ENROLLED_NO_GENERATION_YET','order_id':oid,
      'attempt_id':aid,'proposal_id':pid,'mission_id':scope['mission_id'],'case_sha256':sha256_file(maintainer.case_dir(pid)/'case.json'),
      'source_revision':scope['source_revision'],'operations_epoch':42,'scheduler_fencing_epoch':lease,
      'role_registry_preflight':'PASS','scheduler_native_preflight':'PASS','model_requests':0,'at':utc_now()})
print((O/'enrolment.json').read_text(),flush=True)
with I.lock():
    assert I.read()['mode']=='RUNNING' and I.read()['epoch']==42
    subprocess.run(['systemctl','--user','--no-block','start','forge-conductor-local-omniverse2.service',
        'forge-afo-watchdog-014-omniverse2.timer'],check=True,timeout=20)
print(json.dumps({'status':'EXISTING_CONDUCTOR_STARTED_FOR_MAINTENANCE','order_id':scope['new_order_id']}),flush=True)
