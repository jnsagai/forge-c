"""Exact public entry + private sequence controls. No remote/systemd/cleanup effects."""
import copy,hashlib,importlib.util,json,os,subprocess,sys,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
O=Path(__file__).resolve().parent;HELPER=O/'owner-profile-bootstrap-f0-cleanup-start-r1.py';P=O/'owner-profile-bootstrap-f0c8fc5c-main-review-20261105/owner-main-ops';C=O/'owner-bootstrap-642-f0-cleanup-v3-review-20261105'
results=[]
def control(name,fn):
 try:fn();results.append(dict(name=name,PASS=True))
 except BaseException as e:results.append(dict(name=name,PASS=False,error_type=type(e).__name__,error=str(e)[:200]))
def module():
 spec=importlib.util.spec_from_file_location('bridge_private',HELPER);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
for key in ['FORGE_AGENT_ROLE','FORGE_WORKSPACE','FORGE_POLICY_BINDING','FORGE_OWNER_DEVELOPMENT_RECORD','FORGE_OWNER_DEVELOPMENT_SHA256','FORGE_LINE_STACK_PAYLOAD','FORGE_LINE_STACK_PAYLOAD_SHA256','FORGE_STACK_LOCK_FD']:
 def entry(k=key):
  env={a:b for a,b in os.environ.items() if not a.startswith('FORGE_')};env[k]='PRIVATE_FORBIDDEN_CONTROL'
  r=subprocess.run([sys.executable,str(HELPER),'--apply-reviewed'],env=env,capture_output=True,text=True,timeout=3)
  assert r.returncode!=0 and 'CLEAN_EXTERNAL_OPERATOR_CONTEXT_REQUIRED' in r.stderr
 control('public_entry_refuses_'+key,entry)
def default():
 r=subprocess.run([sys.executable,str(HELPER)],capture_output=True,text=True,timeout=3);assert r.returncode==0 and json.loads(r.stdout)['effects'] is False
control('actual_default_PLAN_ONLY',default)
def location():
 env={a:b for a,b in os.environ.items() if not a.startswith('FORGE_')};r=subprocess.run([sys.executable,str(HELPER),'--apply-reviewed'],env=env,capture_output=True,text=True,timeout=3);assert r.returncode!=0 and 'EXACT_SEQUENCE_LOCATION_REQUIRED' in r.stderr
control('clean_public_entry_wrong_location_refuses_before_marker',location)

