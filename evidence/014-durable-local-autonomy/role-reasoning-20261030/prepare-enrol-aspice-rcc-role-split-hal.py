"""Conditional finite HAL intake. A single check/action; no scheduler or model calls."""
from pathlib import Path
import argparse,copy,hashlib,json,os,re,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/aspice-rcc-role-split-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations,policy,contracts,dispatch,authz
from forge_factory.afo.queue import Store,ReadSnapshot
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.overnight import provision_order
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.common import sha256_file,utc_now
from forge_factory.workorder import provided_ll
from forge_factory.fabro.client import FabroClient,load_token,run_status
from forge_factory.release.finalize import verify_archive
ap=argparse.ArgumentParser();ap.add_argument('--enrol',action='store_true');args=ap.parse_args()
s=json.loads((O/'scope.json').read_text());assert digest(s)=='7a3aa5041f60f51edd91a3458406fe463ff7b38a80de7c0a5550dfc028007533'
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==s['source_revision']
I=operations.Intent();intent=I.read();assert intent['mode']=='RUNNING' and intent['epoch']==104 and time.time()<s['deadline_epoch'],'NEWER_INTENT_OR_DEADLINE_PRESERVED'
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as read:
 order=read.order(s['ll']['order_id'])
 if order['state']!='READY_FOR_OFFLINE_REVIEW':
  print(json.dumps({'status':'NOT_RUN_VERIFIED_LL_REQUIRED','ll_order_state':order['state'],'hal_submitted':False,'model_requests':0,'at':utc_now()}));raise SystemExit(3)
 attempts=read.attempts(s['ll']['order_id']);att=attempts[-1];record=att['record']
 ws=P/'state/workorders'/record['workspace_ref'].removeprefix('workorder:')/'workspace';assert ws.resolve().is_relative_to(P/'state/workorders')
 with read.tx() as c:
  candidates=[json.loads(x[0]) for x in c.execute('SELECT record FROM afo_product_jobs')]
  jobs=[j for j in candidates if j.get('order_id')==s['ll']['order_id'] and j.get('attempt_id')==att['attempt_id']]
  assert len(jobs)==1;job=jobs[0]
  ex=c.execute('SELECT record FROM afo_execution_liveness WHERE job_id=?',(job['job_id'],)).fetchone();ex=json.loads(ex[0])
  assert ex['execution_liveness']=='QUIESCENT' and ex['resource_lease']=='RELEASED'
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
 snapshot=MissionLedger(read).snapshot(s['mission_id'])
with FabroClient(token=load_token(),timeout=10) as client:
 assert ex['native_run_ids'] and all(run_status(client.get_run(rid))=='SUCCEEDED' for rid in ex['native_run_ids'])
manifest=json.loads((ws/'.forge-run/manifest.json').read_text())
inv=json.loads((ws/'.forge-run/lrtx/SWE.1/inventory.json').read_text())
required=set()
for text in manifest['scope']:
 if text.lower().startswith('out of scope'):continue
 for first,last in re.findall(r'\b(\d+\.\d+\.\d+)\s*[-–]\s*(\d+\.\d+\.\d+)\b',text):
  a=first.split('.');b=last.split('.');assert a[:-1]==b[:-1] and 0<=int(b[-1])-int(a[-1])<1024
  required.update('.'.join(a[:-1]+[str(n)]) for n in range(int(a[-1]),int(b[-1])+1))
missing=sorted(required-{r['section'] for r in inv['registers']})
if missing:
 print(json.dumps({'status':'NOT_RUN_LL_GLOBAL_SCOPE_NOT_PROVEN','omitted_owner_sections':missing,'hal_submitted':False,'model_requests':0}));raise SystemExit(3)
verdict=dispatch.package_verdict(ws/'.forge-run/package.json');assert verdict['verdict']=='READY_FOR_OFFLINE_REVIEW'
package=json.loads((ws/'.forge-run/package.json').read_text());archive=Path(package['archive'])
assert archive.resolve().is_relative_to(P/'archives') and not archive.is_symlink()
integrity=verify_archive(archive);assert integrity['integrity']=='PASS'
header,provenance=provided_ll(ws.parent.name,'rcc');assert hashlib.sha256(header).hexdigest()==provenance['sha256']
proof={'status':'PASS_FRESH_LL_DEPENDENCY','source_revision':s['source_revision'],'ll_order':s['ll']['order_id'],'attempt_id':att['attempt_id'],'work_order':ws.parent.name,'native_run_ids':ex['native_run_ids'],'archive_sha256':sha256_file(archive),'provided_ll':provenance,'archive_integrity':integrity,'at':utc_now()}
if not args.enrol:
 print(json.dumps({'status':'PASS_DEPENDENCY_CHECK_ONLY','proof':proof,'hal_submitted':False,'model_requests':0}));raise SystemExit(0)
launch=json.loads((O/'launch.json').read_text())
launch.update(example=s['hal']['example'],provided_from=ws.parent.name)
env=json.loads((O/'envelope.json').read_text());raw=json.dumps(launch,sort_keys=True,separators=(',',':')).encode()
env.update(driver_class='HAL',request_id=s['hal']['request_id'],deadline_utc=s['deadline_utc'],input_manifest_ref='.evidence-tmp/aspice-rcc-role-split-20261030-v1/hal-launch.json',manifest_sha256=hashlib.sha256(raw).hexdigest(),submitted_utc=utc_now(),target='Complete RCC HAL SWE.1-SWE.6 using newly independently verified LL; ASPICE-only blocking gates and existing stepwise AFO recovery')
contracts.require('work-order',env)
entry={'order_id':s['hal']['order_id'],'continuation_of':s['ll']['order_id'],'envelope':env,'mission':{'mission_id':s['mission_id'],'lineage':snapshot['lineage'],'limits':snapshot['limits'],'authorization_ref':snapshot['authorization_ref'],'admission_authorization_ref':s['primary_authorization'],'request':{'order_id':env['request_id'],'driver_class':'HAL','model':s['model']}}}
S=Store()
with I.lock():
 now=I.read();assert now['mode']=='RUNNING' and now['epoch']==104 and time.time()<s['deadline_epoch']
 assert dispatch.package_verdict(ws/'.forge-run/package.json')==verdict and sha256_file(archive)==proof['archive_sha256']
 assert MissionLedger(S).snapshot(s['mission_id'])==snapshot,'MISSION_CHANGED_REPREPARE_WITHOUT_RESET'
 eff=policy.load(log=False);assert eff.mode=='PILOT' and eff.sha256==s['policy_sha256']
 assert authz.find(eff.mode,eff.sha256,ref=s['primary_authorization'],action='submit_workorder',request=entry['mission']['request']).allow
 D=O/'hal';D.mkdir(mode=0o700)
 immutable_json(D/'dependency-proof.json',proof);immutable_bytes(D/'launch.json',raw);immutable_json(D/'entry.json',entry)
 immutable_bytes(R/env['input_manifest_ref'],raw)
 provision_order(S,entry,eff,s['deadline_epoch'])
 immutable_json(D/'intake.json',{'status':'HAL_ENROLLED_AFTER_INDEPENDENT_LL_VERIFICATION','order_id':entry['order_id'],'same_mission':s['mission_id'],'source_revision':s['source_revision'],'scope_sha256':digest(s),'provided_ll_sha256':provenance['sha256'],'historical_counters_preserved':True,'model_requests_by_intake':0,'at':utc_now()})
print((D/'intake.json').read_text())

