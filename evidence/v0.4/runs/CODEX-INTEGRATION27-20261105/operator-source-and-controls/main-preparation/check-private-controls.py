"""Private staged JSON/SQLite/socket publication controls; no systemd/real state effects."""
import ast,copy,hashlib,importlib.util,json,os,sqlite3,subprocess,sys,tempfile,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;P=HERE/'owner-main-ops/start-main-reviewed.py'
s=importlib.util.spec_from_file_location('starter',P);M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
SOURCE=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-owner-namespace-history-v6');os.environ['FORGE_REPO_ROOT']=str(SOURCE);sys.path.insert(0,str(SOURCE/'factory/python'))
from forge_factory.afo import owner_supervised_development as REAL
from forge_factory.afo.durable import Refused,canonical,digest
from forge_factory.lrtx.provider_process import identity,owner_view
results=[]
def control(name,fn):
 try:fn();results.append({'name':name,'PASS':True})
 except BaseException as e:results.append({'name':name,'PASS':False,'error':type(e).__name__+':'+str(e)})
def refuses(fn,code):
 try:fn()
 except Exception as e:assert code in str(e),(code,str(e));return
 raise AssertionError('DID_NOT_REFUSE')
def publication_case(change=None):
 with tempfile.TemporaryDirectory() as t:
  parent=Path(t);parent.chmod(0o700);sock=parent/'guardian.sock';dbpath=parent/'state.db'
  code="""import socket,sys,json,os
from pathlib import Path
s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.bind(sys.argv[1]);print('BOUND',flush=True)
h=sys.stdin.readline().strip();s.listen(4);print('LISTENING',flush=True)
while True:
 c,_=s.accept()
 with c:
  r=json.loads(c.recv(4096));c.sendall(json.dumps({'record_sha256':h,'nonce':r['nonce'],'scope':'OWNER_SUPERVISED_DEVELOPMENT'},sort_keys=True,separators=(',',':')).encode())
"""
  child=subprocess.Popen([sys.executable,'-c',code,str(sock)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  saved={k:os.environ.get(k) for k in [REAL.FILE,REAL.SHA]}
  try:
   assert child.stdout.readline().strip()=='BOUND';kernel=identity(child.pid);st=sock.stat()
   record={'guardian_pid':child.pid,'guardian':{k:v for k,v in kernel.items() if k!='state'},'guardian_socket':str(sock),'guardian_socket_identity':{'device':st.st_dev,'inode':st.st_ino},'control_context':{'user_namespace':owner_view(os.getpid())['user_namespace']},'source_revisions':['f0c8fc5c8ae83952a05cea578d41e0ff06324afd'],'control_ref':{'sha256':'c'*64},'profile_sha256':'p'*64}
   h=digest(record);path=parent/(h+'.json');path.write_bytes(b'{"guardian_pid":');path.chmod(0o600)
   with sqlite3.connect(dbpath) as c:c.execute('CREATE TABLE afo_independent_decisions(decision_id TEXT,kind TEXT,record TEXT,sha256 TEXT)')
   calls=[]
   def actual_attestation_leaf():
    calls.append('normal_D_attestation')
    if change=='authfatal':raise Refused('OWNER_DEVELOPMENT_CONTROL_CHANGED')
    REAL._attest(record,str(sock));return record
   D=SimpleNamespace(_private=REAL._private,guardian_alive=REAL.guardian_alive,MODE=REAL.MODE,FILE=REAL.FILE,SHA=REAL.SHA,current=actual_attestation_leaf)
   observe=lambda:M.observe_issuing_record(parent,child.pid,dbpath,D,{},record['source_revisions'][0],'c'*64,'p'*64)
   assert observe() is None and calls==[] # Actual partialJSON, no normal auth attempted.
   path.write_bytes(canonical(record));assert observe() is None and calls==[] # Complete file, no issuerrow yet.
   with sqlite3.connect(dbpath) as c:c.execute('INSERT INTO afo_independent_decisions VALUES(?,?,?,?)',('owner-development-'+h,REAL.MODE,canonical(record).decode(),h if change!='row' else '0'*64))
   if change=='row':refuses(observe,'NEW_ISSUER_CANONICAL_ROW_CHANGED');return
   if change=='authfatal':refuses(observe,'OWNER_DEVELOPMENT_CONTROL_CHANGED');return
   assert observe() is None and calls==['normal_D_attestation'] # Real bound socket not listening yet => unavailable.
   child.stdin.write(h+'\n');child.stdin.flush();assert child.stdout.readline().strip()=='LISTENING'
   found=observe();assert found==(path,record)
   if change=='baseline':
    old=parent/('a'*64+'.json');old.write_bytes(b'PRIVATE_OLD');old.chmod(0o600);base={str(old):M.sha(old)};old.write_bytes(b'CHANGED')
    refuses(lambda:M.observe_issuing_record(parent,child.pid,dbpath,D,base,record['source_revisions'][0],'c'*64,'p'*64),'OLD_RECORD_CHANGED_DURING_STARTUP')
   if change=='foreign':refuses(lambda:M.observe_issuing_record(parent,child.pid+1,dbpath,D,{},record['source_revisions'][0],'c'*64,'p'*64),'NEW_RECORD_PID_OR_CONTENT_REBOUND')
   if change=='established':
    # Execute exact established-authority branch; exception must propagate.
    tree=ast.parse(P.read_text());main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main');branch=next(n for n in ast.walk(main) if isinstance(n,ast.If) and isinstance(n.test,ast.Name) and n.test.id=='established')
    def revoked():raise Refused('OWNER_DEVELOPMENT_GUARDIAN_ATTESTATION_UNAVAILABLE')
    env={'established':(path,record),'sha':M.sha,'digest':M.digest,'need':M.need,'os':os,'D':SimpleNamespace(FILE=REAL.FILE,SHA=REAL.SHA,current=revoked)}
    wrapped=ast.FunctionDef(name='private_established_branch',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),body=[branch],decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[wrapped],type_ignores=[])),'exact_established_branch','exec'),env)
    refuses(env['private_established_branch'],'OWNER_DEVELOPMENT_GUARDIAN_ATTESTATION_UNAVAILABLE')
  finally:
   child.terminate();child.communicate(timeout=3)
   for k,v in saved.items():
    if v is None:os.environ.pop(k,None)
    else:os.environ[k]=v
