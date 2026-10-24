#!/mnt/data/forge-c/venv/bin/python
"""Mission-only native evidence recorder; no model requests, shell text, or private input copying."""
import os,sys,json,time,hashlib,subprocess,sqlite3,signal
from pathlib import Path
from datetime import datetime,timezone
REPO=Path('/home/omniverse2/forge-c-remote/repos/forge-c-autonomy-36ed0fc')
STATE=Path('/mnt/data/forge-c/lrtx-v2/state')
OPS=STATE/'operator-runs/feature013-v4'
PROGRESS=Path('/home/omniverse2/forge-c-remote/repos/forge-c-overnight-review')
BRANCH='overnight/2026-10-24-qwen-omniverse2'
PIN='36ed0fc70bd8765f0cc90a45b21bbf02924b0269'
os.environ.update(FORGE_REPO_ROOT=str(REPO),FORGE_STATE_DIR=str(STATE),FORGE_DATA_ROOT='/mnt/data/forge-c/lrtx-v2',FORGE_ARCHIVE_DIR='/mnt/data/forge-c/lrtx-v2/archives')
sys.path.insert(0,str(REPO/'factory/python'))
from forge_factory.afo.dispatch import package_verdict
from forge_factory.inspection.engine import Store as Phases
stop=False
def stopping(*args):
 global stop
 stop=True
signal.signal(signal.SIGTERM,stopping)
signal.signal(signal.SIGINT,stopping)
def run(args,**kw):return subprocess.run(args,capture_output=True,text=True,timeout=30,**kw)
def git(*args):
 p=run(['git','-C',str(PROGRESS),*args])
 if p.returncode:raise RuntimeError('Git operation failed: '+args[0])
 return p.stdout.strip()
def digest(data):return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def dump(p,obj):
 temp=p.with_suffix('.tmp');temp.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n');os.replace(temp,p)
def read(p):
 try:return json.loads(p.read_text())
 except (OSError,ValueError):return {}
