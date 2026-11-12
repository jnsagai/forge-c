"""Read-only metadata observer; no model text, private primary text, credentials or hidden reasoning."""
from pathlib import Path
import collections, json, os, subprocess, sys, time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/idr-m1-high-20261028'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#'):
  k,v=line.split('=',1);os.environ[k]=v
os.environ['FORGE_REPO_ROOT']=str(R);sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import policy
from forge_factory.afo.operations import Intent
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.fabro.client import FabroClient,load_token,run_status
from forge_factory.inspection.engine import Store as Inspections,PHASES
from forge_factory.common import utc_now
from forge_factory.afo.durable import digest
S=Store();L=MissionLedger(S);scope=json.loads((O/'scope.json').read_text());oid=scope['order_id']
order=S.order(oid);attempts=S.attempts(oid);observations=[];ws=None
for attempt in attempts:
 ws=P/'state/workorders'/('WO-AFO-'+oid.removeprefix('afo-')+'-a'+str(attempt['seq']))/'workspace'
 st=Inspections(ws);phases=[]
 for phase in PHASES:
  baselines=st.baselines(phase);ins=st.inspections(phase)
  phases.append({'phase':phase,'baselines':len(baselines),'inspections':len(ins),
   'gate':{k:v for k,v in st.gate(phase).items() if k in ['decision','reason','baseline_id','inspection_id']}})
 observations.append({'attempt_id':attempt['attempt_id'],'seq':attempt['seq'],'state':attempt['state'],'phases':phases})
with S.tx() as c:
 jobs=[json.loads(r[0]) for r in c.execute('SELECT record FROM afo_product_jobs') if json.loads(r[0]).get('order_id')==oid]
 requests=[json.loads(r[0]) for r in c.execute('SELECT record FROM afo_request_ledger') if json.loads(r[0]).get('job_id') in {j['job_id'] for j in jobs}]
executions=[Executions(S).get(j['job_id']) for j in jobs]
units={u:subprocess.run(['systemctl','--user','is-active',u],capture_output=True,text=True).stdout.strip()
 for u in ['forge-conductor-local-omniverse2.service','forge-afo-watchdog-014-omniverse2.timer','forge-idr-m1-20261028.service']}
natives=[]
with FabroClient(base_url='http://127.0.0.1:32491/api/v1',token=load_token(),timeout=8) as client:
 for ex in executions:
  for rid in (ex or {}).get('native_run_ids',[]):
   run=client.get_run(rid)
   natives.append({'native_id':rid,'status':run_status(run),'updated_at':run.get('updated_at')})
eff=policy.load(log=False);intent=Intent().read()
with S.tx() as c:mids=[r[0] for r in c.execute('SELECT mission_id FROM afo_missions')]
prior={m:L.snapshot(m) for m in mids if m!=scope['mission_id']}
before=json.loads((O/'history-before.json').read_text())
body={'at':utc_now(),'source_revision':subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip(),
 'source_dirty':bool(subprocess.check_output(['git','-C',str(R),'status','--porcelain'],text=True).strip()),
 'intent':{k:intent[k] for k in ['mode','epoch']},'policy_mode':eff.mode,'policy_sha256':eff.sha256,
 'order':{k:order.get(k) for k in ['order_id','state','terminal_reason','created_epoch']},'mission':L.snapshot(scope['mission_id']),
 'attempts':observations,'native_handles':natives,'executions':executions,
 'requests':[{k:r.get(k) for k in ['request_id','state','input_tokens','output_tokens','reported_tokens','charge','reserved_tokens','created_at','updated_at']} for r in requests],
 'request_state_counts':dict(collections.Counter(r.get('state') for r in requests)),
 'old_missions_unchanged':prior==before,'old_mission_history_sha256':digest(prior),
 'units':units,'gpu':subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,memory.free,utilization.gpu','--format=csv,noheader'],text=True).strip(),
 'runtime_qualification':'NOT_ESTABLISHED','product_success':'NOT_ESTABLISHED','safety_assurance':'NOT_ASSESSED'}
if '--compact' in sys.argv:
 print('Updated:',body['at'])
 print('Order:',body['order']['order_id'],body['order']['state'])
 print('Operator:',body['intent'],'| GPU:',body['gpu'])
 print('Native:',', '.join(n['native_id']+' '+n['status'] for n in natives) or 'not launched')
 print('Requests:',len(requests),body['request_state_counts'])
 print('Provider-reported completed output tokens:',sum(r.get('output_tokens') or 0 for r in requests),'| Requests with unknown usage:',sum(r.get('reported_tokens') is None for r in requests))
 print('Mission charge (conservative, not actual usage):',body['mission']['charged_tokens'])
 if body['order'].get('terminal_reason'):print('Terminal reason:',body['order']['terminal_reason'])
 for attempt in observations:
  print('Attempt',attempt['seq'],attempt['state'])
  for phase in attempt['phases']:
   gate=phase['gate'];print(' ',phase['phase'],gate.get('decision'),gate.get('reason',''))
 print('Recorder:',body['units']['forge-idr-m1-20261028.service'])
else:print(json.dumps(body))
