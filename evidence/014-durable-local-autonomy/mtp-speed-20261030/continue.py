"""Finite owner-authorized MTP cohorts; Conductor retains all scheduling/dispatch authority."""
from pathlib import Path
import json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');O=P/'deployment/q38-mtp-speed-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.afo.operations import Intent
from forge_factory.afo.durable import immutable_json
from forge_factory.common import sha256_file,utc_now
scope=json.loads((O/'scope.json').read_text());tools=json.loads((O/'execution-tools.json').read_text());I=Intent()
assert sha256_file(Path(__file__))==tools['continue-mtp-speed.py']['sha256']
expected=79
for variant in ('draft3','draft2','draft4','draft6'):
 E=O/variant;deadline=scope['grants'][variant]['mission']['limits']['deadline']
 completion=E/'completion.json';activation=E/'activation.json'
 if completion.exists():
  done=json.loads(completion.read_text());assert done['source_revision']==scope['source_revision'] and done['observed_trials']==8
  assert done['mission']['mission_id']==scope['grants'][variant]['mission']['mission_id']
  expected=json.loads(activation.read_text())['operator_epoch'];continue
 assert time.time()<deadline,'EXPERIMENT_AUTHORITY_EXPIRED'
 if not activation.exists():
  current=I.read();assert current['epoch']==expected and current['mode']==('PAUSED' if expected==79 else 'RUNNING'),'NEWER_OPERATOR_INTENT_PRESERVED'
  tool=P/'deployment/activate-mtp-speed.py';assert sha256_file(tool)==tools[tool.name]['sha256']
  with (E/'activation-driver.log').open('ab') as log:
   r=subprocess.run([str(P/'venv/bin/python'),str(tool),'--variant',variant,'--epoch',str(expected)],stdout=log,stderr=subprocess.STDOUT,timeout=300)
  immutable_json(E/'activation-exit.json',{'code':r.returncode,'at':utc_now()})
  if r.returncode:raise SystemExit(r.returncode)
 active=json.loads(activation.read_text());expected=active['operator_epoch']
 assert I.read()['mode']=='RUNNING' and I.read()['epoch']==expected
 tool=P/'deployment/run-mtp-speed.py';assert sha256_file(tool)==tools[tool.name]['sha256']
 with (E/'driver.log').open('ab') as log:
  r=subprocess.run([str(P/'venv/bin/python'),str(tool),'--variant',variant],stdout=log,stderr=subprocess.STDOUT)
 immutable_json(E/'driver-exit.json',{'code':r.returncode,'at':utc_now(),'automatic_product_retry':False,'grant_renewed':False})
 if r.returncode:raise SystemExit(r.returncode)
 assert completion.exists()
immutable_json(O/'continuation-complete.json',{'status':'ALL_FROZEN_MTP_COHORTS_COMPLETED','at':utc_now(),'source_revision':scope['source_revision'],'draft_order':[3,2,4,6],'factory_service':'CONTINUES_MODEL_FREE','product_accepted':False,'automatic_selection':False,'grant_renewed':False})

