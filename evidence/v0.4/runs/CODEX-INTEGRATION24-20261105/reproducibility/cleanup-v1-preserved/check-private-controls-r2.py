"""Private harmless PID graph + SQL/hash/FD controls. No canonical data or services."""
import copy,importlib.util,json,os,signal,sqlite3,subprocess,sys,tempfile,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;P=HERE/'cleanup-exact-partial-bootstrap.py'
s=importlib.util.spec_from_file_location('cleanup',P);M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
V9=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/ops/scratch/owner-development-legacy-retirement-v9/retire-legacy-v9-DRAFT.py');s=importlib.util.spec_from_file_location('old',V9);OLD=importlib.util.module_from_spec(s);s.loader.exec_module(OLD)
SOURCE=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-owner-profile-bootstrap-v4');sys.path.insert(0,str(SOURCE/'factory/python'))
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
  root=Path(t);(root/'holder.pid').write_text('PRIVATE');(root/'history').write_bytes(b'PRIVATE_HISTORY');(root/'unknown').write_bytes(b'PRIVATE_UNKNOWN_IMMUTABLE')
  ignore=change=='stall'
  child="import os,sys,signal,time;signal.signal(signal.SIGTERM,"+('signal.SIG_IGN' if ignore else 'signal.SIG_DFL')+");print(os.getpid(),flush=True);time.sleep(60)"
  waiter=subprocess.Popen(['unshare','--user','--map-root-user','--net','--fork',sys.executable,'-c',child],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  holder=int(waiter.stdout.readline())
  fabrocode="import os,sys,time;f=open(sys.argv[1],'w');os.dup2(f.fileno(),9);print('READY',flush=True);time.sleep(60)"
  fabro=subprocess.Popen(['nsenter','-t',str(holder),'-U','-n','--preserve-credentials',sys.executable,'-c',fabrocode,str(root/'server.lock')],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  extra=None
  try:
   assert fabro.stdout.readline().strip()=='READY'
   r=object.__new__(M.Runtime);r.exp={'processes':{n:{'kernel':M.identity(p)} for n,p in [('fabro',fabro.pid),('holder',holder),('waiter',waiter.pid)]}}
   r.pidfd=pidfd;r.actions=[];r.retired=set();r.deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+(0.25 if ignore else 20)
   before={n:(root/n).read_bytes() for n in ['history','unknown']};counters={'attempts':1,'charged_tokens':1048576,'usage_unknown':True};original=copy.deepcopy(counters)
   for wrong in ['pid','start','uid','ppid']:
    expected=dict(r.exp['processes']['fabro']['kernel']);expected[{'pid':'pid','start':'start_ticks','uid':'uid','ppid':'ppid'}[wrong]]=999999
    refuses(lambda expected=expected:M.check_lifetime(expected,M.identity(fabro.pid)),'EXACT_LIFETIME_REBOUND')
   def guard(stage):
    assert counters==original and all((root/n).read_bytes()==v for n,v in before.items())
    if change=='active':raise RuntimeError('PRIVATE_ACTIVE_NATIVE_OR_REQUEST')
    if change=='unknown':raise RuntimeError('PRIVATE_UNKNOWN_OCCUPANT')
    if change=='fd':raise RuntimeError('PRIVATE_WRONG_FD_CONTEXT')
    for n,item in r.exp['processes'].items():
     if n not in r.retired:M.check_lifetime(item['kernel'],M.identity(item['kernel']['pid']))
    if stage=='all_quiet':assert all(M.quiet(v['kernel']) for v in r.exp['processes'].values())
   r.guard=guard
   def tail():
    assert time.clock_gettime(time.CLOCK_BOOTTIME)<r.deadline
    if change=='intent':raise RuntimeError('PRIVATE_INTENT_STOP')
   r.tail=tail
   r.remove_holder_file=lambda:(root/'holder.pid').unlink()
   r.verify_and_emit=lambda:None
   if change in ['active','unknown','fd','intent']:
    refuses(lambda:M.reap(r),{'active':'PRIVATE_ACTIVE_NATIVE_OR_REQUEST','unknown':'PRIVATE_UNKNOWN_OCCUPANT','fd':'PRIVATE_WRONG_FD_CONTEXT','intent':'PRIVATE_INTENT_STOP'}[change]);assert r.actions==[]
   elif ignore:
    refuses(lambda:M.reap(r),'PARTIAL_QUIESCENCE_UNKNOWN_NO_RETRY_NO_ESCALATION')
    assert [v['name'] for v in r.actions]==['fabro','holder'] and all(v['signal']=='SIGTERM' for v in r.actions)
    assert M.identity(holder)['state']!='Z' and waiter.poll() is None and (root/'holder.pid').exists()
   else:
    M.reap(r);assert [a['name'] for a in r.actions]==['fabro','holder'];assert all(a['signal']=='SIGTERM' for a in r.actions);assert not(root/'holder.pid').exists();assert all(M.quiet(v['kernel']) for v in r.exp['processes'].values())
   assert counters==original and all((root/n).read_bytes()==v for n,v in before.items())
   refuses(lambda:M.Runtime.signal(r,'waiter',signal.SIGTERM),'ONLY_EXACT_TERM_ALLOWED')
   refuses(lambda:M.Runtime.signal(r,'holder',signal.SIGKILL),'ONLY_EXACT_TERM_ALLOWED')
  finally:
   # Explicit harmless CONTROL teardown after tested API returned; never production escalation.
   if fabro.poll() is None:fabro.terminate()
   fabro.communicate(timeout=3)
   remaining=M.identity(holder)
   if remaining is not None and remaining['state']!='Z':os.kill(holder,signal.SIGKILL)
   waiter.communicate(timeout=3)
control('actual_sameNET_private_Fabro_holder_waiter_2TERM_natural_exit_preserves_unknown_and_charge',actual_graph)
for ch in ['active','unknown','fd','intent','stall']:control('actual_private_graph_refuses_'+ch,lambda ch=ch:actual_graph(ch))

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
  st=dbpath.stat();record={'store_identity':{'device':st.st_dev,'inode':st.st_ino},'control_ref':refs[0],'runtime_policy_ref':refs[1],'line_policy_ref':refs[2]}
  ref=M.digest(record);record_path.write_bytes(M.canonical(record));record_path.chmod(0o600)
  intent={'record_sha256':ref};result={'status':'UNKNOWN_REQUIRES_RECONCILIATION','no_retry':True}
  r=object.__new__(M.Runtime);r.record=record;r.queue=dbpath;r.old_key='owner-profile-bootstrap-'+ref;r.exp={'old_intent_sha256':M.digest(intent),'old_result_sha256':M.digest(result)};r.D=SimpleNamespace(MODE='OWNER_SUPERVISED_DEVELOPMENT',guardian_alive=lambda _:change=='live_issuer')
  for key,kind,value in [('owner-development-'+ref,r.D.MODE,record),(r.old_key,'OWNER_PROFILE_BOOTSTRAP_INTENT',intent),(r.old_key+'-result','OWNER_PROFILE_BOOTSTRAP_RESULT',result)]:c.execute('INSERT INTO afo_independent_decisions VALUES(?,?,?,?)',(key,kind,M.canonical(value).decode(),M.digest(value)))
  if change=='row':c.execute("UPDATE afo_independent_decisions SET sha256=? WHERE kind='OWNER_PROFILE_BOOTSTRAP_RESULT'",('0'*64,))
  if change=='file':record_path.write_bytes(b'PRIVATE_FORGED')
  if change=='private_mode':record_path.chmod(0o640)
  c.commit();old_record,old_ref=M.RECORD,M.REF;M.RECORD,M.REF=record_path,ref
  try:
   if change:refuses(lambda:r.authenticated_dead_origin(c),{'row':'ORIGINAL_ISSUANCE_OR_UNKNOWN_CHANGED','file':'OLD_ISSUER_CONTEXT_CHANGED','private_mode':'PRIVATE_OWNER_CONTEXT_REQUIRED','live_issuer':'OLD_ISSUER_CONTEXT_CHANGED'}[change])
   else:r.authenticated_dead_origin(c)
  finally:M.RECORD,M.REF=old_record,old_ref;c.close()
control('actual_private_owner_file_and_SQL_dead_origin_hashbinding_positive',protected_origin_case)
for change in ['row','file','private_mode','live_issuer']:control('actual_private_origin_refuses_'+change,lambda change=change:protected_origin_case(change))

report={'schema':'forge-c/partial-bootstrap-cleanup-private-controls/1','PASS':sum(v['PASS'] for v in results),'FAIL':sum(not v['PASS'] for v in results),'results':results,'no_canonical_remote_or_owner_record_changes':True,'actual_models_or_GPU_calls':0,'fixture_overlays':'Private authority/history/resource/Intent leaves for harmless sameNET PID graph; actual Runtime.signal, pidfd APIs, TERM/quiet sequencing executed. Normal SQL/resource primitives separately actual-private tested; no live owner authority claim.','no_D_current_or_new_authority':True,'all_private_handles_closed':True}
with(HERE/'private-controls-r2.json').open('x') as f:json.dump(report,f,sort_keys=True,indent=2)
print(json.dumps(report));raise SystemExit(bool(report['FAIL']))