control('actual_partialJSON_then_canonicalrow_then_socketlisten_publication_waits_to_authenticate',publication_case)
for ch in ['row','authfatal','baseline','foreign','established']:control('publication_refuses_'+ch,lambda ch=ch:publication_case(ch))
def static_and_default():
 tree=ast.parse(P.read_text());assert "publishing_until=min(until,time.monotonic()+30)" in P.read_text();assert 'ISSUING_UNIT_PID_OR_INVOCATION_CHANGED' in P.read_text();assert M.BINDING_SHA=='576c8af67548e57efb1363c8f80f117600ac4c067ffa9dbe6d60782237ef9733'
 r=subprocess.run([sys.executable,str(P)],capture_output=True,text=True,timeout=3);assert r.returncode==0 and json.loads(r.stdout)['effects'] is False
control('actual_default_and_bounded_exactunit_publication_scope_static_controls',static_and_default)
def unit_state_case(change=None):
 view={'LoadState':'loaded','ActiveState':'active','MainPID':'123','InvocationID':'a'*32}
 if change=='activating':view['ActiveState']='activating'
 if change=='pid':view['MainPID']='124'
 if change=='invocation':view['InvocationID']='b'*32
 if change in ('pid','invocation'):refuses(lambda:M.require_issuing_unit(view,123,'a'*32),'ISSUING_UNIT_CHANGED_DURING_PUBLICATION_CHECK')
 else:M.require_issuing_unit(view,123,'a'*32)
control('same_PID_invocation_activating_to_active_accepted',unit_state_case)
control('same_PID_invocation_still_activating_accepted',lambda:unit_state_case('activating'))
control('changed_PID_during_publication_refused',lambda:unit_state_case('pid'))
control('changed_invocation_during_publication_refused',lambda:unit_state_case('invocation'))
def deadline_case():
 M.require_publication_deadline(time.monotonic()+1)
 refuses(lambda:M.require_publication_deadline(time.monotonic()-1),'GUARDIAN_PUBLICATION_TIMEOUT_NO_RETRY')
control('late_return_from_blocking_publication_cannot_establish',deadline_case)

from forge_factory.afo import owner_bootstrap_reconciliation as Q

