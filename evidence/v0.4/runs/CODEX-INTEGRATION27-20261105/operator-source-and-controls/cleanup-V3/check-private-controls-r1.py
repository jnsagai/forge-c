"""Private harmless PID graph + SQL/hash/FD controls. No canonical data or services."""
import copy,importlib.util,json,os,signal,sqlite3,subprocess,sys,tempfile,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;P=HERE/'cleanup-exact-failed642-v3.py'
s=importlib.util.spec_from_file_location('cleanup',P);M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
V9=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/ops/scratch/owner-development-legacy-retirement-v9/retire-legacy-v9-DRAFT.py');s=importlib.util.spec_from_file_location('old',V9);OLD=importlib.util.module_from_spec(s);s.loader.exec_module(OLD)
SOURCE=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-owner-namespace-history-v6');sys.path.insert(0,str(SOURCE/'factory/python'))
from forge_factory.lrtx import pidfd
results=[]
def control(name,fn):
 try:fn();results.append({'name':name,'PASS':True})
 except BaseException as e:results.append({'name':name,'PASS':False,'error':type(e).__name__+':'+str(e)})
def refuses(fn,code):
 try:fn()
 except RuntimeError as e:assert code in str(e),(code,str(e));return
 raise AssertionError('DID_NOT_REFUSE')
