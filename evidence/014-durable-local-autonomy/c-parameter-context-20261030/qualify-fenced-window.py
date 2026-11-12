"""Finite serial verifier scopes after Qwen quiescence; no deployment, inference or deadline extension."""
from pathlib import Path
import json,os,subprocess,sys
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/reasoning-context-qualification-window-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations
from forge_factory.afo.queue import Store
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import immutable_json
S=Store();I=operations.Intent()
def quiet():
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute("SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL").fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
quiet();assert I.read()['mode']=='RUNNING' and I.read()['epoch']==72
O.mkdir(mode=0o700)
p=operations.synchronize(S,'pause',str(os.getuid()),'Owner requested medium/high speed comparison after this run finishes: qualify exact37c0c35 preparation and reporting; no model call, source activation, mission reset or grant renewal',expected_epoch=72,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
assert p['mode']=='PAUSED' and p['epoch']==73
immutable_json(O/'pause.json',{'mode':p['mode'],'epoch':p['epoch'],'source_revision':'37c0c354629312a70eb6a199989477036bb674d9','model_requests':0,'deployment':False})
results=[]
scopes_quiet=True
try:
 for cohort in ('reasoning','context'):
  assert I.read()['mode']=='PAUSED' and I.read()['epoch']==73;quiet()
  unit='forge-qual-reasoning-'+cohort+'-37c0c35-v1'
  command=['systemd-run','--user','--scope','--quiet','--collect','--unit='+unit,'-p','MemoryMax=8G','-p','MemorySwapMax=0','-p','CPUQuota=400%','-p','RuntimeMaxSec=660',
   str(P/'venv/bin/python'),str(P/'deployment/qualify-native-reasoning-context-37c0c35.py'),'--cohort',cohort]
  scopes_quiet=False
  try:
   run=subprocess.run(command,capture_output=True,timeout=660)
   (O/(cohort+'.log')).write_bytes(run.stdout+run.stderr)
   code=run.returncode
  except subprocess.TimeoutExpired as exc:
   (O/(cohort+'.log')).write_bytes((exc.stdout or b'')+(exc.stderr or b''));code=124
   subprocess.run(['systemctl','--user','stop',unit+'.scope'],capture_output=True,timeout=30)
  # Settle this owned scope on success as well as failure before resuming inference.
  subprocess.run(['systemctl','--user','stop',unit+'.scope'],capture_output=True,timeout=30)
  state=subprocess.run(['systemctl','--user','show',unit+'.scope','-p','LoadState,ActiveState,TasksCurrent'],capture_output=True,text=True,timeout=10)
  fields=dict(line.split('=',1) for line in state.stdout.splitlines() if '=' in line)
  scopes_quiet=fields.get('ActiveState')=='inactive' and (fields.get('LoadState')=='not-found' or fields.get('TasksCurrent')=='0')
  assert scopes_quiet,'VERIFIER_SCOPE_QUIESCENCE_NOT_PROVEN'
  results.append({'cohort':cohort,'returncode':code})
  immutable_json(O/(cohort+'-exit.json'),results[-1])
  if code:break
finally:
 current=I.read()
 if current['mode']=='PAUSED' and current['epoch']==73 and scopes_quiet:
  quiet()
  r=operations.synchronize(S,'resume',str(os.getuid()),'Finite source qualification ended; resume existing deployed source and model-free supervision; no automatic source promotion or retry',expected_epoch=73,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
  result={'mode':r['mode'],'epoch':r['epoch'],'cohorts':results,'model_requests':0,'deployment':False}
 else:
  result={'status':'VERIFIER_SCOPE_NOT_QUIESCENT' if not scopes_quiet else 'NEWER_OPERATOR_INTENT_PRESERVED','mode':current['mode'],'epoch':current['epoch'],'cohorts':results,'deployment':False}
 immutable_json(O/'result.json',result);print(json.dumps(result))

