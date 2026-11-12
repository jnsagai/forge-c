from pathlib import Path
import os,json,sys,subprocess,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/rcc-canonical-commit-reconciliation-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations,maintainer as M
from forge_factory.afo.queue import Store
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.durable import digest,immutable_json
from forge_factory.common import utc_now
s=json.loads((O/'scope.json').read_text());assert digest(s)=='a90483bdac34e445e72544fd6d92752af0c89e5114a351ae422ba1b97932870d'
proof=json.loads((O/'reconciliation-receipt.json').read_text());assert proof['status']=='EXISTING_MODEL_COMMIT_RECEIPT_RECONCILED'
assert time.time()<s['expiry_epoch']
S=Store();I=operations.Intent();before=json.loads((O/'all-missions-before.json').read_text())
with I.lock():
 assert I.read()['mode']=='PAUSED' and I.read()['epoch']==55
 assert not Executions(S).pending()
 assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==s['runtime_revision']
 assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
 case=json.loads(Path(s['case_path']).read_text());sub,receipt=M.submission(case,require_receipt=True)
 assert sub['candidate']==s['candidate_commit']
 for mid,record in before.items():assert MissionLedger(S).snapshot(mid)==record
operations.synchronize(S,'resume',str(os.getuid()),'Exact original Qwen commit receipt reconciled by qualified operator kernel, same source/policy/history; existing Conductor independently reviews; no new product intake',expected_epoch=55,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
with I.lock():
 assert I.read()['mode']=='RUNNING' and I.read()['epoch']==56
 subprocess.run(['systemctl','--user','--no-block','start',operations.UNIT,'forge-afo-watchdog-014-omniverse2.timer'],check=True,timeout=20)
 immutable_json(O/'resume.json',{'status':'EXISTING_CONDUCTOR_RESUMED_FOR_NORMAL_RECEIPT_ADOPTION_AND_REVIEW','operator_epoch':56,'runtime_revision':s['runtime_revision'],'source_unchanged':True,'mission_histories_preserved':True,'deadline_unchanged':True,'model_requests_by_resume':0,'at':utc_now()})
print((O/'resume.json').read_text())
