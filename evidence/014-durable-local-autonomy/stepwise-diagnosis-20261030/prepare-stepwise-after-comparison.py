"""Prepare the existing four-question diagnosis mode after current work; no grant, activation or inference."""
from pathlib import Path
import json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';D=P/'deployment';F=D/'wal-session-followup-a7804054-v1/result.json';O=D/'q38-stepwise-protocol-20261030-v1';N=D/'stepwise-preparation-20261030-v1';N.mkdir(mode=0o700)
while not F.exists():
 if time.time()>=1793368372.0:
  (N/'result.json').write_text(json.dumps({'status':'NOT_RUN_EXISTING_WINDOW_ENDED','model_requests':0})+'\n');raise SystemExit(3)
 time.sleep(15)
prior=json.loads(F.read_text());window=prior.get('window_result') or {}
assert window.get('owned_verifier_quiescent') is True
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations,qualification as Q,qualification_inputs as inputs,semantic_proposal as S,durable_agent as A
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import immutable_json,digest
from forge_factory.common import sha256_file
I=operations.Intent();intent=I.read();assert intent['mode']=='RUNNING' and intent['epoch']==96
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()=='12e601e4f53ab71b6d184ae19379faa1dd8f6e97'
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
proof=json.loads((D/'qualification-non-thinking-12e601e4-epoch87-v1/provenance.json').read_text());assert proof['source_revision']=='12e601e4f53ab71b6d184ae19379faa1dd8f6e97' and proof['pytest_exit_code']==0 and proof['summary']=={'tests':279,'errors':0,'failures':0,'skipped':0}
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as st:
 assert not Executions(st).pending()
 with st.tx() as c:
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
O.mkdir(mode=0o700);old={k:os.environ.get(k) for k in ['FORGE_STATE_DIR','FORGE_EVENTS_DIR']}
os.environ['FORGE_STATE_DIR']=str(O/'preparation-state');os.environ['FORGE_EVENTS_DIR']=str(O/'preparation-events')
try:
 inp=inputs.prepare(O/'medium',compiler=P/'toolchains/LLVM-19.1.7-Linux-X64/bin/clang',campaign_id='q38-stepwise-medium-20261030-v1',authorization_ref='AUTH-014-STEPWISE-Q38-MEDIUM-20261030-V1',model='qwen3.8:27b-q8_0',profile='local-rtx-v2-omniverse2-q38-qm-demo-repair-mtp-medium-trial',qualification_job_tokens=262144,stage='targeted')
 measures={}
 for trial,b in inp['jobs'].items():
  job={'case':b['case'],'model':'qwen3.8:27b-q8_0','role':'afo-recovery-planner','profile':'local-rtx-v2-omniverse2-q38-qm-demo-repair-mtp-medium-trial'}
  _,measures[trial]=A.request_material(job,step=1)
finally:
 for k,v in old.items():
  if v is None:os.environ.pop(k,None)
  else:os.environ[k]=v
assert Q.requests_per_job({'task_class':S.TWO_STEP})==4
identity={'role':'afo-recovery-planner','model_digest':inp['model_configuration']['model_digest'],'precision':'Q8_0','reasoning':'medium','schema_mode':'json_schema','adapter_revision':'12e601e4f53ab71b6d184ae19379faa1dd8f6e97','context_tokens':262144,'sampling':{'temperature':0},'task_class':S.TWO_STEP}
plan={'schema':'forge-c/stepwise-diagnosis-pilot/1','scope':'EXPOSED_PROTOCOL_CASES_NOT_PRODUCT_OR_FRESH_HOLDOUT_QUALIFICATION','source_revision':identity['adapter_revision'],'task_class':S.TWO_STEP,'requests_per_job_bound':4,'questions':['fact_conflict','catalogued_technique','owning_phase_strategy','bounded_repair_details'],'complete_packet_unknown_still_allowed':True,'incomplete_packet_unknown_only_grammar_disclosed':True,'cases_oracles_gates_changed':False,'same_model_agreement_is_independent_evidence':False,'initial_step_measurements':measures,'later_steps':'Runtime measures actual complete serialized context and cumulative allowance before every request; no fabricated future model answers','one_inference':True,'mtp_draft':3,'context_tokens':262144,'precision':'Q8_0','kv':'f16','reasoning':'medium','all_failures_and_unused_trials_retained':True,'automatic_selection':False}
immutable_json(O/'stepwise-plan.json',plan)
m=Q.freeze('targeted',O/'medium/campaign-unsigned.json',identity=identity,inputs=[str(O/'medium/inputs.json'),str(O/'stepwise-plan.json')],jobs=inp['jobs'],model_profile='qwen3.8:27b-q8_0',job_token_reservations=inp['requested_initial_reservations'])
r={'status':'PREPARED_NOT_RUN','source_revision':identity['adapter_revision'],'identity':identity,'case_count':8,'max_provider_requests':32,'manifest_sha256':digest(m),'model_requests':0,'grants_created':0,'mission_job_created':False,'source_activated':False,'operator_intent_changed':False,'job_token_reservation':262144,'previous_failed_comparison':'PRESERVED_UNCHANGED','no_old_mission_reset':True}
immutable_json(O/'preparation.json',r);immutable_json(N/'result.json',r);print(json.dumps(r))
