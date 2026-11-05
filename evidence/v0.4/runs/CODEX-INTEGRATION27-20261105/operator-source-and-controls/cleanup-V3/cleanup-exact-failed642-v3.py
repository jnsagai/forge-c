"""Exact stop-only OS-owner reconciliation after issuer loss; default PLAN_ONLY.

Never calls D.current, issues authority, changes old UNKNOWN or starts work.
"""
import argparse,contextlib,fcntl,hashlib,importlib.util,json,os,re,signal,sqlite3,stat,subprocess,sys,time
from pathlib import Path
F=Path('/mnt/data/forge-c/swe1-fabro-20261031');L=F/'lrtx'
OLD=F/'qualification/owner-development-dc27abba-review-20261105'
R=F/'qualification/owner-profile-bootstrap-88782030-review-20261105';S=R/'newS'
AUDIT=R/'partial-reconciliation-642-f0-r1';INTENT=Path('/home/omniverse2/.config/forge-c/line-local/operations-intent.json')
REF='642087d2cfe25034eb54cfc96185b9703d8da1f5314666911eba3f42567aa04f'
RECORD=INTENT.parent/'owner-supervised-development'/(REF+'.json')
UNIT='forge-c-owner-development-88782030-20261105.service'
V9=OLD/'owner-bootstrap-ops/retire-legacy-v9-DRAFT.py'
V9_SHA='54d75f613cce2c72fff4291f3cc0281d2419b1317e08871efa8ae21267aa95b5'
EXPECT_SHA='95ad72cc87510751a6f64304cfa809c2872001d2520b63f0abe9faf3ae1b3c6f'
TERMINAL={'succeeded','failed','cancelled','canceled'}

def require(ok,code):
 if not ok:raise RuntimeError(code)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
def digest(v):return hashlib.sha256(canonical(v)).hexdigest()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def private(path,directory=False):
 s=path.lstat();require(not path.is_symlink() and s.st_uid==1000 and not s.st_mode&0o077 and stat.S_ISDIR(s.st_mode)==directory,'PRIVATE_OWNER_CONTEXT_REQUIRED')
def write_new(path,value):
 with path.open('x') as f:os.fchmod(f.fileno(),0o600);json.dump(value,f,sort_keys=True,indent=2);f.flush();os.fsync(f.fileno())
def identity(pid):
 try:
  p=Path('/proc')/str(pid);s=(p/'stat').read_text();v=s[s.rfind(')')+2:].split()
  return dict(pid=pid,ppid=int(v[1]),start_ticks=v[19],state=v[0],uid=p.stat().st_uid)
 except FileNotFoundError:return None

def check_lifetime(expected,current):
 require(current is not None and current.get('state') in ['R','S','D','I'] and all(current.get(k)==v for k,v in expected.items() if k!='state'),'EXACT_LIFETIME_REBOUND')
def quiet(item):
 now=identity(item['pid']);return now is None or now['start_ticks']!=item['start_ticks'] or now['state']=='Z'


def require_original_issuer_ended(record):
 """An unreadable kernel fact raises; False attestation never proves death."""
 now=identity(record['guardian_pid'])
 boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
 require(now is None or boot!=record['guardian']['boot_id']
         or now['start_ticks']!=record['guardian']['start_ticks'] or now['state']=='Z',
         'ORIGINAL_ISSUER_LIFETIME_STILL_LIVE')

def require_holder_term_ignored(pid):
 status=dict(line.split(':',1) for line in Path(f'/proc/{pid}/status').read_text().splitlines() if ':' in line)
 require(int(status['SigIgn'].strip(),16)&(1<<(signal.SIGTERM-1)) and int(status['SigBlk'].strip(),16)==0 and int(status['SigCgt'].strip(),16)==0,'HOLDER_TERM_IGNORE_PROOF_CHANGED')

def reap(runtime):
 """Stop incoming delivery, retire Fabro, planned holder KILL; never signal waiter."""
 for name in ['bridge_outer','bridge_inner','fabro']:
  runtime.guard(name);runtime.signal(name,signal.SIGTERM);runtime.wait_quiet(name)
 runtime.guard('holder');runtime.signal('holder',signal.SIGKILL);runtime.wait_quiet('holder')
 runtime.wait_quiet('waiter');runtime.guard('all_quiet')
 runtime.remove_holder_file();runtime.verify_and_emit()

