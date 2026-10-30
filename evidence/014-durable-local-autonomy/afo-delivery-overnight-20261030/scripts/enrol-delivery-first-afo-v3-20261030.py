"""Enroll the frozen real product order through existing AFO intake, with no model call."""
from pathlib import Path
import json,os,sys,time,subprocess
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1');Q=E/'source';O=E/'control/delivery-first-afo-authority-20261030-v3'
os.environ.update(json.loads((E/'control/runtime-env-v5.json').read_text()));sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.afo import authz,policy,authority,contracts,product_role_trial,scheduler
from forge_factory.afo.operations import Intent
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.durable import digest,immutable_json
from forge_factory.common import utc_now,sha256_file
from forge_factory.lrtx import profile
from forge_factory import workorder as W,delivery_first as D,development_execution as X
s=json.loads((O/'scope.json').read_text());assert time.time()<s['deadline_epoch']
assert subprocess.check_output(['git','-C',str(Q),'rev-parse','HEAD'],text=True).strip()==s['source_revision']
assert not subprocess.check_output(['git','-C',str(Q),'status','--porcelain','--untracked-files=no'],text=True).strip()
assert os.readlink('/proc/self/ns/net')==json.loads((E/'run/services.json').read_text())['netns']
actual_profile=profile.select(s['profile'],model=s['model'],provider='ollama',code_model=None,acp_authors=None,acp_inspectors=None)
eff=policy.load();assert eff.mode=='PILOT' and eff.sha256==s['policy_sha256']
g=json.loads((O/'roles-authorization.json').read_text())
assert authz.signature_valid(g,O/'roles-authorization-message.bin.sig',E/'control/allowed-signers')
from forge_factory.afo.durable import immutable_bytes
immutable_json(E/'control/authorizations'/(g['authorization_id']+'.json'),g)
immutable_bytes(E/'control/authorizations'/g['signature_ref'],(O/'roles-authorization-message.bin.sig').read_bytes())
ref=json.loads((O/'trial-ref.json').read_text());trial=json.loads((O/'trial.json').read_text());assert digest(trial)==ref['sha256']
assert sha256_file(Path(trial['context_allocation_ref']['path']))==trial['context_allocation_ref']['sha256']
immutable_json(E/'state'/ref['path'],trial)
launch={'example':s['example'],'profile':s['profile'],'model_profile':s['model'],'model':s['model'],'provider':'ollama',
 'purpose':'QM','evaluation_holdout':True,'product_role_trial':ref,'product_attempt_token_reservations':[s['current_job_token_reservation']],
 'mission_id':s['mission_id'],'scope_sha256':digest(s),'candidate_reuse':False}
relative='.forge-run/delivery-first-afo/launch-'+s['request_id']+'.json';mpath=Q/relative;immutable_json(mpath,launch)
envelope={'schema_version':'1.0','request_id':s['request_id'],'tenant_scope':s['tenant_scope'],
 'manifest_sha256':sha256_file(mpath),'input_manifest_ref':relative,'approved_by':'jefferson',
 'authorization_ref':s['primary_authorization'],'driver_class':'LL','target':'STM32N6 Cortex-M55 CRC IDR two-function development',
 'safety_scope':'QM DEVELOPMENT; NO SAFETY OR PRODUCTION RELEASE CLAIM','model_profile':s['model'],
 'submitted_utc':utc_now(),'priority':'NORMAL','deadline_utc':s['deadline_utc'],'git_revision':s['source_revision']}
contracts.require('work-order',envelope)
S=Store();L=MissionLedger(S)
assert L.snapshot(s['mission_id'])==json.loads((E/'control/mission-before-v3.json').read_text())
L.link(s['mission_id'],s['order_id'])
intent=Intent()
with intent.lock():
 assert intent.read()['mode']=='RUNNING' and intent.read()['epoch']==4
 oid,created=S.submit(envelope,repo=Q,max_queued=100,
  approve=lambda _: (authority.decide('submit_workorder',{'order_id':s['request_id'],'driver_class':'LL','model':s['model']},afo=eff).allow,'SIGNED_SCOPED_DEVELOPMENT'))
 assert oid==s['order_id']
job={'order_id':oid,'profile':s['profile'],'model':s['model'],'model_digest':s['model_digest'],'precision':'Q8_0',
 'factory_revision':{'commit':s['source_revision'],'dirty':False}}
product_role_trial.authorized(ref,job,eff)
ws,man=W.prepare(Q/s['example'],'WO-DF-AFO-PREFLIGHT-20261030-03',purpose='QM',execution_policy=X.DEMO)
D.preflight(ws)
preflight=product_role_trial.preflight(ws,job,[])
assert preflight['generation_performed'] is False
issues=scheduler.preflight(S.order(oid),eff,S);assert not issues,issues
record={'at':utc_now(),'status':'ENROLLED_NO_GENERATION_YET','order_id':oid,'created':created,
 'source_revision':s['source_revision'],'scope_sha256':digest(s),'role_trial_sha256':ref['sha256'],
 'namespace_preflight':actual_profile['enforcement']['network'],'scheduler_preflight':'PASS',
 'role_request_inventory_preflight':preflight,'model_requests':0,'operations_epoch':4,
 'mission_before':L.snapshot(s['mission_id']),'deadline_utc':s['deadline_utc']}
immutable_json(E/'control/enrolment-v3.json',record)
print(json.dumps({k:record[k] for k in ('status','order_id','source_revision','scheduler_preflight','model_requests','deadline_utc')}))

