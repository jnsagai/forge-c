"""CPU-only source qualification after the frozen MTP campaign; no deployment/model calls."""
from pathlib import Path
import argparse,json,os,subprocess,sys
P=Path('/mnt/data/forge-c/production-local-014');O=P/'deployment/q38-mtp-speed-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.afo import operations
from forge_factory.afo.queue import Store
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import immutable_json
a=argparse.ArgumentParser();a.add_argument('--expected-epoch',type=int,required=True);args=a.parse_args()
S=Store();I=operations.Intent()
complete=json.loads((O/'continuation-complete.json').read_text());assert complete['status']=='ALL_FROZEN_MTP_COHORTS_COMPLETED'
assert complete['source_revision']=='a9b2ddfccc326bdcf8287c95a4310c0408429ccb'
for v in ('draft3','draft2','draft4','draft6'):
 r=json.loads((O/v/'completion.json').read_text());assert r['observed_trials']==r['expected_trials']==8
assert subprocess.check_output(['git','-C',str(P/'repo'),'rev-parse','HEAD'],text=True).strip()==complete['source_revision']
def quiet():
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
quiet();assert I.read()['mode']=='RUNNING' and I.read()['epoch']==args.expected_epoch
N=P/('deployment/non-thinking-qualification-window-epoch'+str(args.expected_epoch)+'-v1');N.mkdir(mode=0o700)
pause=operations.synchronize(S,'pause',str(os.getuid()),'Owner goal: qualify owner-requested explicit non-thinking comparison and existing context correction after all MTP measurements; CPU only, no source activation or model call',expected_epoch=args.expected_epoch,authentication={'method':'OS_STATE_DIRECTORY_OWNER'})
epoch=pause['epoch'];unit='forge-qual-non-thinking-12e601e4-'+str(epoch)+'.scope';scope_quiet=True;code=125
try:
 quiet();scope_quiet=False
 command=['systemd-run','--user','--scope','--quiet','--collect','--unit='+unit.removesuffix('.scope'),'-p','MemoryMax=8G','-p','MemorySwapMax=0','-p','CPUQuota=400%','-p','RuntimeMaxSec=660',str(P/'venv/bin/python'),str(P/'deployment/qualify-native-non-thinking-12e601e4.py'),'--expected-epoch',str(epoch)]
 try:
  run=subprocess.run(command,capture_output=True,timeout=665);(N/'qualification.log').write_bytes(run.stdout+run.stderr);code=run.returncode
 except subprocess.TimeoutExpired as exc:
  (N/'qualification.log').write_bytes((exc.stdout or b'')+(exc.stderr or b''));code=124
finally:
 subprocess.run(['systemctl','--user','stop',unit],capture_output=True,timeout=30)
 state=subprocess.run(['systemctl','--user','show',unit,'-p','LoadState,ActiveState,TasksCurrent'],capture_output=True,text=True,timeout=10)
 fields=dict(line.split('=',1) for line in state.stdout.splitlines() if '=' in line)
 scope_quiet=fields.get('ActiveState')=='inactive' and (fields.get('LoadState')=='not-found' or fields.get('TasksCurrent')=='0')
 current=I.read();resumed=False
 if scope_quiet and current['mode']=='PAUSED' and current['epoch']==epoch:
  current=operations.synchronize(S,'resume',str(os.getuid()),'CPU-only qualification ended; preserve deployed MTP source and all prior history; no source promotion or product retry',expected_epoch=epoch,authentication={'method':'OS_STATE_DIRECTORY_OWNER'})
  resumed=True
 result={'exit_code':code,'source_revision':'12e601e4f53ab71b6d184ae19379faa1dd8f6e97','owned_verifier_quiescent':scope_quiet,'operator_mode':current['mode'],'operator_epoch':current['epoch'],'resumed_only_own_pause':resumed,'model_requests':0,'deployment':False}
 immutable_json(N/'result.json',result);print(json.dumps(result))
raise SystemExit(code)

