"""Actual initial context preflight and one source-bound LL intake; Conductor alone launches."""
from pathlib import Path
import json,os,subprocess,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/aspice-rcc-context-fixed-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import authz,operations,policy,product_role_trial
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.overnight import provision_order
from forge_factory.afo.durable import digest,immutable_json,immutable_bytes
from forge_factory.common import utc_now,sha256_file
from forge_factory.lrtx import stack,profile,swe1,structured
from forge_factory.llm_gateway import sanitize_request
from forge_factory.afo.diagnosis_packet import measure_request
from forge_factory import workorder as W
s=json.loads((O/'scope.json').read_text());assert digest(s)=='df87551ec7ad82c1b0e7bcabad40da9162157d2c68a6bc98db99eff71b7a7065'
assert time.time()<s['deadline_epoch'] and operations.Intent().read()['mode']=='RUNNING' and operations.Intent().read()['epoch']==58
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==s['source_revision'] and not subprocess.check_output(['git','-C',str(R),'status','--porcelain'])
# Input-only workspace: not a native execution or model capability result.
state=os.environ['FORGE_STATE_DIR'];events=os.environ.get('FORGE_EVENTS_DIR')
os.environ['FORGE_STATE_DIR']=str(O/'input-preflight-state');os.environ['FORGE_EVENTS_DIR']=str(O/'input-preflight-events')
prof=profile.load(s['profile']);ws,man=W.prepare(R/s['ll']['example'],'WO-F014-RCC-LL-CONTEXT-FIXED-PREFLIGHT-V2',purpose='ASPICE_ONLY')
man['local_profile']={'id':s['profile'],'version':prof['version'],'config_sha256':prof['_sha256']};(ws/'.forge-run/manifest.json').write_text(json.dumps(man))
token=structured.RECOVERY_WORKSPACE.set(ws);inv=swe1.inventory(ws);groups=swe1.groups(inv);assert groups and not inv['missing_sections'];rows=[]
for group in groups:
 packet=swe1.group_packet(ws,group,s['model']);body={'model':s['model'],'messages':packet['_messages'],'stream':True,'max_tokens':packet['output_reserve'],'stream_options':{'include_usage':True},'response_format':{'type':'json_schema','json_schema':{'name':'packet_output','strict':True,'schema':packet['output_schema']}}}
 effective=sanitize_request(body,policy=prof['gateway']['reasoning']);measure=measure_request(effective);total=measure['input_tokens']+effective['max_tokens'];assert total<=262144
 assert packet['accounting']['context_tokens']==262144 and packet['accounting']['context_basis']=='profile:'+s['profile']
 rows.append({'task':packet['task'],'request_sha256':digest(effective),'measurement':measure,'output_reserve':effective['max_tokens'],'conservative_reservation':total})
structured.RECOVERY_WORKSPACE.reset(token)
immutable_json(O/'initial-request-preflight-v2.json',{'status':'PASS_INITIAL_SWE1_GROUP_CONTEXT_ONLY','source_revision':s['source_revision'],'workspace':str(ws),'groups':len(groups),'inventory_items':len(inv['items']),'global_inventory_sha256':digest(inv),'missing_sections':inv['missing_sections'],'rows':rows,'maximum_conservative_reservation':max(r['conservative_reservation'] for r in rows),'generation_requests':0,'later_phase_context':'MEASURE_COMPLETE_ACTUAL_REQUESTS_AT_RUNTIME','capability':'NOT_QUALIFIED'})
os.environ['FORGE_STATE_DIR']=state
if events is None:os.environ.pop('FORGE_EVENTS_DIR',None)
else:os.environ['FORGE_EVENTS_DIR']=events
S=Store();I=operations.Intent();L=MissionLedger(S)
with I.lock():
 assert I.read()['mode']=='RUNNING' and I.read()['epoch']==58 and time.time()<s['deadline_epoch']
 assert not Executions(S).pending()
 with S.tx() as c:
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
 eff=policy.load(log=False);assert eff.mode=='PILOT' and eff.sha256==s['policy_sha256']
 assert stack.serving_instance(stack.settings(s['profile']))==json.loads((P/'deployment/aspice-rcc-pair-20261030-v1/allocation.json').read_text())['provider_instance']
 trial=json.loads((O/'trial.json').read_text());ref=json.loads((O/'trial-ref.json').read_text());assert digest(trial)==ref['sha256']
 immutable_json(P/'state'/ref['path'],trial)
 entry=json.loads((O/'entry.json').read_text());entry['mission']['admission_authorization_ref']=s['primary_authorization'];immutable_json(O/'entry-current-admission-authority.json',entry);envelope=entry['envelope'];immutable_bytes(R/envelope['input_manifest_ref'],(O/'launch.json').read_bytes());assert sha256_file(R/envelope['input_manifest_ref'])==envelope['manifest_sha256']
 before=L.snapshot(s['mission_id']);assert before==s['mission_before']
 provision_order(S,entry,eff,s['deadline_epoch']);assert L.for_order(entry['order_id'])==s['mission_id'] and L.snapshot(s['mission_id'])==before
 immutable_json(O/'intake.json',{'status':'ENROLLED_EXISTING_CONDUCTOR_OWNS_EXECUTION','order_id':entry['order_id'],'mission_id':s['mission_id'],'source_revision':s['source_revision'],'operator_epoch':58,'deadline_utc':s['deadline_utc'],'spent_counters_preserved_before_dispatch':True,'HAL':'NOT_SUBMITTED_DEPENDS_ON_VERIFIED_LL','capability':'EXPERIMENT_NOT_QUALIFIED','product_result':'NOT_YET_MEASURED','model_requests_by_enrolment':0,'at':utc_now()})
print((O/'intake.json').read_text())
