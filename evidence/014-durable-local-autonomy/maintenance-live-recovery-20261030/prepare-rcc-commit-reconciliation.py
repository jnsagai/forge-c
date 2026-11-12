from pathlib import Path
import datetime,json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';Q=P/'deployment/qualification-commit-reconciliation-53e1234-v1/repo';O=P/'deployment/rcc-canonical-commit-reconciliation-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import authz,policy,operations
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.completion_receipt import Context
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.fabro.client import FabroClient,load_token
from forge_factory.common import utc_now,sha256_file
REV='53e1234709eeaea91aaf681d1d5068659c85762a';JID='afo-agent-61401956787984d8c097bc36'
assert operations.Intent().read()['mode']=='PAUSED' and operations.Intent().read()['epoch']==55
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()=='ab46545c1cfb7ffd90fb09715b6715b7d21ad242'
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
# The exact prepared revision may be qualified asynchronously; execution requires its PASS provenance.
assert subprocess.check_output(['git','-C',str(Q),'rev-parse','HEAD'],text=True).strip()==REV
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as S:
 assert not Executions(S).pending()
 Context.from_job(S,JID)
 with S.tx() as c:
  j=json.loads(c.execute('SELECT record FROM afo_local_agent_jobs WHERE job_id=?',(JID,)).fetchone()[0])
  assert j['state']=='RUNNING' and j['run_id']=='01M65A075HQ97KJXSG6A1Z9KC6'
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  mids=[r[0] for r in c.execute('SELECT mission_id FROM afo_missions')]
 histories={mid:MissionLedger(S).snapshot(mid) for mid in mids}
 case=json.loads(Path(j['case']).read_text());d=Path(j['case']).parent
 raw=(d/'submission-intent.json').read_bytes();intent=json.loads(raw)
 assert digest(intent)=='1fac9374b0f7ccaa85b36991569188e78de6b9a7f46293d9018d59ad668d6881'
 assert not (d/'submission-receipt.json').exists()
 head=subprocess.check_output(['git','-C',case['src'],'rev-parse','HEAD'],text=True).strip()
 actual=subprocess.check_output(['git','-C',case['src'],'show','-s','--format=%P%n%T%n%B','HEAD'],text=True).strip().split('\n',2)
 assert actual==[intent['parent'],intent['tree'],intent['message'].rstrip(' ')] and actual[2]!=intent['message']
 assert not subprocess.check_output(['git','-C',case['src'],'status','--porcelain'])
 matches=[]
 with FabroClient(token=load_token(),timeout=10) as client:
  for event in client.iter_events(j['run_id']):
   if event['event']!='agent.tool.started':continue
   item=(event['properties'].get('event') or {}).get('ToolCallStarted') or {}
   if item.get('tool_name')!='mcp__forge_maintainer_mcp__submit_candidate':continue
   args=item.get('arguments') or {}
   if not all(isinstance(args.get(k),str) for k in ('summary','reproducer','symptom_signature')):continue
   req={'case_sha256':sha256_file(Path(j['case'])),'summary':args['summary'],'reproducer':args['reproducer'],'signature':args['symptom_signature']}
   if digest(req)==intent['request_sha256']:matches.append({'seq':event['seq'],'args':args})
 assert matches and len({digest(x['args']) for x in matches})==1
 modelargs=matches[0]['args']
 exp=int(min(j['deadline_epoch'],histories[j['mission_id']]['limits']['deadline']))
 expires=datetime.datetime.fromtimestamp(exp,datetime.timezone.utc).isoformat().replace('+00:00','Z')
 assert time.time()<exp
 eff=policy.load(log=False);envelope=json.loads(S.order(j['order_id'])['envelope'])
 scope={'schema':'forge-c/operator-commit-reconciliation/1','qualified_reconciler_revision':REV,'runtime_revision':'ab46545c1cfb7ffd90fb09715b6715b7d21ad242','job_id':JID,'native_run_id':j['run_id'],'job_state_before':'RUNNING','mission_id':j['mission_id'],'order_id':j['order_id'],'request_id':envelope['request_id'],'case_path':j['case'],'case_sha256':j['case_sha256'],'intent_sha256':sha256_file(d/'submission-intent.json'),'request_sha256':intent['request_sha256'],'original_model_request_sha256':digest(modelargs),'native_submit_sequences':[x['seq'] for x in matches],'candidate_commit':head,'candidate_parent':actual[0],'candidate_tree':actual[1],'expected_message_sha256':digest(intent['message']),'git_cleaned_message_sha256':digest(actual[2]),'only_normalization':'TRAILING_ASCII_SPACE_GIT_CLEANUP','operator_epoch':55,'policy_sha256':eff.sha256,'expiry_epoch':exp,'expires_utc':expires,'source_change':False,'engineering_code_edits':False,'new_model_requests':0,'budget_or_deadline_changed':False,'historical_failures_reset':False,'standing_signing_delegation':'always approve it for now on automatically','authority':'RECOVER_EXISTING_MODEL_INITIATED_HASH_BOUND_EFFECT_ONLY','at':utc_now()}
 aid='AUTH-014-RCC-CANONICAL-COMMIT-20261030-V1'
 grant={'schema_version':'1.0','authorization_id':aid,'approver':'jefferson','approval_evidence_ref':'owner-standing-exact-commit-reconciliation:'+digest(scope),'issued_utc':utc_now(),'expires_utc':expires,'policy_sha256':eff.sha256,'mode':eff.mode,'allowed_actions':['recover_workorder'],'scope':{'order_ids':[envelope['request_id']],'driver_classes':['LL'],'models':[j['model']]},'signature_ref':aid+'.sig','signed_runbook_ref':'maintenance-commit-reconciliation-014:'+digest(scope)}
 assert not authz.schema_errors(grant),authz.schema_errors(grant)
 O.mkdir(mode=0o700)
 for name,obj in {'scope.json':scope,'authorization.json':grant,'model-request.json':modelargs,'all-missions-before.json':histories,'owner-approval.json':{'scope_sha256':digest(scope),'standing_signing_delegation':scope['standing_signing_delegation'],'interpretation':'Complete only the exact original model submission after Git-trimmed trailing space; keep raw intent, commit, engineering source, all expenditure/deadlines and native cancellation history. Qualified broker independently reviewed; no new inference or deployment.','at':utc_now()}}.items():immutable_json(O/name,obj)
 immutable_bytes(O/'original-submission-intent.json',raw)
 immutable_bytes(O/'authorization-message.bin',authz.message(grant))
 immutable_bytes(O/'allowed-signers',authz.ALLOWED_SIGNERS.read_bytes())
 print(json.dumps({'status':'EXACT_UNSIGNED_EXISTING_EFFECT_RECONCILIATION_PREPARED','scope_sha256':digest(scope),'candidate':head,'expiry_utc':expires,'model_requests':0,'source_deployed':False}))
