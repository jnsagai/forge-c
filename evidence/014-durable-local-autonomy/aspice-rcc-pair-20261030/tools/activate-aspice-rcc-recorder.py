"""Reuse the existing five-minute Git observer, with no pending intake or second scheduler."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/aspice-rcc-pair-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations
from forge_factory.afo.queue import Store
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.common import utc_now
s=json.loads((O/'scope.json').read_text());assert digest(s)=='3e60ba7507f085996b6ae838878a37f4bf5ae2d246fe4d4573c8ed137e519b47'
I=operations.Intent();assert I.read()['mode']=='RUNNING' and I.read()['epoch']==50
entry=json.loads((O/'entry.json').read_text());assert Store().order(entry['order_id'])
out=P/'progress-aspice-rcc-20261030-v1';old=P/'progress-afo-focused-20261029-v7'
def git(root,*args,check=True):return subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,check=check,timeout=25)
branch='overnight/2026-10-30-local-qwen-aspice'
out.mkdir(mode=0o700)
git(out,'init','-b',branch);git(out,'config','user.name','Forge-C Mission Recorder');git(out,'config','user.email','forge-c-mission@localhost')
# Reuse already functioning authorized transport without printing its URL or private configuration.
git(out,'remote','add','origin',git(old,'remote','get-url','origin').stdout.strip())
cmd=git(old,'config','--get','core.sshCommand',check=False)
if cmd.returncode==0:git(out,'config','core.sshCommand',cmd.stdout.strip())
plan={'schema':'forge-c/overnight-intake/1','source_revision':s['source_revision'],'started_epoch':int(time.time()),
 'deadline_epoch':s['deadline_epoch'],'progress_repo':str(out),'progress_branch':branch,
 'orders':[entry],'claim':'Experimental full ASPICE LL; HAL waits for verified LL; old mission preserved, no auto deployment'}
immutable_json(O/'progress-plan.json',plan)
wrapper=P/'deployment/run-aspice-rcc-recorder.py'
raw="""from pathlib import Path
import os,sys
P=Path('/mnt/data/forge-c/production-local-014')
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.lrtx import stack
raise SystemExit(stack.exec_in(stack.settings('local-rtx-v2-omniverse2-q38-aspice-max-mtp'),[str(P/'venv/bin/python'),'-m','forge_factory.afo.overnight',str(P/'deployment/aspice-rcc-pair-20261030-v1/progress-plan.json')]))
"""
immutable_bytes(wrapper,raw.encode())
unit=Path.home()/'.config/systemd/user/forge-qwen-mission-recorder.service'
before=unit.read_bytes();immutable_bytes(O/'recorder-unit-before.txt',before)
lines=before.decode().splitlines();assert sum(line.startswith('ExecStart=') for line in lines)==1
new='\n'.join('ExecStart='+str(P/'venv/bin/python')+' '+str(wrapper) if line.startswith('ExecStart=') else line for line in lines)+'\n'
with I.lock():
 assert I.read()['mode']=='RUNNING' and I.read()['epoch']==50
 fd,tmp=tempfile.mkstemp(prefix='.recorder-next-',dir=unit.parent)
 with os.fdopen(fd,'w') as f:f.write(new);f.flush();os.fsync(f.fileno())
 os.chmod(tmp,0o600);os.replace(tmp,unit)
 subprocess.run(['systemctl','--user','daemon-reload'],check=True,timeout=20)
 subprocess.run(['systemctl','--user','start','forge-qwen-mission-recorder.service'],check=True,timeout=20)
immutable_json(O/'recorder.json',{'status':'EXISTING_RECORDER_STARTED','progress_branch':branch,'interval_seconds':300,
 'expiry_stops_factory':False,'new_scheduler':False,'model_requests':0,'at':utc_now()})
print((O/'recorder.json').read_text())