def consumption_case(change=None):
 # Real private SQLite+normal source hashrow/consumption value; only historical
 # control/trial lookup leaf is replaced, not claimed as source authority test.
 with tempfile.TemporaryDirectory() as temp:
  db=sqlite3.connect(Path(temp)/'state.db');db.execute('CREATE TABLE afo_independent_decisions(decision_id TEXT PRIMARY KEY,kind TEXT,record TEXT,sha256 TEXT)')
  live={'source_revisions':[M.SOURCE]};current=M.digest(live);successor_id='owner-profile-bootstrap-'+current
  binding=json.loads((HERE/'owner-main-ops/binding.json').read_text());old_id=binding['reconciliation']['old_intent_id'];ev={'path':binding['reconciliation']['evidence_path'],'sha256':'e'*64}
  request={'intent_id':old_id,'result_sha256':binding['reconciliation']['old_result_sha256'],'evidence_ref':ev}
  ackid=old_id+'-reconciliation-'+M.digest({'request':request,'issuer':current})
  ack={'request':request,'reconciler_record_sha256':current,'reconciler_source_revisions':[M.SOURCE],'bindings':{'old_intent_sha256':binding['reconciliation']['old_intent_sha256']}}
  token={'decision_id':ackid,'sha256':M.digest(ack)}
  successor={'schema':'forge-c/owner-profile-bootstrap-intent/2','record_sha256':current,'reconciliation_ref':token}
  consumed=Q._consumption_value(old_id,token,current=live,successor_id=successor_id,successor=successor)
  if change=='foreignissuer':ack['reconciler_record_sha256']='f'*64
  if change=='old214':ack['request']=dict(request,intent_id='owner-profile-bootstrap-ebf'+'0'*61)
  if change=='oldintenthash':ack['bindings']['old_intent_sha256']='0'*64
  if change=='successor_ref':successor['reconciliation_ref']={'decision_id':'foreign','sha256':'0'*64}
  if change=='consumed_sha':consumed['successor_intent_sha256']='0'*64
  if change=='consumed_oldid':consumed['old_intent_id']='foreign'
  if change=='legacy':successor['schema']='forge-c/owner-profile-bootstrap-intent/1'
  for key,kind,value in [(ackid,Q.KIND,ack),(successor_id+'-reconciliation-consumed',Q.CONSUMED_KIND,consumed)]:
   if change=='missingconsumed' and kind==Q.CONSUMED_KIND:continue
   db.execute('INSERT INTO afo_independent_decisions VALUES(?,?,?,?)',(key,kind,canonical(value).decode(), '0'*64 if change=='badhash' and kind==Q.KIND else M.digest(value)))
  calls=[]
  def chain(c,r,i,a):calls.append('normal_chain_leaf');return live,successor_id,successor
  try:
   with patch.object(Q,'_chain',chain):
    if change:
     try:M.verify_reconciled_chain(db,live,binding,ev)
     except Exception:pass
     else:raise AssertionError('UNSAFE_CONSUMPTION_ACCEPTED:'+change)
    else:
     got=M.verify_reconciled_chain(db,live,binding,ev);assert got['successor_intent_id']==successor_id and calls==['normal_chain_leaf']
  finally:db.close()
control('actual_SQL_current642_ACK_CONSUMED_successor_binding_positive',consumption_case)
for change in ['foreignissuer','old214','oldintenthash','successor_ref','consumed_sha','consumed_oldid','legacy','missingconsumed','badhash']:
 control('current642_chain_refuses_'+change,lambda change=change:consumption_case(change))

def exact_metadata_and_command():
 binding=json.loads((HERE/'owner-main-ops/binding.json').read_text());capture=json.loads((HERE/'readonly-remote-bindings.json').read_text());assert len(binding['inputs'])==12 and len(binding['source_files'])==14
 assert binding['files']=={r['path']:r['sha256'] for r in capture['files']}
 assert M.SOURCE==binding['source'] and M.OLD_UNIT==binding['old_unit'] and M.UNIT==binding['unit']
 assert '642087d2' in binding['reconciliation']['old_intent_id'] and binding['reconciliation']['old_intent_sha256']=='b432d51de1413ed18aa70d84501d8260efa8ed9870ccb8c928562f00f42fb16a'
 text=P.read_text();tree=ast.parse(text);strings=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
 for flag in ['--bootstrap-managed-profile','--reconcile-bootstrap-intent','--reconcile-bootstrap-result-sha256','--reconcile-bootstrap-evidence','--reconcile-bootstrap-evidence-sha256','--property=Restart=no','--property=KillMode=process','--property=NoNewPrivileges=yes']:assert flag in strings
 assert '--max-cycles' not in strings
 assert 'owner-main-start-attempt-f0.json' in text and 'owner-main-unknown-f0.json' in text
 assert 'D.validate_expiry_ticket(ticket,1795057626.0);evidence_fresh()' in text
 assert 'operations.fenced_call(evidence['intent_epoch'],request_start)' in text
 meta=HERE/'owner-main-ops/install-metadata-reviewed.py';r=subprocess.run([sys.executable,str(meta)],capture_output=True,text=True,timeout=3);assert r.returncode==0 and json.loads(r.stdout)['effects'] is False
control('exact_remote_binding_fourflags_fixeddeadline_Intentfence_no_cycles_metadata_default',exact_metadata_and_command)
report={'schema':'forge-c/f0-main-private-controls/1','PASS':sum(r['PASS'] for r in results),'FAIL':sum(not r['PASS'] for r in results),'results':results,'scope':'Real private JSON/SQLite issuerrow publication/socket.bind beforelisten, actual sourceD._attest/kernel/SO_PEERCRED nonce; D.current policy/mission/fullcanonicalStore leaf PRIVATE overlay. Exact establishedbranch has fatal auth error. No actualsystemd/ownerrecord/model/canonicalstate.','helper_source_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),'metadata_sha256':hashlib.sha256((HERE/'owner-main-ops/install-metadata-reviewed.py').read_bytes()).hexdigest(),'binding_sha256':M.BINDING_SHA,'all_private_handles_closed':True,'no_actual_remote_effects':True}
with(HERE/'private-controls-r1.json').open('x') as f:json.dump(report,f,sort_keys=True,indent=2)
print(json.dumps(report));raise SystemExit(bool(report['FAIL']))
