from pathlib import Path
import hashlib,json,os,subprocess,sys
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/afo-repair-live-20261029-v6'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.durable import immutable_json,immutable_bytes
from forge_factory.common import sha256_file,utc_now
from forge_factory.fabro.client import FabroClient,load_token
scope=json.loads((O/'scope.json').read_text())
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as db:
 with db.tx() as c:
  job=json.loads(c.execute('SELECT record FROM afo_local_agent_jobs WHERE order_id=?',(scope['new_order_id'],)).fetchone()[0]);x=json.loads(c.execute('SELECT record FROM afo_execution_liveness WHERE job_id=?',(job['job_id'],)).fetchone()[0]);assert x['execution_liveness']=='QUIESCENT' and x['resource_lease']=='RELEASED'
assert not (Path(job['case']).parent/'submission.json').exists(), 'USE_RECEIPT_BOUND_VERIFIER_FOR_SUBMITTED_CANDIDATE'
case=json.loads(Path(job['case']).read_text());src=Path(case['src']);out=O/'written-artifacts';out.mkdir(mode=0o700);writes={};submissions=[];tests=[]
with FabroClient(token=load_token(),timeout=10) as cl:
 for e in cl.iter_events(job['run_id']):
  if e['event']=='agent.tool.started':
   v=e['properties']['event']['ToolCallStarted'];a=v.get('arguments') or {};tool=v['tool_name']
   if tool.endswith('__write_source'):
    content=a['content'];writes[a['path']]={'event_seq':e['seq'],'at':e['ts'],'sha256':hashlib.sha256(content.encode()).hexdigest(),'bytes':len(content.encode())}
   if tool.endswith('__submit_candidate'):submissions.append({'event_seq':e['seq'],'field_lengths':{k:len(v) if isinstance(v,str) else None for k,v in a.items()},'summary':a.get('summary'),'reproducer':a.get('reproducer'),'symptom_signature':a.get('symptom_signature')})
  elif e['event']=='agent.tool.completed':
   v=e['properties']['event']['ToolCallCompleted']
   if v['tool_name'].endswith('__run_candidate_tests'):tests.append({'event_seq':e['seq'],'result':json.loads(v['output'])})
seed=json.loads((O/'seed-receipt.json').read_text())
for rel,seed_sha in seed['exact_copied_file_hashes'].items():
 if rel not in writes:
  assert sha256_file(src/rel)==seed_sha
  writes[rel]={'origin':'unchanged exact Qwen seed from recorded source native run','sha256':seed_sha,'bytes':(src/rel).stat().st_size,'source_native_run_id':seed['source_native_run_id']}
assert writes and len(writes)<=12
assert all(rel=='factory/python/forge_factory/fabro/runconfig.py' or (rel.startswith('factory/python/tests/afo_candidate/') and rel.endswith('.py') and '..' not in rel.split('/')) for rel in writes)
for rel,proof in writes.items():
 assert sha256_file(src/rel)==proof['sha256'];immutable_bytes(out/rel,(src/rel).read_bytes())
patch=subprocess.check_output(['git','-C',str(src),'diff','--binary']);immutable_bytes(out/'candidate-unsubmitted.patch',patch)
report={'schema':'forge-c/qwen-written-artifacts-snapshot/1','at':utc_now(),'job_id':job['job_id'],'native_run_id':job['run_id'],'base':case['base'],'case_sha256':sha256_file(Path(job['case'])),'files':writes,'candidate_owned_tests':tests,'failed_submission_calls':submissions,'candidate_commit':None,'broker_receipt':False,'author':'Actual Qwen native write_source events; no operator edits','original_worktree_changed_by_collector':False,'source_worktree':str(src),'artifact_root':str(out),'model_requests':0};immutable_json(out/'provenance.json',report);print(json.dumps(report,indent=2))