class Runtime:
 def __init__(self,next_source):
  require(__debug__ and os.getuid()==1000,'INITIAL_OS_OWNER_REQUIRED')
  require(not any(os.environ.get(k) for k in ['FORGE_AGENT_ROLE','FORGE_WORKSPACE','FORGE_POLICY_BINDING']),'EXTERNAL_OPERATOR_REQUIRED')
  require([list(map(int,x.split())) for x in Path('/proc/self/uid_map').read_text().splitlines()]==[[0,0,4294967295]],'INITIAL_OS_OWNER_REQUIRED')
  require(next_source=='f0c8fc5c8ae83952a05cea578d41e0ff06324afd','REVIEWED_NEXT_SOURCE_REQUIRED');self.next_source=next_source
  p=Path(__file__).parent/'exact-642-expectation-v2.json';require(not p.is_symlink() and sha(p)==EXPECT_SHA,'EXPECTATION_REBOUND');self.exp=json.loads(p.read_text())
  require(subprocess.check_output(['git','-C',str(S),'rev-parse','HEAD'],text=True).strip()==self.exp['source_revision'] and not subprocess.check_output(['git','-C',str(S),'status','--porcelain']),'FAILED_SOURCE_REBOUND')
  require(sha(V9)==V9_SHA and not V9.is_symlink(),'HISTORY_KERNEL_HELPER_REBOUND')
  spec=importlib.util.spec_from_file_location('retirement',V9);self.M=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.M)
  sys.path.insert(0,str(S/'factory/python'))
  from forge_factory.afo import owner_supervised_development as D,operations,line_launcher as LL,owner_bootstrap_history as H
  from forge_factory.lrtx import pidfd,provider_process
  self.D,self.LL,self.H,self.pidfd,self.provider=D,LL,H,pidfd,provider_process
  self.intent=operations.Intent(INTENT);self.cfg=LL.LineConfig.from_env();require(self.cfg.stack_root.resolve()==L,'CANONICAL_ROOT_REQUIRED')
  self.queue=L/'state/supervisor/line-queue.sqlite3';self.deadline=time.clock_gettime(time.CLOCK_BOOTTIME)+90;self.retired=set();self.actions=[];self.act_fd=None
  private(INTENT.parent,True);private(RECORD.parent,True);private(RECORD);require(sha(RECORD)==REF,'FAILED_RECORD_CHANGED');self.record=json.loads(RECORD.read_bytes())
  require(digest(self.record)==REF and self.record['schema']==D.SCHEMA and self.record['mode']==D.MODE and self.record['qualification_only'] is True and self.record['acceptance']=='UNACCEPTED' and self.record['directive_sha256']==D.digest(dict(external_directive=D.DIRECTIVE)),'FAILED_RECORD_INVALID')
  require(self.record['source_revisions']==[self.exp['source_revision']] and self.record['profile']==D.PROFILE and self.record['profile_sha256']==D.PROFILE_SHA and self.record['order_ids']==list(D.ORDERS),'ORIGINAL_SCOPE_REBOUND')
  require(self.record['mission']['mission_id']==D.MISSION and self.record['mission']['lineage']==D.LINEAGE and all(self.record['mission']['limits'].get(k)==v for k,v in D.CAPS.items()) and self.record['mission']['limits']['deadline']==D.DEADLINE,'MISSION_ENVELOPE_REBOUND')
  require(self.record['store_path']==str(self.queue),'CANONICAL_STORE_REBOUND');self.old_key='owner-profile-bootstrap-'+REF
  self.producer=json.loads((V9.parent/'inactive-history-expectation.json').read_bytes());require(sha(V9.parent/'inactive-history-expectation.json')==self.exp['producer_expectation_sha256'],'PRODUCER_EXPECTATION_REBOUND')
  self.services=(L/'run/services.json').read_bytes();require(sha(L/'run/services.json')==self.exp['services']['sha256'],'STOPPED_SERVICES_CHANGED')
  self.native_before=self.H.native_checkpoint(L);require({k:v for k,v in self.native_before.items() if k!='inventory'}==self.exp['native_snapshot'],'NATIVE_HISTORY_CHANGED')
  self.ledger_before=self.ledger();require(self.ledger_before==self.exp['ledger_checkpoint'],'LEDGER_HISTORY_CHANGED')
  self.decisions_before=self.decisions();require(self.decisions_before=={'afo_independent_decisions':self.exp['queue_snapshot']['afo_independent_decisions']},'INDEPENDENT_HISTORY_CHANGED')
  self.anchor_fd=self.M.open_proc_net_entry(self.exp['processes']['holder']['kernel']['pid']);self.anchor=self.M.proc_entry_identity(self.anchor_fd)
  self.evidence_dir=INTENT.parent/'owner-bootstrap-reconciliation';self.evidence=self.evidence_dir/('cleanup-'+REF+'-'+next_source+'.json')
  require(not AUDIT.exists() and not AUDIT.is_symlink() and not self.evidence.exists() and not self.evidence.is_symlink(),'ALREADY_ATTEMPTED_NO_RETRY')
 def ledger(self):return {k:v for k,v in self.M.table_hashes(self.queue).items() if k!='afo_independent_decisions'}
 def decisions(self):return self.M.table_hashes(self.queue,('afo_independent_decisions',))
 def require_decisions_unchanged(self):require(self.decisions()==self.decisions_before,'INDEPENDENT_HISTORY_CHANGED')
 def db(self):
  c=sqlite3.connect(self.queue.as_uri()+'?mode=ro',uri=True,timeout=3);c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON');c.execute('BEGIN');return c
 @contextlib.contextmanager
 def act_lock(self):
  path=L/'state/supervisor/act.lock';fd=os.open(path,os.O_RDWR|os.O_CLOEXEC|os.O_NOFOLLOW)
  try:
   fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);self.act_fd=fd
   require((os.fstat(fd).st_dev,os.fstat(fd).st_ino)==(path.stat().st_dev,path.stat().st_ino) and self.LL.flock_holders(path)=={os.getpid()},'ACT_LOCK_UNPROVEN');yield
  finally:self.act_fd=None;os.close(fd)
 def unit(self):
  raw=subprocess.check_output(['systemctl','--user','show',UNIT,'--property=LoadState,ActiveState,MainPID,InvocationID'],text=True,timeout=3);v=dict(x.split('=',1) for x in raw.splitlines())
  require(v.get('MainPID')=='0' and ((v.get('LoadState')=='loaded' and v.get('ActiveState') in ['inactive','failed'] and v.get('InvocationID')==self.exp['unit']['InvocationID']) or (v.get('LoadState')=='not-found' and v.get('ActiveState')=='inactive' and v.get('InvocationID')=='')),'FAILED_UNIT_REBOUND');return v
 def authenticated_dead_origin(self,c):
  private(RECORD);require(sha(RECORD)==REF,'OLD_ISSUER_CONTEXT_CHANGED');require_original_issuer_ended(self.record)
  require(dict(device=self.queue.stat().st_dev,inode=self.queue.stat().st_ino)==self.record['store_identity'],'CANONICAL_STORE_REBOUND')
  for key,kind,expected in [('owner-development-'+REF,self.D.MODE,REF),(self.old_key,'OWNER_PROFILE_BOOTSTRAP_INTENT',self.exp['old_intent_sha256']),(self.old_key+'-result','OWNER_PROFILE_BOOTSTRAP_RESULT',self.exp['old_result_sha256'])]:
   row=c.execute('SELECT kind,record,sha256 FROM afo_independent_decisions WHERE decision_id=?',(key,)).fetchone();require(row is not None and row['kind']==kind and row['sha256']==expected and hashlib.sha256(row['record'].encode()).hexdigest()==expected,'ORIGINAL_ISSUANCE_OR_UNKNOWN_CHANGED')
   if kind==self.D.MODE:require(json.loads(row['record'])==self.record,'ISSUANCE_RECORD_REBOUND')
   if kind=='OWNER_PROFILE_BOOTSTRAP_RESULT':require(json.loads(row['record'])['status']=='UNKNOWN_REQUIRES_RECONCILIATION' and json.loads(row['record'])['no_retry'] is True,'UNKNOWN_RESULT_CHANGED')
  for old in self.exp['historical_rows']:
   row=c.execute('SELECT kind,record,sha256 FROM afo_independent_decisions WHERE decision_id=?',(old['decision_id'],)).fetchone();require(row and row['kind']==old['kind'] and row['sha256']==old['sha256'] and hashlib.sha256(row['record'].encode()).hexdigest()==old['raw_sha256'],'HISTORICAL_ACK_OR_UNKNOWN_CHANGED')
  for key in ['control_ref','runtime_policy_ref','line_policy_ref']:
   ref=self.record[key];require(sha(Path(ref['path']))==ref['sha256'],'ORIGINAL_BOUND_INPUT_CHANGED')
 def resources(self,c):
  require(c.execute("SELECT 1 FROM afo_resource_ownership WHERE holder IS NOT NULL AND holder!='' LIMIT 1").fetchone() is None,'RESOURCE_OWNER_BUSY')
  require(c.execute("SELECT 1 FROM afo_execution_liveness WHERE json_extract(record,'$.resource_lease')!='RELEASED' LIMIT 1").fetchone() is None,'EXECUTION_NOT_RELEASED')
  require(c.execute("SELECT 1 FROM afo_request_ledger WHERE state!='QUIESCENT' LIMIT 1").fetchone() is None,'REQUEST_NOT_QUIESCENT')
  require(c.execute("SELECT 1 FROM afo_work_orders WHERE state IN ('QUEUED','ADMITTED','RUNNING','WAITING_RECOVERY','VALIDATING') LIMIT 1").fetchone() is None,'ACTIVE_ORDER')
  require(c.execute("SELECT 1 FROM afo_commands_outbox WHERE state NOT IN ('ACKED','FAILED','QUARANTINED') LIMIT 1").fetchone() is None,'UNRESOLVED_COMMAND')
  orders=[dict(r) for r in c.execute("SELECT * FROM afo_work_orders WHERE state='PAUSED'")];old=self.producer
  ids=set(old['orders']);extra=[dict(c.execute('SELECT * FROM afo_work_orders WHERE order_id=?',(oid,)).fetchone()) for oid in ids if oid not in {r['order_id'] for r in orders}]
  attempts=[dict(c.execute('SELECT * FROM afo_attempts WHERE attempt_id=?',(aid,)).fetchone()) for aid in old['attempts']]
  commands=[dict(r) for r in c.execute("SELECT * FROM afo_commands_outbox WHERE state='FAILED'")]
  self.M.pinned_inactive_history(orders+extra,attempts,commands,old,self.record['order_ids'])
 def processes(self):
  for name,expected in self.exp['processes'].items():
   now=identity(expected['kernel']['pid'])
   if name in self.retired:
    require(quiet(expected['kernel']),'RETIRED_LIFETIME_ACTIVE');continue
   check_lifetime(expected['kernel'],now);p=Path('/proc')/str(now['pid'])
   require(os.readlink(p/'exe')==expected['exe'] and self.M.digest(self.M.kernel_argv_vector((p/'cmdline').read_bytes()))==expected['argv_sha256'],'PROCESS_EXE_OR_ARGV_REBOUND')
   require(all(os.readlink(p/k)==v for k,v in expected['namespace'].items()) and [list(map(int,x.split())) for x in (p/'uid_map').read_text().splitlines()]==expected['uid_map'] and (p/'cgroup').read_text().strip()==expected['cgroup'],'PROCESS_NAMESPACE_OR_SCOPE_REBOUND')
   require(sha(p/'environ')==expected['env_sha256'],'PROCESS_CONTEXT_REBOUND')
  if 'holder' not in self.retired:require(identity(self.exp['processes']['holder']['kernel']['pid'])['ppid']==self.exp['processes']['waiter']['kernel']['pid'],'HOLDER_WAITER_CHAIN_REBOUND');require_holder_term_ignored(self.exp['processes']['holder']['kernel']['pid'])
 def fd_context(self):
  pid=self.exp['processes']['fabro']['kernel']['pid'];p=Path('/proc')/str(pid)/'fd/9';target=L/'fabro/storage/server.lock'
  require(os.readlink(p)==str(target),'FABRO_LOCK_FD_CONTEXT_CHANGED')
  a,b=p.stat(),target.stat();want=self.exp['server_lock_file']
  require((a.st_dev,a.st_ino,a.st_uid)==(b.st_dev,b.st_ino,b.st_uid)==(want['device'],want['inode'],want['uid']),'FABRO_LOCK_FD_REBOUND')
 def census(self):
  known={v['kernel']['pid'] for v in self.exp['processes'].values()};parents={};seen=set()
  for p in Path('/proc').iterdir():
   if not p.name.isdigit():continue
   try:
    row=identity(int(p.name))
    if row is None:continue
    parents[row['pid']]=row['ppid']
    if row['uid']!=1000 or row['state']=='Z':continue
    fd=self.M.open_proc_net_entry(row['pid'])
    try:
     value=self.M.proc_entry_identity(fd);require(value[0]==self.anchor[0],'PROC_MOUNT_REBOUND')
     require(identity(row['pid'])==row,'CENSUS_PID_REBOUND')
     if value==self.anchor:seen.add(row['pid'])
    finally:os.close(fd)
   except FileNotFoundError:continue
  roots=set(known)
  for _ in range(len(parents)+1):
   more={p for p,parent in parents.items() if parent in roots}
   if more<=roots:break
   roots|=more
  for name,item in self.exp['processes'].items():
   pid=item['kernel']['pid'];now=identity(pid)
   if now is not None and now['state']!='Z':require(now['start_ticks']==item['kernel']['start_ticks'],'CENSUS_ORIGINAL_PID_REUSED')
  require(not ((seen|roots)-known),'UNKNOWN_NAMESPACE_OCCUPANT_OR_DESCENDANT')
  if len(self.retired)==5:require(not seen,'PARTIAL_NAMESPACE_NOT_QUIET')
 def guard(self,stage):
  require(time.clock_gettime(time.CLOCK_BOOTTIME)<self.deadline,'CLEANUP_TOTAL_BOUND_EXPIRED');require(self.act_fd is not None and self.LL.flock_holders(L/'state/supervisor/act.lock')=={os.getpid()},'ACT_LOCK_LOST')
  require(self.intent.read()==self.exp['Intent'],'INTENT_CHANGED');self.unit()
  with self.db() as c:self.authenticated_dead_origin(c);self.resources(c)
  # Original production observer remains exact and model-free. No live newworker.
  prod=self.producer['producers'][0];now=identity(int(prod['MainPID']));require(now is not None and now['start_ticks']==prod['start_ticks'] and sha(Path('/proc')/str(now['pid'])/'cmdline')==prod['argv_sha256'],'PRODUCTION_OBSERVER_REBOUND')
  require('--mode' in self.M.kernel_argv_vector((Path('/proc')/str(now['pid'])/'cmdline').read_bytes()) and 'OBSERVE' in self.M.kernel_argv_vector((Path('/proc')/str(now['pid'])/'cmdline').read_bytes()),'PRODUCTION_OBSERVER_NOT_OBSERVE')
  require(self.H.native_checkpoint(L)==self.native_before and self.ledger()==self.ledger_before,'HISTORY_OR_ACCOUNTING_CHANGED')
  require((L/'run/services.json').read_bytes()==self.services,'STOPPED_SERVICES_CHANGED')
  self.require_decisions_unchanged();self.processes();self.census()
  if 'fabro' not in self.retired:self.fd_context()
  else:require(not self.LL.flock_holders(L/'fabro/storage/server.lock'),'FABRO_FD_NOT_QUIET')
 def tail(self):
  require(self.intent.read()==self.exp['Intent'] and sha(RECORD)==REF,'STOP_ONLY_ORIGIN_OR_INTENT_CHANGED');require_original_issuer_ended(self.record)
  require(Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.exp['boot_id'],'BOOT_CHANGED')
  require(time.monotonic()<self.record['expiry_ticket']['deadline_monotonic'] and time.clock_gettime(time.CLOCK_BOOTTIME)<min(self.deadline,self.record['expiry_boottime_deadline']),'FINAL_EFFECT_WINDOW_EXPIRED')
 def signal(self,name,sig):
  require((name in ['bridge_outer','bridge_inner','fabro'] and sig==signal.SIGTERM) or (name=='holder' and sig==signal.SIGKILL and {'bridge_outer','bridge_inner','fabro'}<=self.retired),'ONLY_EXACT_PLANNED_SIGNAL_ALLOWED');expected=self.exp['processes'][name]['kernel'];fd=self.pidfd.open_pid(expected['pid'])
  try:
   self.guard(name);check_lifetime(expected,identity(expected['pid']));
   if name=='holder':require_holder_term_ignored(expected['pid'])
   self.tail();self.pidfd.send_signal(fd,sig);self.actions.append({'name':name,'pid':expected['pid'],'signal':signal.Signals(sig).name,'pidfd_owned':True})
  finally:os.close(fd)
 def wait_quiet(self,name):
  until=min(time.clock_gettime(time.CLOCK_BOOTTIME)+(10 if name=='fabro' else 3),self.deadline)
  item=self.exp['processes'][name]['kernel']
  while not quiet(item):
   require(time.clock_gettime(time.CLOCK_BOOTTIME)<until,'PARTIAL_QUIESCENCE_UNKNOWN_NO_RETRY_NO_ESCALATION');time.sleep(0.05)
  self.retired.add(name)
 def remove_holder_file(self):
  require(len(self.retired)==5,'ALL_ORIGINAL_LIFETIMES_MUST_BE_QUIET');self.guard('unlink')
  p=L/'run/holder.pid';expected=self.exp['holder_file'];st=p.lstat();require(not p.is_symlink() and st.st_uid==1000 and (st.st_dev,st.st_ino)==(expected['stat']['device'],expected['stat']['inode']) and sha(p)==expected['sha256'],'HOLDER_FILE_REBOUND')
  parent=os.open(L/'run',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
  try:self.tail();os.unlink('holder.pid',dir_fd=parent);self.actions.append({'holder_file_removed_after_all_quiet':True})
  finally:os.close(parent)
 def verify_and_emit(self):
  self.guard('verify');require(not (L/'run/holder.pid').exists(),'HOLDER_FILE_NOT_REMOVED')
  native=self.H.native_checkpoint(L);ledger=self.ledger();require(native==self.native_before and ledger==self.ledger_before,'HISTORY_CHANGED')
  self.tail()
  context={'boot_id':self.exp['boot_id'],**self.provider.owner_view(os.getpid())}
  evidence=dict(schema='forge-c/owner-bootstrap-cleanup-evidence/1',status='WHOLE_STACK_QUIET_HISTORY_CONSERVED',old_intent_id=self.old_key,bootstrap_nonce=self.old_key,old_intent_sha256=self.exp['old_intent_sha256'],old_result_sha256=self.exp['old_result_sha256'],old_record_sha256=REF,old_source_revisions=self.record['source_revisions'],old_control_ref=self.record['control_ref'],profile=self.record['profile'],profile_sha256=self.record['profile_sha256'],mission=self.record['mission'],store_path=str(self.queue),store_identity=self.record['store_identity'],intent_epoch=self.record['intent_epoch'],next_source_revisions=[self.next_source],owner_context=context,observed_monotonic=time.monotonic(),observed_boottime=time.clock_gettime(time.CLOCK_BOOTTIME),whole_stack_quiet=True,unknown_occupants=[],lifetimes=[{k:v['kernel'][k] for k in ['pid','start_ticks']}|{'boot_id':self.exp['boot_id']} for v in self.exp['processes'].values()],native_before=self.native_before,native_after=native,ledger_before=self.ledger_before,ledger_after=ledger,old_unit={'name':UNIT,'MainPID':'0','InvocationID':self.exp['unit']['InvocationID']},old_namespace={'user':self.exp['processes']['holder']['namespace']['ns/user'],'net':self.exp['processes']['holder']['namespace']['ns/net'],'pid':self.exp['processes']['holder']['namespace']['ns/pid'],'uid_map':self.exp['processes']['holder']['uid_map']},services_before_sha256=hashlib.sha256(self.services).hexdigest(),services_after_sha256=sha(L/'run/services.json'),holder_file_removed_after_quiet=True,old_lifetimes_fds_quiet=True,no_charge_reset_or_relabel=True)
  self.evidence_dir.mkdir(mode=0o700,exist_ok=True);private(self.evidence_dir,True)
  write_new(self.evidence,evidence)
  require(0<=time.monotonic()-evidence['observed_monotonic']<=60 and 0<=time.clock_gettime(time.CLOCK_BOOTTIME)-evidence['observed_boottime']<=60,'FINAL_EVIDENCE_FRESHNESS_UNKNOWN_NO_RETRY')
  final_decisions=self.decisions();require(final_decisions==self.decisions_before,'INDEPENDENT_HISTORY_CHANGED')
  self.tail()
  require(0<=time.monotonic()-evidence['observed_monotonic']<=60 and 0<=time.clock_gettime(time.CLOCK_BOOTTIME)-evidence['observed_boottime']<=60,'FINAL_EVIDENCE_FRESHNESS_UNKNOWN_NO_RETRY')
  result={'schema':'forge-c/partial-bootstrap-cleanup-result/1','status':'EXACT_PARTIAL_LIFETIMES_QUIET_HISTORY_CONSERVED','evidence_ref':{'path':str(self.evidence),'sha256':sha(self.evidence)},'actions':self.actions,'model_calls':0,'independent_decisions_before':self.decisions_before,'independent_decisions_after':final_decisions,'all_independent_decisions_unchanged':True,'old_UNKNOWN_unchanged':True,'no_charge_or_history_reset':True,'next_work_authority_issued':False,'evidence':evidence}
  write_new(AUDIT/'verified-result.json',result);print(json.dumps(result,sort_keys=True))

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply-reviewed',action='store_true');p.add_argument('--inspect-reviewed',action='store_true');p.add_argument('--next-source-revision');a=p.parse_args()
 require(not(a.apply_reviewed and a.inspect_reviewed),'ONE_MODE_REQUIRED')
 if not(a.apply_reviewed or a.inspect_reviewed):print(json.dumps({'status':'PLAN_ONLY_NOT_EXECUTED','effects':False,'scope':'ONLY exact failed642 bridgesTERM/FabroTERM then planned ignoredTERM holderKILL; waiter naturalquiet; no workauthority','audit':str(AUDIT)}));return
 r=Runtime(a.next_source_revision)
 try:
  with r.intent.lock(),r.LL.gpu_lock(r.cfg.gpu_lock),r.LL.held_stack_lock(L),r.act_lock():
   r.guard('initial')
   if a.inspect_reviewed:print(json.dumps({'status':'READONLY_READY_NOT_EXECUTED','effects':False,'exact_lifetimes':r.exp['processes']}));return
   AUDIT.mkdir(mode=0o700)
   write_new(AUDIT/'intent.json',{'schema':'forge-c/partial-bootstrap-stop-only-intent/1','failed_record_sha256':REF,'bootstrap_nonce':r.old_key,'source_revision':r.exp['source_revision'],'next_source_revision':r.next_source,'expectation_sha256':EXPECT_SHA,'helper_sha256':sha(Path(__file__)),'native_before':r.native_before,'ledger_before':r.ledger_before,'independent_decisions_before':r.decisions_before,'Intent':r.exp['Intent'],'exact_lifetimes':r.exp['processes'],'no_new_work_authority':True,'owner_context':r.provider.owner_view(os.getpid())})
   try:reap(r)
   except BaseException as e:write_new(AUDIT/'unknown-result.json',{'status':'UNKNOWN_NO_RETRY_NO_ESCALATION','error_type':type(e).__name__,'actions':r.actions,'old_UNKNOWN_unchanged':True});raise
 finally:os.close(r.anchor_fd)
if __name__=='__main__':main()