def actual_graph(change=None):
 with tempfile.TemporaryDirectory() as t:
  root=Path(t);(root/'holder.pid').write_text('PRIVATE');(root/'history').write_bytes(b'PRIVATE_HISTORY');(root/'unknown').write_bytes(b'OLD214_AND_642_UNKNOWN_IMMUTABLE')
  ignore=change!='not_ignored'
  child="import os,signal,time;signal.signal(signal.SIGTERM,"+('signal.SIG_IGN' if ignore else 'signal.SIG_DFL')+");print(os.getpid(),flush=True);time.sleep(60)"
  waiter=subprocess.Popen(['unshare','--user','--map-root-user','--net','--fork',sys.executable,'-c',child],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  holder=int(waiter.stdout.readline());children={}
  for name in ['bridge_outer','bridge_inner','fabro']:
   p=subprocess.Popen([sys.executable,'-c',"import time;print('READY',flush=True);time.sleep(60)"],stdout=subprocess.PIPE,text=True);assert p.stdout.readline().strip()=='READY';children[name]=p
  try:
   expected={n:{'kernel':M.identity(p.pid)} for n,p in children.items()};expected.update(holder={'kernel':M.identity(holder)},waiter={'kernel':M.identity(waiter.pid)})
   r=object.__new__(M.Runtime);r.exp={'processes':expected};r.retired=set();r.actions=[];r.pidfd=pidfd;r.deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+10
   def guard(stage):
    assert (root/'history').read_bytes()==b'PRIVATE_HISTORY' and (root/'unknown').read_bytes()==b'OLD214_AND_642_UNKNOWN_IMMUTABLE'
    if change=='unknown':raise RuntimeError('PRIVATE_UNKNOWN_OCCUPANT')
    if change=='active':raise RuntimeError('PRIVATE_ACTIVE_REQUEST')
    if change=='rebound':raise RuntimeError('PRIVATE_LIFETIME_REBOUND')
    if 'holder'not in r.retired:M.require_holder_term_ignored(holder)
    for name,item in expected.items():
     if name not in r.retired:M.check_lifetime(item['kernel'],M.identity(item['kernel']['pid']))
   r.guard=guard;r.tail=lambda:None;r.remove_holder_file=lambda:(root/'holder.pid').unlink();r.verify_and_emit=lambda:None
   if change:
    refuses(lambda:M.reap(r),{'not_ignored':'HOLDER_TERM_IGNORE_PROOF_CHANGED','unknown':'PRIVATE_UNKNOWN_OCCUPANT','active':'PRIVATE_ACTIVE_REQUEST','rebound':'PRIVATE_LIFETIME_REBOUND'}[change]);assert r.actions==[] and M.identity(holder)['state']!='Z'
   else:
    M.reap(r);assert [(a['name'],a['signal']) for a in r.actions]==[('bridge_outer','SIGTERM'),('bridge_inner','SIGTERM'),('fabro','SIGTERM'),('holder','SIGKILL')]
    assert not(root/'holder.pid').exists();assert all(M.quiet(item['kernel']) for item in expected.values())
    assert all(a['name']!='waiter' for a in r.actions)
   refuses(lambda:M.Runtime.signal(r,'holder',signal.SIGTERM),'ONLY_EXACT_PLANNED_SIGNAL_ALLOWED')
   refuses(lambda:M.Runtime.signal(r,'waiter',signal.SIGKILL),'ONLY_EXACT_PLANNED_SIGNAL_ALLOWED')
   refuses(lambda:M.Runtime.signal(r,'fabro',signal.SIGKILL),'ONLY_EXACT_PLANNED_SIGNAL_ALLOWED')
  finally:
   for p in children.values():
    if p.poll() is None:p.terminate()
    p.communicate(timeout=3)
   alive=M.identity(holder)
   if alive is not None and alive['state']!='Z':os.kill(holder,signal.SIGKILL)
   waiter.communicate(timeout=3)
control('actual_five_lifetime_graph_send_fence_TERM_then_planned_holderKILL_waiter_natural',actual_graph)
for change in ['not_ignored','unknown','active','rebound']:control('beforeeffect_refuses_'+change,lambda change=change:actual_graph(change))

def sql_resources(change=None):
 with tempfile.TemporaryDirectory() as t:
  p=Path(t)/'state.db';c=sqlite3.connect(p);c.row_factory=sqlite3.Row
  c.executescript("CREATE TABLE afo_resource_ownership(resource TEXT,holder TEXT);CREATE TABLE afo_execution_liveness(record TEXT);CREATE TABLE afo_request_ledger(state TEXT);CREATE TABLE afo_work_orders(order_id TEXT,state TEXT);CREATE TABLE afo_commands_outbox(state TEXT);CREATE TABLE afo_attempts(attempt_id TEXT);")
  r=object.__new__(M.Runtime);r.producer={'orders':{},'attempts':{},'failed_commands':{}};r.M=OLD;r.record={'order_ids':['PRIVATE_B']}
  if change=='resource':c.execute("INSERT INTO afo_resource_ownership VALUES('inference','foreign')")
  if change=='lease':c.execute('INSERT INTO afo_execution_liveness VALUES(?)',(json.dumps({'resource_lease':'HELD'}),))
  if change=='request':c.execute("INSERT INTO afo_request_ledger VALUES('UNKNOWN')")
  if change=='order':c.execute("INSERT INTO afo_work_orders VALUES('PRIVATE','RUNNING')")
  if change=='command':c.execute("INSERT INTO afo_commands_outbox VALUES('UNKNOWN')")
  c.commit()
  if change:refuses(lambda:r.resources(c),{'resource':'RESOURCE_OWNER_BUSY','lease':'EXECUTION_NOT_RELEASED','request':'REQUEST_NOT_QUIESCENT','order':'ACTIVE_ORDER','command':'UNRESOLVED_COMMAND'}[change])
  else:r.resources(c)
  c.close()
control('actual_private_SQL_resource_boundary_quiet_positive',sql_resources)
for ch in ['resource','lease','request','order','command']:control('actual_private_SQL_resource_refuses_'+ch,lambda ch=ch:sql_resources(ch))

def unit_case(change=None):
 r=object.__new__(M.Runtime);r.exp={'unit':{'InvocationID':'3'*32}}
 v={'LoadState':'loaded','ActiveState':'failed','MainPID':'0','InvocationID':'3'*32}
 if change=='collected':v={'LoadState':'not-found','ActiveState':'inactive','MainPID':'0','InvocationID':''}
 if change=='active':v['MainPID']='123';v['ActiveState']='active'
 if change=='rebound':v['InvocationID']='4'*32
 with patch.object(M.subprocess,'check_output',lambda *a,**k:'\n'.join(k+'='+v for k,v in v.items())):
  if change in ['active','rebound']:refuses(r.unit,'FAILED_UNIT_REBOUND')
  else:r.unit()
control('unit_loaded_failed_original_invocation_positive',unit_case)
control('unit_legitimately_collected_inactive_accepted_without_reset',lambda:unit_case('collected'))
control('unit_active_foreign_actor_refused',lambda:unit_case('active'))
control('unit_rebound_invocation_refused',lambda:unit_case('rebound'))

def plan():
 p=subprocess.run([sys.executable,str(P)],capture_output=True,text=True,timeout=3);assert p.returncode==0,p.stderr;v=json.loads(p.stdout);assert v['status']=='PLAN_ONLY_NOT_EXECUTED' and v['effects'] is False
control('actual_default_PLAN_ONLY_no_runtime_import_or_effect',plan)
def process_context_case(change=None):
 p=subprocess.Popen([sys.executable,'-c',"import time;print('READY',flush=True);time.sleep(60)"],stdout=subprocess.PIPE,text=True)
 try:
  assert p.stdout.readline().strip()=='READY';base=Path('/proc')/str(p.pid)
  item={'kernel':M.identity(p.pid),'exe':os.readlink(base/'exe'),'argv_sha256':OLD.digest(OLD.kernel_argv_vector((base/'cmdline').read_bytes())),'namespace':{k:os.readlink(base/k) for k in ['ns/net','ns/user','ns/pid']},'uid_map':[list(map(int,x.split())) for x in (base/'uid_map').read_text().splitlines()],'cgroup':(base/'cgroup').read_text().strip(),'env_sha256':M.sha(base/'environ')}
  if change=='namespace':item['namespace']['ns/net']='net:[1]'
  if change=='argv':item['argv_sha256']='0'*64
  if change=='context':item['env_sha256']='0'*64
  r=object.__new__(M.Runtime);r.M=OLD;r.exp={'processes':{'fabro':item}};r.retired={'holder'} # isolatedmethod fixture; no production __init__ bypass claim
  if change:refuses(r.processes,{'namespace':'PROCESS_NAMESPACE_OR_SCOPE_REBOUND','argv':'PROCESS_EXE_OR_ARGV_REBOUND','context':'PROCESS_CONTEXT_REBOUND'}[change])
  else:r.processes()
 finally:p.terminate();p.communicate(timeout=3)
control('actual_Runtime_process_context_private_kernel_positive',process_context_case)
for change in ['namespace','argv','context']:control('actual_Runtime_process_context_refuses_'+change,lambda change=change:process_context_case(change))

def fd_case(rebound=False):
 with tempfile.TemporaryDirectory() as t:
  root=Path(t);(root/'fabro/storage').mkdir(parents=True);lock=root/'fabro/storage/server.lock'
  code="import os,sys,time;f=open(sys.argv[1],'w');os.dup2(f.fileno(),9);print('READY',flush=True);time.sleep(60)"
  p=subprocess.Popen([sys.executable,'-c',code,str(lock)],stdout=subprocess.PIPE,text=True)
  old=M.L
  try:
   assert p.stdout.readline().strip()=='READY';v=lock.stat();r=object.__new__(M.Runtime);r.exp={'processes':{'fabro':{'kernel':{'pid':p.pid}}},'server_lock_file':{'device':v.st_dev,'inode':v.st_ino,'uid':v.st_uid}};M.L=root
   if rebound:lock.rename(root/'old.lock');lock.write_bytes(b'REBOUND');refuses(r.fd_context,'FABRO_LOCK_FD_CONTEXT_CHANGED')
   else:r.fd_context()
  finally:M.L=old;p.terminate();p.communicate(timeout=3)
control('actual_Fabro_FD9_serverlock_context_positive',fd_case)
control('actual_Fabro_FD9_path_replacement_refused',lambda:fd_case(True))

def protected_origin_case(change=None):
 with tempfile.TemporaryDirectory() as t:
  root=Path(t);record_path=root/'record.json';dbpath=root/'state.db';c=sqlite3.connect(dbpath);c.row_factory=sqlite3.Row;c.execute('CREATE TABLE afo_independent_decisions(decision_id TEXT,kind TEXT,record TEXT,sha256 TEXT)')
  refs=[]
  for name in ['control','runtime','line']:
   p=root/name;p.write_bytes(b'PRIVATE_BOUND_INPUT');refs.append({'path':str(p),'sha256':M.sha(p)})
  st=dbpath.stat();record={'guardian_pid':(os.getpid() if change=='live_issuer' else 2147483647),'guardian':{'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':M.identity(os.getpid())['start_ticks']},'store_identity':{'device':st.st_dev,'inode':st.st_ino},'control_ref':refs[0],'runtime_policy_ref':refs[1],'line_policy_ref':refs[2]}
  ref=M.digest(record);record_path.write_bytes(M.canonical(record));record_path.chmod(0o600)
  intent={'record_sha256':ref};result={'status':'UNKNOWN_REQUIRES_RECONCILIATION','no_retry':True}
  r=object.__new__(M.Runtime);r.record=record;r.queue=dbpath;r.old_key='owner-profile-bootstrap-'+ref;r.exp={'old_intent_sha256':M.digest(intent),'old_result_sha256':M.digest(result),'historical_rows':[]};r.D=SimpleNamespace(MODE='OWNER_SUPERVISED_DEVELOPMENT',guardian_alive=lambda _:change=='live_issuer')
  for key,kind,value in [('owner-development-'+ref,r.D.MODE,record),(r.old_key,'OWNER_PROFILE_BOOTSTRAP_INTENT',intent),(r.old_key+'-result','OWNER_PROFILE_BOOTSTRAP_RESULT',result)]:c.execute('INSERT INTO afo_independent_decisions VALUES(?,?,?,?)',(key,kind,M.canonical(value).decode(),M.digest(value)))
  if change=='row':c.execute("UPDATE afo_independent_decisions SET sha256=? WHERE kind='OWNER_PROFILE_BOOTSTRAP_RESULT'",('0'*64,))
  if change=='file':record_path.write_bytes(b'PRIVATE_FORGED')
  if change=='private_mode':record_path.chmod(0o640)
  c.commit();old_record,old_ref=M.RECORD,M.REF;M.RECORD,M.REF=record_path,ref
  try:
   if change:refuses(lambda:r.authenticated_dead_origin(c),{'row':'ORIGINAL_ISSUANCE_OR_UNKNOWN_CHANGED','file':'OLD_ISSUER_CONTEXT_CHANGED','private_mode':'PRIVATE_OWNER_CONTEXT_REQUIRED','live_issuer':'ORIGINAL_ISSUER_LIFETIME_STILL_LIVE'}[change])
   else:r.authenticated_dead_origin(c)
  finally:M.RECORD,M.REF=old_record,old_ref;c.close()
control('actual_private_owner_file_and_SQL_dead_origin_hashbinding_positive',protected_origin_case)
for change in ['row','file','private_mode','live_issuer']:control('actual_private_origin_refuses_'+change,lambda change=change:protected_origin_case(change))

def strict_dead_origin_case(change=None):
 record={'guardian_pid':os.getpid(),'guardian':{'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'start_ticks':M.identity(os.getpid())['start_ticks']}}
 if change=='absent':record['guardian_pid']=2147483647;M.require_original_issuer_ended(record)
 elif change=='reused':record['guardian']['start_ticks']='1';M.require_original_issuer_ended(record)
 elif change=='unknown':
  with patch.object(M,'identity',side_effect=PermissionError(13,'PRIVATE_PROC_DENIED')):
   try:M.require_original_issuer_ended(record)
   except PermissionError:pass
   else:raise AssertionError('UNKNOWN_WAS_DEAD')
 else:refuses(lambda:M.require_original_issuer_ended(record),'ORIGINAL_ISSUER_LIFETIME_STILL_LIVE')
control('strict_dead_origin_actual_absent_positive',lambda:strict_dead_origin_case('absent'))
control('strict_dead_origin_original_PID_start_ended_positive',lambda:strict_dead_origin_case('reused'))
control('strict_dead_origin_actual_same_original_live_refused',strict_dead_origin_case)
control('strict_dead_origin_unreadable_PROC_remains_UNKNOWN',lambda:strict_dead_origin_case('unknown'))
def final_tail_after_history_case(change):
 p=subprocess.Popen([sys.executable,'-c',"import time;print('READY',flush=True);time.sleep(60)"],stdout=subprocess.PIPE,text=True)
 try:
  assert p.stdout.readline().strip()=='READY';r=object.__new__(M.Runtime);r.exp={'processes':{'fabro':{'kernel':M.identity(p.pid)}}};r.retired=set();r.actions=[];r.pidfd=pidfd;live=[True]
  r.guard=lambda stage:live.__setitem__(0,False)
  def tail():
   if not live[0]:raise RuntimeError('PRIVATE_'+change+'_AFTER_HEAVY_HISTORY')
  r.tail=tail
  refuses(lambda:r.signal('fabro',signal.SIGTERM),'PRIVATE_'+change+'_AFTER_HEAVY_HISTORY');assert p.poll() is None and r.actions==[]
 finally:p.terminate();p.communicate(timeout=3)
for change in ['EXPIRY','ORIGIN_CHANGED']:control('actual_Runtime_signal_final_fence_'+change,lambda change=change:final_tail_after_history_case(change))

def wrong_kernel_case(field):
 p=subprocess.Popen([sys.executable,'-c',"import time;print('READY',flush=True);time.sleep(60)"],stdout=subprocess.PIPE,text=True)
 try:
  assert p.stdout.readline().strip()=='READY';expected=M.identity(p.pid)
  if field=='uid':expected['uid']+=1
  else:expected['start_ticks']='1'
  r=object.__new__(M.Runtime);r.exp={'processes':{'fabro':{'kernel':expected}}};r.retired=set();r.actions=[];r.pidfd=pidfd;r.guard=lambda stage:None;r.tail=lambda:None
  refuses(lambda:r.signal('fabro',signal.SIGTERM),'EXACT_LIFETIME_REBOUND');assert p.poll() is None and not r.actions
 finally:p.terminate();p.communicate(timeout=3)
for field in ['uid','start']:control('actual_Runtime_signal_wrong_'+field,lambda field=field:wrong_kernel_case(field))

def independent_history_case(mutation=None):
 with tempfile.TemporaryDirectory() as temp:
  db=Path(temp)/'private.db'
  with sqlite3.connect(db) as c:
   c.execute('CREATE TABLE afo_independent_decisions(decision_id TEXT PRIMARY KEY,kind TEXT,record TEXT,sha256 TEXT)')
   c.execute("INSERT INTO afo_independent_decisions VALUES('owner-development-original','OWNER_SUPERVISED_DEVELOPMENT','PRIVATE_ORIGINAL','digest')")
  r=object.__new__(M.Runtime);r.queue=db;r.M=OLD;r.decisions_before=r.decisions()
  if mutation:
   with sqlite3.connect(db) as c:
    if mutation=='delete':c.execute("DELETE FROM afo_independent_decisions")
    elif mutation=='update':c.execute("UPDATE afo_independent_decisions SET record='PRIVATE_REBOUND'")
    else:c.execute("INSERT INTO afo_independent_decisions VALUES('extra','PRIVATE','value','sha')")
   refuses(r.require_decisions_unchanged,'INDEPENDENT_HISTORY_CHANGED')
  else:r.require_decisions_unchanged()
control('actual_private_whole_independent_history_unchanged_positive',independent_history_case)
for mutation in ['delete','update','append']:control('whole_independent_history_refuses_'+mutation,lambda mutation=mutation:independent_history_case(mutation))

def final_receipt_case(change=None):
 with tempfile.TemporaryDirectory() as temp:
  root=Path(temp);(root/'run').mkdir();(root/'run/services.json').write_bytes(b'PRIVATE_SERVICES_UNCHANGED');audit=root/'audit';audit.mkdir(mode=0o700)
  r=object.__new__(M.Runtime);r.native_before={'PRIVATE_NATIVE':'UNCHANGED'};r.ledger_before={'PRIVATE_LEDGER':'UNCHANGED'};r.decisions_before={'PRIVATE_ISSUER_AND_ACK':'UNCHANGED'};r.H=SimpleNamespace(native_checkpoint=lambda _:r.native_before);r.ledger=lambda:r.ledger_before;r.guard=lambda _:None;r.tail=lambda:None;r.provider=SimpleNamespace(owner_view=lambda _:{'observer_uid':os.getuid()});r.actions=[];r.services=b'PRIVATE_SERVICES_UNCHANGED';r.old_key='PRIVATE_OLD_KEY';r.queue=root/'PRIVATE.db';r.next_source='f0c8fc5c8ae83952a05cea578d41e0ff06324afd';r.evidence_dir=root/'evidence';r.evidence=r.evidence_dir/'PRIVATE-NOT-AUTHORITY.json'
  r.record={'source_revisions':['a'*40],'control_ref':{'PRIVATE':'NOT_REAL_AUTHORITY'},'profile':'PRIVATE','profile_sha256':'a'*64,'mission':{'PRIVATE':'UNACCEPTED'},'store_identity':{'device':1,'inode':2},'intent_epoch':1}
  r.exp={'boot_id':'PRIVATE_BOOT','old_intent_sha256':'b'*64,'old_result_sha256':'c'*64,'processes':{'holder':{'kernel':{'pid':2147483647,'start_ticks':'1'},'namespace':{'ns/user':'user:[1]','ns/net':'net:[2]','ns/pid':'pid:[3]'},'uid_map':[[0,1000,1]]}},'unit':{'InvocationID':'d'*32}}
  delta=[0];mono=time.monotonic;boot=time.clock_gettime
  def final_decisions():
   if change=='mutation':return {'PRIVATE_ISSUER_AND_ACK':'REBOUND'}
   if change=='time':delta[0]=61
   return r.decisions_before
  r.decisions=final_decisions
  clock=SimpleNamespace(monotonic=lambda:mono()+delta[0],clock_gettime=lambda c:boot(c)+delta[0],CLOCK_BOOTTIME=time.CLOCK_BOOTTIME)
  with patch.object(M,'L',root),patch.object(M,'AUDIT',audit),patch.object(M,'time',clock):
   if change:
    refuses(r.verify_and_emit,'INDEPENDENT_HISTORY_CHANGED' if change=='mutation' else 'FINAL_EVIDENCE_FRESHNESS_UNKNOWN_NO_RETRY')
    assert not(audit/'verified-result.json').exists()
   else:
    r.verify_and_emit();v=json.loads((audit/'verified-result.json').read_text());assert v['all_independent_decisions_unchanged'] and v['independent_decisions_before']==v['independent_decisions_after']
  assert (root/'run/services.json').read_bytes()==b'PRIVATE_SERVICES_UNCHANGED'
control('actual_verify_final_independent_snapshot_equal_positive',final_receipt_case)
for mutation in ['mutation','time']:control('final_verify_refuses_'+mutation+'_during_last_history_snapshot',lambda mutation=mutation:final_receipt_case(mutation))

report={'schema':'forge-c/exact642-cleanup-private-controls/1','PASS':sum(v['PASS'] for v in results),'FAIL':sum(not v['PASS'] for v in results),'results':results,'no_canonical_remote_or_owner_record_changes':True,'actual_models_or_GPU_calls':0,'fixture_overlays':'Private authority/history/resource/Intent leaves; actual harmless five-process unshare/holder graph, Runtime.signal/pidfd TERM+plannedKILL/naturalwaiter, SQL/resource predicates, process/FD/protectedfile/hash and final-fence controls. No live-owner authority/complete-production-admission claim.','no_D_current_or_new_authority':True,'all_private_handles_closed':True}
with(HERE/'private-controls-r1.json').open('x') as f:json.dump(report,f,sort_keys=True,indent=2)
print(json.dumps(report));raise SystemExit(bool(report['FAIL']))
