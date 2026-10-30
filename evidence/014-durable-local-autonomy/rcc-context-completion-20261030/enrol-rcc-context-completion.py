"""One-shot authenticated role-only admission through existing AFO primitives; no new scheduler."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/rcc-context-completion-20261030-v1'
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
assert time.time()<scope['deadline_epoch'] and time.time()<scope['enrolment_latest_epoch']
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
    intent=I.read();assert intent['mode']=='RUNNING' and intent['epoch']==54
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
    assert S.order(scope['continuation_of'])['state']=='BLOCKED'
    assert L.snapshot(scope['mission_id'])==scope['mission_before']
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
    man={'work_order':wo,'local_profile':local,'purpose':'ASPICE_ONLY','layer':'LL','evaluation_holdout':True,
      'source_kind':'CURRENT_REAL_FACTORY_CODE_DEFECT_NOT_A_SEEDED_OUTAGE','no_product_launch':True,
      'mission_id':scope['mission_id'],'controller_revision':scope['source_revision'],'scope_sha256':digest(scope)}
    immutable_json(ws/'.forge-run/manifest.json',man)
    immutable_json(ws/'.forge-run/model-profile.json',{'default':scope['model']})
    S.attempt_transition(aid,'CANCELLED',workspace_ref='workorder:'+wo,factory_revision=scope['source_revision'],
      exit_status='ROLE_ONLY_QUALIFICATION_NO_PRODUCT_LAUNCH',finished_utc=utc_now())
    S.transition(oid,'RUNNING','Owner-authorized historical factory maintenance qualification; no product run')
    S.transition(oid,'WAITING_EXTERNAL_CHANGE','Controlled historical FACTORY_CODE_DEFECT replay',terminal_reason='HISTORICAL_FACTORY_CODE_DEFECT_REPLAY')
    incident={'order_id':oid,'origin':'ACTUAL_CURRENT_RCC_RETAINED_UNSUBMITTED_QWEN_PATCH',
      'source_order_id':scope['continuation_of'],'parent_job_id':scope['parent_job_id'],
      'source_native_run_id':scope['parent_native_run_id'],'native_write_seq':137,
      'phase':'FACTORY_MAINTENANCE','error_code':'UNSUBMITTED_DRAFT_CAPABILITY_LIMIT',
      'finding':'Retained Qwen structured.py patch passes all3 frozen original inspector-context tests. An inherited HTTP429 refusal test crashes with AttributeError: module time has no attribute monetic.',
      'engineering_obligation':'Preserve the retained profile-context repair, correct the independently measured unrelated call-path regression, add baseline-failing context reproducer and pytest, run candidate tests and submit. For a local change use the exact hash-bound edit_source operation; avoid full-file rewrite.',
      'candidate_file':'factory/python/forge_factory/lrtx/structured.py',
      'retained_file_sha256':scope['retained_seed']['sha256'],
      'context_feedback':'Original baseline uses24576 context despite selected262144. Retained candidate profile_context_tokens helper passes actual frozen262144/131072 inspector preparation and legacy24576 checks. Do not undo it.',
      'regression_feedback':'Existing test_da014_settled_usage.py::test_structured_refusal_preserves_bounded_typed_reason_without_body_leak fails at structured.call time.monetic before mocked HTTP429 handling; original baseline passes that inherited test.',
      'protocol_feedback':'Previous native session hit CAPABILITY_LIMIT after writing this exact file, before any reproducer or submission. No completion receipt exists. Complete the remaining test and submit obligations in this fresh bounded context; historical failure and charges are retained.',
      'reproducer_contract':'Register suffix only, without SYMPTOM_PRESENT: prefix. Sealed script must import baseline code from current working directory; baseline exits1 ending SYMPTOM_PRESENT:<suffix>, fixed candidate exits0 ending SYMPTOM_ABSENT:<suffix>. Reproduce original profile-context defect, not an already-correct baseline clock.',
      'scope_boundaries':'Only structured.py and candidate-owned tests. No policy/grant/gate/requirement changes, no deployment by model. Independent checker contents remain withheld.'}
    catalog=json.loads((O/'source-catalog.json').read_text())
    for index,row in enumerate(catalog['entries']):
      incident[f'source_catalog_file_{index}']=row['path']+'; bytes='+str(row['bytes'])+'; sha256='+row['sha256']
      names=','.join(x['name']+'@'+str(x['line']) for x in row['symbols'])
      for n,start in enumerate(range(0,len(names),350)):incident[f'source_catalog_symbols_{index}_{n}']=names[start:start+350]
    assert all(len(str(v))<=400 for v in incident.values())
    pid='mnt-'+oid.removeprefix('afo-')[:16]+'-a1'
    case=maintainer.prepare(pid,scope['repair_baseline_revision'],incident,repo=R)
    seed=Path(scope['retained_seed']['path']).read_bytes()
    assert hashlib.sha256(seed).hexdigest()==scope['retained_seed']['sha256']
    assert maintainer.write_source(case,'factory/python/forge_factory/lrtx/structured.py',seed.decode('utf-8'))==scope['retained_seed']['sha256']
    immutable_json(O/'retained-seed-receipt.json',{'schema':'forge-c/operator-retained-unsubmitted-seed/1','source':scope['retained_seed'],'parent_job_id':scope['parent_job_id'],'parent_native_run_id':scope['parent_native_run_id'],'case_sha256':sha256_file(maintainer.case_dir(pid)/'case.json'),'new_proposal_id':pid,'operator_code_edits':False,'completion_receipt_created':False,'independent_scope':scope['independent_seed_context_result'],'independent_regression':scope['independent_seed_regression_result'],'at':utc_now()})
    immutable_json(O/'enrolment.json',{'status':'AFO_MAINTENANCE_ENROLLED_NO_GENERATION_YET','order_id':oid,
      'attempt_id':aid,'proposal_id':pid,'mission_id':scope['mission_id'],'case_sha256':sha256_file(maintainer.case_dir(pid)/'case.json'),
      'source_revision':scope['source_revision'],'operations_epoch':54,'scheduler_fencing_epoch':lease,
      'role_registry_preflight':'PASS','scheduler_native_preflight':'PASS','model_requests':0,'at':utc_now()})
print((O/'enrolment.json').read_text(),flush=True)
with I.lock():
    assert I.read()['mode']=='RUNNING' and I.read()['epoch']==54
    subprocess.run(['systemctl','--user','--no-block','start','forge-conductor-local-omniverse2.service',
        'forge-afo-watchdog-014-omniverse2.timer'],check=True,timeout=20)
print(json.dumps({'status':'EXISTING_CONDUCTOR_STARTED_FOR_MAINTENANCE','order_id':scope['new_order_id']}),flush=True)
