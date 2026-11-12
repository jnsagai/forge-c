"""Delegate-sign one finite existing four-question configuration; no activation or new source."""
from pathlib import Path
import copy,datetime,json,subprocess,sys
import yaml
A=Path(__file__).parent;B=A.parents[2];W=B/'operations/feature014/recovery-after-overnight-20261028';D=A/'stepwise-native-prepared';T=A/'stepwise-diagnosis-signing';P=Path('/mnt/data/forge-c/production-local-014');O=P/'deployment/q38-stepwise-protocol-20261030-v1'
sys.path.insert(0,str(W/'factory/python'))
from forge_factory.afo import authz,qualification as Q,semantic_proposal as S
from forge_factory.afo.durable import canonical,digest
from forge_factory.common import sha256_file
REV='12e601e4f53ab71b6d184ae19379faa1dd8f6e97';expiry='2026-10-30T13:52:52Z';deadline=1793368372.0
assert datetime.datetime.now(datetime.timezone.utc).timestamp()<deadline
prep=json.loads((D/'preparation.json').read_text());assert prep['source_revision']==REV and prep['model_requests']==0 and prep['grants_created']==0 and prep['case_count']==8 and prep['max_provider_requests']==32
m=json.loads((D/'medium/campaign-unsigned.json').read_text());assert m['source_revision']==REV and m['identity']['task_class']==S.TWO_STEP and Q.requests_per_job(m['identity'])==4
inp=json.loads((D/'medium/inputs.json').read_text());assert inp['generator_revision']['dirty'] is False and inp['model_configuration']['reasoning_effort']=='medium'
aid='AUTH-014-STEPWISE-Q38-MEDIUM-20261030-V1';requests=[]
for f in sorted((D/'medium/cases').glob('*/envelope.json')):
 e=json.loads(f.read_text());assert e['authorization_ref']==aid;requests.append(e['request_id'])
assert len(requests)==8
T.mkdir(mode=0o700);E=T/'medium';E.mkdir(mode=0o700)
tools={kind+'-stepwise-diagnosis.py':{'path':str(P/'deployment'/(kind+'-stepwise-diagnosis.py')),'sha256':sha256_file(A/(kind+'-stepwise-diagnosis.py'))} for kind in ('activate','run','continue')}
(T/'execution-tools.json').write_bytes(canonical(tools))
policy=yaml.safe_load((A/'non-thinking-speed-signing-v2/medium/policy.yaml').read_text());policy['authorization_ref']=aid
(E/'policy.yaml').write_text(yaml.safe_dump(policy,sort_keys=False));policysha=digest(policy)
mission={'mission_id':inp['mission_id'],'lineage':'owner:existing-stepwise-diagnosis:20261030','limits':{'deadline':deadline,'max_attempts':0,'max_corrections':0,'max_jobs':8,'max_requests':32,'max_tokens':sum(m['job_token_reservations'].values()),'max_tools':0}}
m['mission']=mission;m['inputs'].append({'path':str(O/'execution-tools.json'),'sha256':sha256_file(T/'execution-tools.json')});(E/'campaign.json').write_bytes(canonical(m));sha=digest(m)
ginfo={'authorization_ref':aid,'profile':inp['model_configuration']['profile'],'manifest_sha256':sha,'policy_sha256':policysha,'mission':mission,'mtp_draft':3}
scope={'schema':'forge-c/owner-stepwise-diagnosis-scope/1','purpose':'STEPWISE_DIAGNOSIS_CONFIGURATION_PILOT_ONLY','source_revision':REV,'grants':{'medium':ginfo},'execution_tools':tools,'existing_task_class':S.TWO_STEP,'max_requests_per_job':4,'starting_operator_epoch':96,'expires_utc':expiry,'deadline_renewed':False,'one_inference':True,'historical_missions_reset':False,'one_shot_failed_results_retained':True,'cases_previously_exposed':True,'incomplete_packet_unknown_only_grammar_disclosed':True,'no_product_or_fresh_role_qualification_claim':True,'source_promoted':False,'workability_goal':'make AFO workable on Qwen, then complete ASPICE LL/HAL examples','standing_signing_delegation':'always approve it for now on automatically','automatic_selection':False}
(T/'scope.json').write_bytes(canonical(scope));sh=digest(scope)
(T/'owner-approval.json').write_bytes(canonical({'scope_sha256':sh,'approved_by':'jefferson','authority':'Existing delegated signing and active AFO/Qwen workability goal; existing finite expiry unchanged','no_product_continuation':True}))
g=copy.deepcopy(json.loads((A/'non-thinking-speed-signing-v2/medium/authorization.json').read_text()));g.update(authorization_id=aid,approval_evidence_ref='owner-stepwise-diagnosis-20261030:'+sh,issued_utc=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'),expires_utc=expiry,policy_sha256=policysha,signature_ref=aid+'.sig',signed_runbook_ref='qualification-014:'+sha);g['scope']['order_ids']=requests
assert not authz.schema_errors(g)
(E/'authorization.json').write_bytes(canonical(g));msg=E/'authorization-message.bin';msg.write_bytes(authz.message(g))
allowed=A/'rcc-context-fixed-signing/allowed-signers';keys=subprocess.check_output(['ssh-add','-L'],text=True).splitlines();keys=[k for k in keys if k.startswith('ssh-ed25519 ') and k.split()[1] in allowed.read_text()];assert len(keys)==1
pub=T/'agent.pub';pub.write_text(keys[0]+'\n');pub.chmod(0o600)
subprocess.run(['ssh-keygen','-Y','sign','-f',str(pub),'-n',authz.NAMESPACE,str(msg)],check=True,stdout=subprocess.DEVNULL)
assert authz.signature_valid(g,Path(str(msg)+'.sig'),allowed)
print(json.dumps({'status':'STEPWISE_FINITE_SCOPE_SIGNED_NOT_ACTIVATED','scope_sha256':sh,'source_revision':REV,'expires_utc':expiry,'max_requests':32,'model_requests':0}))
