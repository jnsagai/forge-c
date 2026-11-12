"""Rebind the existing host-only observer, retaining Git history; no intake or model calls."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/aspice-rcc-role-split-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations
from forge_factory.afo.queue import Store
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.common import utc_now
s=json.loads((O/'scope.json').read_text());assert digest(s)=='7a3aa5041f60f51edd91a3458406fe463ff7b38a80de7c0a5550dfc028007533'
I=operations.Intent();assert I.read()['mode']=='RUNNING' and I.read()['epoch']==104
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==s['source_revision']
old=P/'progress-aspice-rcc-stepwise-20261030-v1';out=P/'progress-aspice-rcc-role-split-20261030-v1'
def git(root,*args,check=True):return subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,check=check,timeout=30)
assert not out.exists()
subprocess.run(['git','clone','--shared',str(old),str(out)],capture_output=True,check=True)
git(out,'remote','set-url','origin',git(old,'remote','get-url','origin').stdout.strip())
ssh=git(old,'config','--get','core.sshCommand',check=False)
if ssh.returncode==0:git(out,'config','core.sshCommand',ssh.stdout.strip())
git(out,'switch','-c','overnight/2026-10-30-aspice-role-split')
git(out,'config','user.name','Forge-C Mission Recorder');git(out,'config','user.email','forge-c-mission@localhost')
(out/'plans').mkdir(exist_ok=True);git(out,'mv','plan.json','plans/pre-role-split-observer.json');git(out,'commit','-m','Preserve previous finite observer plan before stepwise ASPICE trial')
orders=[{'order_id':s['ll']['order_id']}]
S=Store();assert all(S.order(e['order_id']) for e in orders)
plan={'schema':'forge-c/overnight-intake/1','source_revision':s['source_revision'],'started_epoch':int(time.time()),'progress_repo':str(out),'progress_branch':'overnight/2026-10-30-aspice-role-split','deadline_epoch':s['deadline_epoch'],'orders':orders,'claim':'OBSERVE_EXISTING_ORDER_ONLY_NO_INTAKE; blocking ASPICE gates; no accepted-product claim'}
immutable_json(O/'progress-plan-observer.json',plan)
wrapper=O/'run-observer-host.py'
raw="""from pathlib import Path
import os
p=Path('/mnt/data/forge-c/production-local-014')
env=dict(os.environ)
for line in (p/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);env[k]=v
env.update(PYTHONPATH=str(p/'repo/factory/python'),PYTHONDONTWRITEBYTECODE='1',GIT_TERMINAL_PROMPT='0')
py=str(p/'venv/bin/python')
os.execvpe(py,[py,'-m','forge_factory.afo.overnight',str(p/'deployment/aspice-rcc-role-split-20261030-v1/progress-plan-observer.json')],env)
"""
immutable_bytes(wrapper,raw.encode());unit=Path.home()/'.config/systemd/user/forge-qwen-mission-recorder.service';before=unit.read_bytes();immutable_bytes(O/'recorder-unit-before.txt',before)
lines=before.decode().splitlines();assert sum(l.startswith('ExecStart=') for l in lines)==1
new='\n'.join('ExecStart='+str(P/'venv/bin/python')+' '+str(wrapper) if l.startswith('ExecStart=') else l for l in lines)+'\n'
with I.lock():
 assert I.read()['mode']=='RUNNING' and I.read()['epoch']==104
 fd,tmp=tempfile.mkstemp(prefix='.qwen-observer-',dir=unit.parent)
 with os.fdopen(fd,'w') as f:f.write(new);f.flush();os.fsync(f.fileno())
 os.chmod(tmp,0o600);os.replace(tmp,unit)
 subprocess.run(['systemctl','--user','daemon-reload'],check=True,timeout=20);subprocess.run(['systemctl','--user','start','forge-qwen-mission-recorder.service'],check=True,timeout=20)
immutable_json(O/'recorder.json',{'status':'EXISTING_HOST_OBSERVER_REBOUND','source_revision':s['source_revision'],'progress_branch':plan['progress_branch'],'orders':[e['order_id'] for e in orders],'interval_seconds':300,'publication':'CHECK_GITHUB_BEFORE_CLAIMING','expiry_stops_factory':False,'new_scheduler':False,'model_requests':0,'at':utc_now()});print((O/'recorder.json').read_text())
