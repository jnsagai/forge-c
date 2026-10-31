"""Finite serial verifier scopes after Qwen quiescence; no deployment, inference or deadline extension."""
from pathlib import Path
import json,os,subprocess,sys
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/reasoning-context-qualification-stopped73-ram-v2'
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
quiet();assert I.read()['mode']=='STOPPED' and I.read()['epoch']==73 and I.read()['effective_stop']
O.mkdir(mode=0o700)
results=[]
scopes_quiet=True
try:
 for cohort in ('reasoning','context'):
  assert I.read()['mode']=='STOPPED' and I.read()['epoch']==73;quiet()
  unit='forge-qual-reasoning-'+cohort+'-37c0c35-stopped73-ram-v2'
  command=['systemd-run','--user','--scope','--quiet','--collect','--unit='+unit,'-p','MemoryMax=8G','-p','MemorySwapMax=0','-p','CPUQuota=400%','-p','RuntimeMaxSec=660',
   str(P/'venv/bin/python'),str(P/'deployment/qualify-native-reasoning-context-stopped73-ram.py'),'--cohort',cohort]
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
 result={'status':'PASS' if scopes_quiet and len(results)==2 and all(x['returncode']==0 for x in results) else 'FAIL','mode':current['mode'],'epoch':current['epoch'],'operator_intent_unchanged':current['mode']=='STOPPED' and current['epoch']==73 and current['effective_stop'],'cohorts':results,'model_requests':0,'deployment':False,'automatic_resume':False,'owned_scopes_quiescent':scopes_quiet}
 immutable_json(O/'result.json',result);print(json.dumps(result))