def sequence(change=None):
 m=module()
 with tempfile.TemporaryDirectory() as temp:
  root=Path(temp);R=root/'new';OPS=R/'owner-main-ops';FAILED=root/'old887';FAILED214=root/'old214';OPS.mkdir(parents=True);(FAILED214/'partial-reconciliation-r1').mkdir(parents=True)
  m.F=root;m.R=R;m.OPS=OPS;m.FAILED=FAILED;m.FAILED214=FAILED214;m.__file__=str(OPS/'bridge.py')
  for name,src in [('cleanup-exact-failed642-v3.py',C/'cleanup-exact-failed642-v3.py'),('exact-642-expectation-v2.json',C/'exact-642-expectation-v2.json'),('start-main-reviewed.py',P/'start-main-reviewed.py'),('binding.json',P/'binding.json')]: (OPS/name).write_bytes(src.read_bytes())
  meta=R/'metadata-f0-reviewed/result.json';meta.parent.mkdir();meta.write_text(json.dumps(dict(state='METADATA_APPENDED_NO_RUNTIME_START',source='wrong' if change=='metadata' else m.SOURCE,binding_sha256=m.BINDING_SHA)))
  ticket=OPS/'ticket.json';ticket.write_text('{"TEST_TICKET_ONLY":true}')
  for name in ['intent.json','unknown-result.json']:(FAILED214/'partial-reconciliation-r1'/name).write_text('TEST_HISTORICAL_AUDIT_LEAF')
  real_sha=m.sha
  def fixture_sha(path):
   if path==FAILED214/'partial-reconciliation-r1/intent.json':return '60163c6107266a4e61d88e5bf185b54692e106e2fdb3c61d4bc69bdfab5d1225'
   if path==FAILED214/'partial-reconciliation-r1/unknown-result.json':return 'c0f762ac261fc5e1f95738a66f8f606e3c433696d40e17d5a1244623c84a95a0'
   return real_sha(path)
  m.sha=fixture_sha;events=[];validations=[]
  def ticket_leaf(path):
   validations.append(path)
   if change=='ticket_before' or change=='ticket_after_marker' and len(validations)==2:raise RuntimeError('PRIVATE_NORMAL_TICKET_LEAF_REFUSED')
  m.validate_ticket=ticket_leaf
  oldR1={str(f):f.read_bytes()for f in (FAILED214/'partial-reconciliation-r1').iterdir()}
  def effect_leaf(argv,**kw):
   assert kw['env']['XDG_RUNTIME_DIR']=='PRIVATE_EXISTING_SSH_BUS' and kw['env']['DBUS_SESSION_BUS_ADDRESS']=='PRIVATE_EXISTING_DBUS';assert not any(k in kw['env'] for k in ('FORGE_AGENT_ROLE','FORGE_OWNER_DEVELOPMENT_RECORD','FORGE_LINE_STACK_PAYLOAD'))
   assert (R/'root-cleanup-start-f0-attempt-r1.json').is_file()
   if 'cleanup-exact-failed642-v3.py' in argv[1]:
    events.append('cleanup');assert kw['timeout']==110 and kw['env']['FORGE_REPO_ROOT']==str(FAILED/'newS') and argv[-1]==m.SOURCE
    if change=='timeout_cleanup':raise subprocess.TimeoutExpired(['PRIVATE_EFFECT_LEAF'],110)
    if change=='cleanup_failed':return SimpleNamespace(returncode=1)
    audit=FAILED/'partial-reconciliation-642-f0-r1';audit.mkdir(parents=True);ev=OPS/'private-evidence.json';ev.write_text('{"PRIVATE_EVIDENCE_ONLY":true}');(audit/'verified-result.json').write_text(json.dumps(dict(status='EXACT_PARTIAL_LIFETIMES_QUIET_HISTORY_CONSERVED',evidence_ref=dict(path=str(ev),sha256=real_sha(ev)))))
   else:
    events.append('start');assert kw['timeout']==700 and kw['env']['FORGE_REPO_ROOT']==str(R/'newS') and argv[1]==str(OPS/'start-main-reviewed.py');assert events==['cleanup','start']
    if change=='start_failed':return SimpleNamespace(returncode=1)
    (R/'owner-main-readiness-f0.json').write_text(json.dumps(dict(state='NEW_MAIN_GUARDIAN_RECONCILED_BOOTSTRAP_READY_PLACING_SCOPE_UNACCEPTED',source=m.SOURCE)))
   return SimpleNamespace(returncode=0)
  args=[str(HELPER),'--apply-reviewed','--starter',str(OPS/'start-main-reviewed.py'),'--starter-sha256',m.STARTER_SHA,'--ticket',str(ticket),'--ticket-sha256',real_sha(ticket),'--metadata-receipt-sha256',real_sha(meta)]
  env={k:v for k,v in os.environ.items() if not k.startswith('FORGE_')};env.update(XDG_RUNTIME_DIR='PRIVATE_EXISTING_SSH_BUS',DBUS_SESSION_BUS_ADDRESS='PRIVATE_EXISTING_DBUS')
  with patch.dict(os.environ,env,clear=True),patch.object(sys,'argv',args),patch.object(m.subprocess,'run',effect_leaf):
   if change:
    try:m.main()
    except RuntimeError:pass
    else:raise AssertionError('PRIVATE_NEGATIVE_ACCEPTED')
   else:m.main()
   if change in ('metadata','ticket_before'):assert events==[] and not (R/'root-cleanup-start-f0-attempt-r1.json').exists()
   elif change=='ticket_after_marker':assert events==[] and (R/'root-cleanup-start-f0-unknown-r1.json').is_file()
   elif change in ('cleanup_failed','timeout_cleanup'):assert events==['cleanup'] and (R/'root-cleanup-start-f0-unknown-r1.json').is_file()
   elif change=='start_failed':assert events==['cleanup','start'] and (R/'root-cleanup-start-f0-unknown-r1.json').is_file()
   else:assert events==['cleanup','start'] and (R/'root-cleanup-start-f0-result-r1.json').is_file() and len(validations)==2
   assert all(Path(f).read_bytes()==v for f,v in oldR1.items())
   if (R/'root-cleanup-start-f0-attempt-r1.json').exists():
    before=list(events)
    try:m.main()
    except RuntimeError as e:assert 'ALREADY_ATTEMPTED_NO_REPLAY' in str(e)
    else:raise AssertionError('REPLAY_ACCEPTED')
    assert events==before
control('private_sequence_actualpinnedfiles_env_userbus_cleanup_then_start_markers_and_no_replay',sequence)
for change in ['metadata','ticket_before','ticket_after_marker','cleanup_failed','timeout_cleanup','start_failed']:
 control('private_sequence_refuses_'+change,lambda change=change:sequence(change))
report=dict(schema='forge-c/f0-root-bridge-private-controls/1',helper_sha256=hashlib.sha256(HELPER.read_bytes()).hexdigest(),PASS=sum(r['PASS']for r in results),FAIL=sum(not r['PASS']for r in results),results=results,scope='Actual public entries/defaults plus wholebridge in private filesystem with explicitly substituted expiry-ticket validation, historicalaudit digest and subprocess effect leaves; no real authority, cleanup, systemd, remote or ticket issuance.',actual_remote_effects=False,all_private_handles_closed=True)
with(O/'owner-profile-bootstrap-f0-bridge-private-controls-r1.json').open('x')as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(report));raise SystemExit(bool(report['FAIL']))
