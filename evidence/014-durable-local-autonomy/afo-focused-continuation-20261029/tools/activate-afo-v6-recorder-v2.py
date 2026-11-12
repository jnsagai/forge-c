"""Reuse the existing progress recorder/service; no model call, new scheduler or order."""
from pathlib import Path
import json,os,subprocess,sys,tempfile,time
P=Path('/mnt/data/forge-c/production-local-014');O=P/'deployment/afo-repair-live-20261029-v6'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.afo.queue import Store
from forge_factory.afo.operations import Intent
from forge_factory.afo.durable import immutable_json,immutable_bytes
from forge_factory.common import utc_now
scope=json.loads((O/'scope.json').read_text());S=Store();I=Intent();unit='forge-qwen-mission-recorder.service'
assert time.time()<scope['deadline_epoch'] and S.order(scope['new_order_id'])
assert subprocess.check_output(['git','-C',str(P/'repo'),'rev-parse','HEAD'],text=True).strip()==scope['source_revision']
state=subprocess.check_output(['systemctl','--user','show',unit,'-p','ActiveState','--value'],text=True).strip();assert state in ('inactive','failed')
oldplan=json.loads((P/'deployment/overnight-20261027-v2/plan.json').read_text());old=Path(oldplan['progress_repo'])
out=P/'progress-afo-focused-20261029-v6';branch='overnight/2026-10-29-local-qwen-afo'
if not out.exists():subprocess.run(['git','clone','--shared',str(old),str(out)],check=True,capture_output=True)
else:
 assert not subprocess.check_output(['git','-C',str(out),'status','--porcelain'])
 assert subprocess.check_output(['git','-C',str(out),'rev-parse','HEAD'])==subprocess.check_output(['git','-C',str(old),'rev-parse','HEAD'])
def git(*args):return subprocess.run(['git','-C',str(out),*args],check=True,capture_output=True,text=True,timeout=30)
for key in ('remote.origin.url','core.sshCommand','credential.helper'):
 result=subprocess.run(['git','-C',str(old),'config','--get-all',key],capture_output=True,text=True)
 if result.returncode==0:
  subprocess.run(['git','-C',str(out),'config','--unset-all',key],capture_output=True)
  for value in result.stdout.splitlines():git('config','--add',key,value)
assert not git('ls-remote','--heads','origin',branch).stdout.strip(),'EXISTING_BRANCH_REQUIRES_RECONCILIATION'
git('checkout','-b',branch);git('config','user.name','Forge-C Overnight Recorder');git('config','user.email','forge-c-mission@localhost')
if (out/'plan.json').exists():git('mv','plan.json','historical-plan-before-focused-v6.json')
if git('diff','--cached','--name-only').stdout.strip():git('commit','-m','Preserve historical recorder plan before focused Qwen continuation')
plan={'schema':'forge-c/overnight-intake/1','source_revision':scope['source_revision'],'started_epoch':int(time.time()),'deadline_epoch':scope['deadline_epoch'],'progress_repo':str(out),'progress_branch':branch,'orders':[{'order_id':scope['new_order_id']}]}
# The already-present exact order is required. No new intake envelope or mission document is supplied.
# If it disappears, existing provision_order fails before any intake rather than inventing a replacement.
immutable_json(O/'progress-plan.json',plan)
wrapper=P/'deployment/run-overnight.py';raw=("from pathlib import Path\nimport os\np=Path('/mnt/data/forge-c/production-local-014')\nenv=dict(os.environ)\nfor line in (p/'state/afo/conductor.env').read_text().splitlines():\n if line and not line.startswith('#'):\n  k,v=line.split('=',1);env[k]=v\nenv.update(PYTHONPATH=str(p/'repo/factory/python'),PYTHONDONTWRITEBYTECODE='1',GIT_TERMINAL_PROMPT='0')\npy=str(p/'venv/bin/python')\nos.execvpe(py,[py,'-m','forge_factory.afo.overnight',str(p/'deployment/afo-repair-live-20261029-v6/progress-plan.json')],env)\n").encode()
with I.lock():
 assert I.read()['mode']=='RUNNING' and I.read()['epoch']==46 and not I.read()['effective_stop']
 assert S.order(scope['new_order_id']) and time.time()<scope['deadline_epoch']
 immutable_bytes(O/'recorder-wrapper.before',wrapper.read_bytes())
 fd,name=tempfile.mkstemp(prefix='.focused-recorder-',dir=wrapper.parent)
 with os.fdopen(fd,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
 os.chmod(name,0o600);os.replace(name,wrapper)
 subprocess.run(['systemctl','--user','start',unit],check=True,timeout=20)
 report={'status':'EXISTING_PROGRESS_RECORDER_STARTED','service':unit,'progress_branch':branch,'progress_repo':str(out),'record_interval_seconds':300,'mission_deadline_utc':scope['deadline_utc'],'new_orders_enrolled':0,'model_requests':0,'new_scheduler':False,'source_revision':scope['source_revision'],'operator_epoch':46,'at':utc_now()};immutable_json(O/'recorder-activation.json',report)
print(json.dumps(report))
