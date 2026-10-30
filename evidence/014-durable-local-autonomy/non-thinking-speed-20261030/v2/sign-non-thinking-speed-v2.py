"""Owner-delegated signing of three finite source-bound comparison scopes; no activation."""
from pathlib import Path
import copy,datetime,hashlib,json,subprocess,sys
import yaml
A=Path(__file__).parent;B=A.parents[2];W=B/'operations/feature014/recovery-after-overnight-20261028';D=A/'non-thinking-native-prepared-v2';T=A/'non-thinking-speed-signing-v2';P=Path('/mnt/data/forge-c/production-local-014');O=P/'deployment/q38-nonthink-speed-20261030-v2'
sys.path.insert(0,str(W/'factory/python'))
from forge_factory.afo import authz
from forge_factory.afo.durable import canonical,digest
REV='12e601e4f53ab71b6d184ae19379faa1dd8f6e97';expiry='2026-10-30T13:52:52Z';deadline=1793368372.0
assert datetime.datetime.now(datetime.timezone.utc).timestamp()<deadline
prep=json.loads((D/'preparation.json').read_text());assert prep['source_revision']==REV and prep['source_dirty'] is False
assert prep['efforts']==['xhigh','medium','none'] and prep['model_requests']==0 and prep['signed_grants_created']==0
T.mkdir(mode=0o700)
old=A/'q38-reasoning-speed-signing';grants={};records={};tools={}
for kind in ('activate','run','continue'):
 name=kind+'-non-thinking-speed-v2.py';raw=(A/name).read_bytes();tools[name]={'path':str(P/'deployment'/name),'sha256':hashlib.sha256(raw).hexdigest()}
(T/'execution-tools.json').write_bytes(canonical(tools))
for effort in ('none','medium','xhigh'):
 E=T/effort;E.mkdir(mode=0o700)
 manifest=json.loads((D/effort/'campaign-unsigned.json').read_text());assert manifest['source_revision']==REV and manifest['identity']['reasoning']==effort
 inp=json.loads((D/effort/'inputs.json').read_text());assert inp['campaign_id']=='q38-nothink-20261030-v2-'+effort and inp['count']==8
 aid='AUTH-014-REASONING-Q38-NOTHINK-20261030-V2-'+effort.upper()
 requests=[]
 for f in sorted((D/effort/'cases').glob('*/envelope.json')):
  envelope=json.loads(f.read_text());assert envelope['authorization_ref']==aid;requests.append(envelope['request_id'])
 assert len(requests)==8
 policy=yaml.safe_load((old/'xhigh/policy.yaml').read_text());policy['authorization_ref']=aid
 raw=yaml.safe_dump(policy,sort_keys=False).encode();(E/'policy.yaml').write_bytes(raw);policysha=digest(policy)
 mids={v['mission_id'] for v in manifest['jobs'].values()};assert mids=={'qualification-014-q38-nothink-20261030-v2-'+effort}
 mission={'mission_id':next(iter(mids)),'lineage':'owner:explicit-thinking-off-speed:20261030:'+effort,'limits':{'deadline':deadline,'max_attempts':0,'max_corrections':0,'max_jobs':8,'max_requests':8,'max_tokens':sum(manifest['job_token_reservations'].values()),'max_tools':0}}
 manifest['mission']=mission;manifest['inputs'].append({'path':str(O/'execution-tools.json'),'sha256':hashlib.sha256((T/'execution-tools.json').read_bytes()).hexdigest()})
 (E/'campaign.json').write_bytes(canonical(manifest));sha=digest(manifest)
 grants[effort]={'authorization_ref':aid,'profile':inp['model_configuration']['profile'],'manifest_sha256':sha,'policy_sha256':policysha,'mission':mission,'mtp_draft':3}
 g=copy.deepcopy(json.loads((old/'xhigh/authorization.json').read_text()))
 g.update(authorization_id=aid,issued_utc=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'),expires_utc=expiry,policy_sha256=policysha,signature_ref=aid+'.sig',signed_runbook_ref='qualification-014:'+sha)
 g['scope']['order_ids']=requests;records[effort]=g
scope={'schema':'forge-c/owner-non-thinking-speed-scope/1','purpose':'NON_THINKING_SPEED_AND_CONTEXT_DIAGNOSIS_PILOT_ONLY','source_revision':REV,'grants':grants,'execution_tools':tools,'effort_order':['none','medium','xhigh'],'expires_utc':expiry,'deadline_renewed':False,'historical_missions_reset':False,'one_inference':True,'precision':'Q8_0','kv':'f16','mtp_draft':3,'context_tokens':262144,'output_ceiling_per_request':34816,'cases_previously_exposed':True,'fresh_holdout_qualification_claimed':False,'production_retry':False,'predecessor_failed_scope':'ae16935fbde8ac0aa5887d556f1a1b530d02190916869024d5010b7bda1cc0d7','predecessor_failure':'YAML_BYTES_INSTEAD_OF_CANONICAL_POLICY_HASH_BEFORE_ANY_MODEL_OR_MISSION','automatic_selection':False,'starting_operator_epoch':89,'standing_signing_delegation':'always approve it for now on automatically','explicit_owner_instruction':'lets try also enable_thinking=false'}
(T/'scope.json').write_bytes(canonical(scope));scopehash=digest(scope)
(T/'owner-approval.json').write_bytes(canonical({'scope_sha256':scopehash,'approved_by':'jefferson','authority':'Existing delegated SSH-agent signing plus explicit owner-requested non-thinking trial','deadline_renewed':False,'no_product_continuation':True}))
allowed=A/'rcc-context-fixed-signing/allowed-signers';keys=subprocess.check_output(['ssh-add','-L'],text=True).splitlines();matching=[k for k in keys if k.startswith('ssh-ed25519 ') and k.split()[1] in allowed.read_text()];assert len(matching)==1
pub=T/'agent.pub';pub.write_text(matching[0]+'\n');pub.chmod(0o600)
for effort,g in records.items():
 E=T/effort;g['approval_evidence_ref']='owner-nonthinking-speed-20261030:'+scopehash
 assert not authz.schema_errors(g)
 (E/'authorization.json').write_bytes(canonical(g));msg=E/'authorization-message.bin';msg.write_bytes(authz.message(g))
 subprocess.run(['ssh-keygen','-Y','sign','-f',str(pub),'-n',authz.NAMESPACE,str(msg)],check=True,stdout=subprocess.DEVNULL)
 assert authz.signature_valid(g,Path(str(msg)+'.sig'),allowed)
print(json.dumps({'status':'EXACT_FINITE_DELEGATED_SCOPES_SIGNED_NOT_ACTIVATED','scope_sha256':scopehash,'source_revision':REV,'expires_utc':expiry,'model_requests':0,'mission_reset':False}))
