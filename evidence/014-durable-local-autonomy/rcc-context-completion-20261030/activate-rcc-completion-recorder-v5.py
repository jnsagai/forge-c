"""Restore the existing host-side Git observer; never expose network to the model namespace."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/rcc-context-completion-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.operations import Intent
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.afo.queue import Store
from forge_factory.common import utc_now
s=json.loads((O/'scope.json').read_text());assert digest(s)=='858bd287930424bbbb9b9cc2879641a8aa4221d4135377dd9be30d15c39228bf'
I=Intent();out=P/'progress-aspice-rcc-20261030-v1';unit=Path.home()/'.config/systemd/user/forge-qwen-mission-recorder.service'
def git(*args):return subprocess.run(['git','-C',str(out),*args],capture_output=True,text=True,check=True,timeout=25)
with I.lock():
 assert I.read()['mode']=='RUNNING' and I.read()['epoch']==54
 assert Store().order(s['new_order_id']) and time.time()<s['deadline_epoch']
 subprocess.run(['systemctl','--user','stop','forge-qwen-mission-recorder.service'],check=True,timeout=30)
 old=json.loads((O/'progress-plan-observer-v4.json').read_text())
 plan={**old,'source_revision':s['source_revision'],'started_epoch':int(time.time()),'orders':[{'order_id':s['continuation_of']},{'order_id':'afo-7ab1af2aa4e1d7b4'},{'order_id':s['new_order_id']}]}
 immutable_json(O/'progress-plan-observer-v5.json',plan)
 assert plan['source_revision']==subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()
 assert all(Store().order(e['order_id']) and list(e)==['order_id'] for e in plan['orders'])
 if (out/'plan.json').exists():
  git('mv','plan.json','historical-plan-before-context-completion-v5.json')
  git('commit','-m','Preserve previous observer source binding')
 wrapper=P/'deployment/run-rcc-context-recorder-host-v5.py'
 raw="""from pathlib import Path
import os
p=Path('/mnt/data/forge-c/production-local-014')
env=dict(os.environ)
for line in (p/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);env[k]=v
env.update(PYTHONPATH=str(p/'repo/factory/python'),PYTHONDONTWRITEBYTECODE='1',GIT_TERMINAL_PROMPT='0')
py=str(p/'venv/bin/python')
os.execvpe(py,[py,'-m','forge_factory.afo.overnight',str(p/'deployment/rcc-context-completion-20261030-v1/progress-plan-observer-v5.json')],env)
"""
 immutable_bytes(wrapper,raw.encode())
 before=unit.read_bytes();immutable_bytes(O/'recorder-unit-before-context-completion-v5.txt',before)
 new='\n'.join('ExecStart='+str(P/'venv/bin/python')+' '+str(wrapper) if line.startswith('ExecStart=') else line for line in before.decode().splitlines())+'\n'
 fd,name=tempfile.mkstemp(prefix='.recorder-host-',dir=unit.parent)
 with os.fdopen(fd,'w') as stream:stream.write(new);stream.flush();os.fsync(stream.fileno())
 os.chmod(name,0o600);os.replace(name,unit)
 subprocess.run(['systemctl','--user','daemon-reload'],check=True,timeout=20)
 subprocess.run(['systemctl','--user','start','forge-qwen-mission-recorder.service'],check=True,timeout=20)
 immutable_json(O/'recorder-context-continuation-v5.json',{'status':'HOST_SIDE_EXISTING_OBSERVER_RESTORED',
  'old_failed_publication_preserved':True,'model_namespace_network_unchanged':True,'inference_restarted':False,
  'plan_has_no_intake_payload':True,'expiry_unchanged':s['deadline_utc'],'model_requests':0,'at':utc_now()})
print((O/'recorder-context-continuation-v5.json').read_text())
