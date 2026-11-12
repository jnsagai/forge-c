from pathlib import Path
import json,subprocess,sys
A=Path(__file__).parent/'rcc-canonical-reconcile-signing'
sys.path.insert(0,'/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/operations/feature014/recovery-after-overnight-20261028/factory/python')
from forge_factory.afo import authz
from forge_factory.afo.durable import digest
scope=json.loads((A/'scope.json').read_text());assert digest(scope)=='a90483bdac34e445e72544fd6d92752af0c89e5114a351ae422ba1b97932870d'
assert scope['qualified_reconciler_revision']=='53e1234709eeaea91aaf681d1d5068659c85762a'
assert scope['candidate_commit']=='b64f64daf03aec12d72a5513fa322426cf9c93bd'
assert scope['expires_utc']=='2026-10-30T07:05:39Z' and scope['standing_signing_delegation']=='always approve it for now on automatically'
assert json.loads((A/'owner-approval.json').read_text())['scope_sha256']==digest(scope)
grant=json.loads((A/'authorization.json').read_text());assert not authz.schema_errors(grant)
assert grant['signed_runbook_ref']=='maintenance-commit-reconciliation-014:'+digest(scope)
assert grant['allowed_actions']==['recover_workorder'] and grant['scope']['order_ids']==[scope['request_id']]
message=A/'authorization-message.bin';assert message.read_bytes()==authz.message(grant)
keys=subprocess.check_output(['ssh-add','-L'],text=True).splitlines();allowed=(A/'allowed-signers').read_text()
matching=[key for key in keys if key.startswith('ssh-ed25519 ') and key.split()[1] in allowed]
assert len(matching)==1
pub=A/'agent-signing.pub';pub.write_text(matching[0]+'\n');pub.chmod(0o600)
assert not Path(str(message)+'.sig').exists()
subprocess.run(['ssh-keygen','-Y','sign','-f',str(pub),'-n',authz.NAMESPACE,str(message)],check=True,stdout=subprocess.DEVNULL)
assert authz.signature_valid(grant,Path(str(message)+'.sig'),A/'allowed-signers')
print(json.dumps({'status':'EXACT_EXISTING_EFFECT_RECOVERY_SIGNED','scope_sha256':digest(scope),'expires_utc':scope['expires_utc'],'deployment':False,'model_requests':0}))
