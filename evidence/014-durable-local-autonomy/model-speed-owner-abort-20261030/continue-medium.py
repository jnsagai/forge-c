"""Finite continuation of the frozen speed pilot; existing Conductor owns all admission."""
from pathlib import Path
import json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');O=P/'deployment/q38-reasoning-speed-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.afo.operations import Intent
from forge_factory.afo.durable import immutable_json
I=Intent();scope=json.loads((O/'scope.json').read_text());deadline=scope['grants']['xhigh']['mission']['limits']['deadline']
while not (O/'xhigh/completion.json').exists():
 r=I.read()
 if r['mode']!='RUNNING' or r['epoch']!=76 or time.time()>=deadline:
  immutable_json(O/'medium-followup-not-run.json',{'status':'NEWER_OPERATOR_INTENT_OR_EXPIRED_SCOPE','mode':r['mode'],'epoch':r['epoch'],'model_requests':0});raise SystemExit(3)
 time.sleep(10)
if (O/'medium/activation.json').exists():
 raise SystemExit('MEDIUM_ALREADY_ACTIVATED_NO_DUPLICATE_DRIVER')
assert I.read()['mode']=='RUNNING' and I.read()['epoch']==76 and time.time()<deadline
with (O/'medium/activation.log').open('xb') as log:
 r=subprocess.run([str(P/'venv/bin/python'),str(P/'deployment/activate-q38-reasoning-speed.py'),'--effort','medium','--epoch','76'],stdout=log,stderr=subprocess.STDOUT,timeout=300)
immutable_json(O/'medium/activation-exit.json',{'code':r.returncode})
if r.returncode:raise SystemExit(r.returncode)
with (O/'medium/driver.log').open('xb') as log:
 r=subprocess.run([str(P/'venv/bin/python'),str(P/'deployment/run-q38-reasoning-speed.py'),'--effort','medium'],stdout=log,stderr=subprocess.STDOUT)
immutable_json(O/'medium/driver-exit.json',{'code':r.returncode,'automatic_product_retry':False,'factory_service':'CONTINUES_MODEL_FREE','grant_renewed':False})
raise SystemExit(r.returncode)