def snapshot():
 c=sqlite3.connect('file:'+str(STATE/'conductor/conductor.sqlite3')+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
 tables={r[0] for r in c.execute('SELECT name FROM sqlite_master WHERE type=\'table\'')}
 orders=[]
 for row in c.execute('SELECT order_id,request_id,state,terminal_reason,policy_sha256,authorization_id FROM afo_work_orders ORDER BY created_epoch'):
  o=dict(row);o['attempts']=[]
  for ar in c.execute('SELECT attempt_id,seq,state,record FROM afo_attempts WHERE order_id=? ORDER BY seq',(o['order_id'],)):
   a=dict(ar);rec=json.loads(a.pop('record'));a.update({k:rec.get(k) for k in ('workspace_ref','fabro_run_id','factory_revision','recovery_plan_id','exit_status','terminal_package_status')})
   ws=STATE/'workorders'/str(rec.get('workspace_ref','')).removeprefix('workorder:')/'workspace'
   if ws.is_dir():
    ps=Phases(ws);a['gates']={ph:ps.gate(ph).get('decision','UNKNOWN') for ph in ('SWE.1','SWE.2','SWE.3','SWE.4','SWE.5','SWE.6')}
    pkg=read(ws/'.forge-run/package.json');a['package']={k:pkg.get(k) for k in ('package_status','gap_count','archive_sha256','finalized_at')}
    if pkg:
     verdict=package_verdict(ws/'.forge-run/package.json');a['sealed_package_verdict']=verdict.get('verdict','UNKNOWN')
    a['native_success_verified']=a.get('sealed_package_verdict')=='READY_FOR_OFFLINE_REVIEW' and all(v=='PASS' for v in a['gates'].values())
   o['attempts'].append(a)
  orders.append(o)
 jobs=[]
 if 'afo_local_agent_jobs' in tables:
  cols=[r[1] for r in c.execute('PRAGMA table_info(afo_local_agent_jobs)')]
  keep=[k for k in ('job_id','role','order_id','attempt_id','state','fabro_run_id','failure_code','reserved_tokens','record') if k in cols]
  for row in c.execute('SELECT '+','.join(keep)+' FROM afo_local_agent_jobs'):
   j=dict(row)
   if 'record' in j:
    r=json.loads(j.pop('record'));j.update({k:r.get(k) for k in ('run_id','reason','proposal_id','review_state','reserved_tokens','reported_tokens','deadline_epoch') if k in r})
   jobs.append(j)
 plans=[]
 if 'afo_recovery_plans' in tables:
  plans=[dict(r) for r in c.execute('SELECT plan_id,order_id,attempt_id,strategy,source,status,reasons FROM afo_recovery_plans ORDER BY decided_utc')]
 proposals=[]
 if 'afo_maintainer_proposals' in tables:
  for r in c.execute('SELECT proposal_id,status,record FROM afo_maintainer_proposals ORDER BY seq'):
   p=dict(r);rec=json.loads(p.pop('record'));p.update({k:rec.get(k) for k in ('outcome','branch_ref','cre_promotion_id','candidate_commit')});proposals.append(p)
 c.close()
 hb=read(STATE/'afo/conductor.heartbeat')
 ready=any(a.get('native_success_verified') for o in orders if o['request_id'].startswith('q36c-local-selfheal') for a in o['attempts'])
 return dict(source_revision=PIN,policy_sha256=read(OPS/'activation.json').get('policy_sha256'),orders=orders,diagnosis_jobs=jobs,recovery_plans=plans,maintainer_proposals=proposals,conductor={'mode':hb.get('mode'),'ok':hb.get('ok'),'heartbeat_fresh':time.time()-hb.get('epoch',0)<90},next_driver={'selection':'STM32N6 GPIO LL','condition':'RCC all six native gates PASS and sealed READY archive verified','condition_met':ready,'submission':'BLOCKED_PENDING_PROFILE_AND_FROZEN_INPUTS' if ready else 'NOT_TRIGGERED'},inspector_download={k:v for k,v in read(Path('/mnt/data/forge-c/downloads/qwen3.8-27b-q8_0/status.json')).items() if k in ('state','model','manifest_sha256','total_bytes','inference_started')},exclusivity='Qwen mission only, plus owner-requested low-priority Qwen3.8 Q8 download for a later inspector test; no competing inference or trials')
def resources():
 mem={}
 for ln in Path('/proc/meminfo').read_text().splitlines():
  k,_,v=ln.partition(':')
  if k in ('MemTotal','MemAvailable'):mem[k]=v.strip()
 g=run(['nvidia-smi','--query-gpu=utilization.gpu,memory.used,memory.total,power.draw','--format=csv,noheader,nounits'])
 return dict(cpu_load_1_5_15=os.getloadavg(),memory=mem,gpu=g.stdout.strip() if g.returncode==0 else 'UNKNOWN',verification_workers_max=16)
if not PROGRESS.exists():
 p=run(['git','-C',str(REPO),'worktree','add','-b',BRANCH,str(PROGRESS),PIN]);assert p.returncode==0,'progress worktree creation failed'
git('config','user.name','Forge-C Mission Recorder');git('config','user.email','forge-c-mission@localhost')
out=PROGRESS/'evidence/013-local-autonomous-recovery/overnight-20261024';out.mkdir(parents=True,exist_ok=True)
handoff=OPS/'HANDOFF.md'
if handoff.exists():(out/'HANDOFF.md').write_text(handoff.read_text())
for name in ('activation.json','adoption.json','host-preflight.json'):
 p=OPS/name
 if p.exists():(out/name).write_bytes(p.read_bytes())
scripts=out/'operator-scripts';scripts.mkdir(exist_ok=True)
for name in ('feature013-progress-recorder.py','feature013-remote-exec.py','feature013-adopt-history.py','feature013-install-conductor.py','feature013-download-qwen38.py'):
 p=OPS/name
 if p.exists():(scripts/name).write_bytes(p.read_bytes())
lastkey=None;lastcommit=0;lastpush=0
while not stop:
 try:
  snap=snapshot();key=digest(snap);now=time.time();snap['captured_utc']=datetime.now(timezone.utc).isoformat();snap['resources']=resources()
  dump(OPS/'latest-progress.json',snap)
  if key!=lastkey or now-lastcommit>=900:
   dump(out/'progress.json',snap)
   with (out/'timeline.jsonl').open('a') as f:f.write(json.dumps({'captured_utc':snap['captured_utc'],'state_sha256':key,'orders':[{k:o[k] for k in ('order_id','state','terminal_reason')} for o in snap['orders']],'jobs':snap['diagnosis_jobs']},sort_keys=True)+'\n')
   git('add','--',str(out.relative_to(PROGRESS)))
   if run(['git','-C',str(PROGRESS),'diff','--cached','--quiet']).returncode!=0:
    git('commit','-m','Record Qwen mission native status '+snap['captured_utc'])
   lastkey=key;lastcommit=now
   dump(OPS/'recorder-status.json',dict(ok=True,branch=BRANCH,commit=git('rev-parse','HEAD'),captured_utc=snap['captured_utc'],worktree=str(PROGRESS)))
  if now-lastpush>=900:
   lastpush=now
   p=run(['git','-C',str(PROGRESS),'push','--set-upstream','origin',BRANCH],env={**os.environ,'GIT_TERMINAL_PROMPT':'0'})
   dump(OPS/'recorder-publish.json',dict(attempted_utc=snap['captured_utc'],published=p.returncode==0,branch=BRANCH,note='Remote local Git commits remain durable regardless of network credentials'))
 except Exception as e:
  dump(OPS/'recorder-error.json',dict(ok=False,error_type=type(e).__name__,detail=str(e)[:160],epoch=time.time()))
  print('recorder exception '+type(e).__name__,flush=True)
 for _ in range(60):
  if stop:break
  time.sleep(1)
