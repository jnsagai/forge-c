from pathlib import Path
import datetime,json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/rcc-signature-binding-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations,authz,policy,maintainer as M
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.completion_receipt import Context
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.common import utc_now,sha256_file
assert operations.Intent().read()['mode']=='RUNNING' and operations.Intent().read()['epoch']==56
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as S:
 assert not Executions(S).pending()
 with S.tx() as c:
  j=json.loads(c.execute("SELECT record FROM afo_local_agent_jobs WHERE job_id='afo-agent-60d77f8751d27b8fe746cde3'").fetchone()[0])
  mids=[r[0] for r in c.execute('SELECT mission_id FROM afo_missions')]
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
 Context.from_job(S,j['job_id']);case=json.loads(Path(j['case']).read_text());sub,receipt=M.submission(case,require_receipt=True)
 projection=S.proposal(case['proposal_id']);assert projection['status']=='REJECTED' and not sub['veto']
 manifest=json.loads(Path(sub['staged']['manifest']).read_text());rawsig=manifest['reproducers'][0]['symptom_signature']
 assert rawsig=='SYMPTOM_PRESENT:lrtx-profile-context-24576-legacy-despite-selected-262144'
 histories={mid:MissionLedger(S).snapshot(mid) for mid in mids};mission=histories[j['mission_id']]
 assert mission['corrections']==0 and mission['limits']['max_corrections']==1
 exp=int(min(j['deadline_epoch'],mission['limits']['deadline']));assert time.time()<exp
 expires=datetime.datetime.fromtimestamp(exp,datetime.timezone.utc).isoformat().replace('+00:00','Z')
 eff=policy.load(log=False);env=json.loads(S.order(j['order_id'])['envelope'])
 scope={'schema':'forge-c/operator-signature-binding/1','qualified_kernel_revision':'5a288206f8b64c2435375f0e4b943f295ea8e14d','runtime_revision':'ab46545c1cfb7ffd90fb09715b6715b7d21ad242','job_id':j['job_id'],'native_run_id':j['run_id'],'mission_id':j['mission_id'],'order_id':j['order_id'],'request_id':env['request_id'],'case_sha256':j['case_sha256'],'case_path':j['case'],'candidate':sub['candidate'],'baseline':case['base'],'original_receipt_sha256':digest(receipt),'original_manifest_sha256':digest(manifest),'source_proposal_record_sha256':projection['record_sha256'],'raw_signature':rawsig,'canonical_signature':rawsig.split(':',1)[1],'transformation':'REMOVE_ONE_LITERAL_SYMPTOM_PRESENT_PREFIX','protocol_corrections_before':0,'protocol_corrections_after':1,'model_jobs_or_engineering_attempts_added':0,'engineering_or_reproducer_bytes_changed':False,'legacy_cre_gates':'UNCHANGED_AND_MUST_RUN','root_rework_limit_reset':False,'operator_epoch':56,'policy_sha256':eff.sha256,'expires_utc':expires,'expiry_epoch':exp,'standing_signing_delegation':'always approve it for now on automatically','source_deployment':False,'at':utc_now()}
 aid='AUTH-014-RCC-SIGNATURE-BIND-20261030-V1'
 grant={'schema_version':'1.0','authorization_id':aid,'approver':'jefferson','approval_evidence_ref':'owner-standing-deterministic-signature-binding:'+digest(scope),'issued_utc':utc_now(),'expires_utc':expires,'policy_sha256':eff.sha256,'mode':eff.mode,'allowed_actions':['recover_workorder'],'scope':{'order_ids':[env['request_id']],'driver_classes':['LL'],'models':[j['model']]},'signature_ref':aid+'.sig','signed_runbook_ref':'maintenance-signature-binding-014:'+digest(scope)}
 assert not authz.schema_errors(grant),authz.schema_errors(grant)
 O.mkdir(mode=0o700)
 for name,obj in {'scope.json':scope,'authorization.json':grant,'all-missions-before.json':histories,'owner-approval.json':{'scope_sha256':digest(scope),'standing_signing_delegation':scope['standing_signing_delegation'],'interpretation':'Exact prefix-only administrative interpretation using one existing correction, no new engineering attempt or changed program/proof bytes; raw failures retained; normal independent CRE gates required, no source deployment.','at':utc_now()}}.items():immutable_json(O/name,obj)
 immutable_bytes(O/'authorization-message.bin',authz.message(grant));immutable_bytes(O/'allowed-signers',authz.ALLOWED_SIGNERS.read_bytes())
 print(json.dumps({'status':'EXACT_UNSIGNED_BOUNDED_SIGNATURE_BINDING_PREPARED','scope_sha256':digest(scope),'candidate':sub['candidate'],'expires_utc':expires,'model_requests':0}))
