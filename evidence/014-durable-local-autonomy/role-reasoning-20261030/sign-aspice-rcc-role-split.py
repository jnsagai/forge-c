"""Sign only this explicitly disclosed finite scope under standing owner delegation."""
from pathlib import Path
import json,subprocess,sys
A=Path(__file__).parent/'aspice-rcc-role-split-signing/aspice-rcc-role-split-20261030-v1'
sys.path.insert(0,"/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/operations/feature014/recovery-after-overnight-20261028/factory/python")
from forge_factory.afo import authz
from forge_factory.afo.durable import digest
s=json.loads((A/'scope.json').read_text());assert digest(s)=='7a3aa5041f60f51edd91a3458406fe463ff7b38a80de7c0a5550dfc028007533'
assert s['source_revision']=='7fbefc40e0912e15aabeb70ca6b85932085b1b27' and s['deadline_utc']=='2026-10-30T19:40:00Z'
assert s['standing_signing_delegation']=='always approve it for now on automatically' and not s['historical_counters_reset'] and not s['non_time_limits_changed']
assert s['functional_gates_blocking'] and not s['advisory_continue']
assert json.loads((A/'owner-approval.json').read_text())['scope_sha256']==digest(s)
keys=subprocess.check_output(['ssh-add','-L'],text=True).splitlines();allowed=(A/'allowed-signers').read_text();matching=[k for k in keys if k.startswith('ssh-ed25519 ') and k.split()[1] in allowed];assert len(matching)==1
pub=A/'agent.pub';pub.write_text(matching[0]+'\n');pub.chmod(0o600)
for label in ('primary','roles'):
 g=json.loads((A/(label+'-authorization.json')).read_text());assert not authz.schema_errors(g) and g['policy_sha256']==s['policy_sha256'] and g['expires_utc']==s['deadline_utc']
 assert g['scope']['order_ids']==[s['ll']['request_id'],s['hal']['request_id']]
 if label=='primary':assert g['signed_runbook_ref']=='factory-revision:'+s['source_revision']
 elif label=='roles':assert g['signed_runbook_ref']=='qualification-product-014:'+digest(json.loads((A/'trial.json').read_text()))
 else:assert g['signed_runbook_ref']=='mission-deadline-extension-014:'+digest(json.loads((A/'time-document.json').read_text()))
 msg=A/(label+'-authorization-message.bin');assert msg.read_bytes()==authz.message(g)
 sig=Path(str(msg)+'.sig')
 if not sig.exists():subprocess.run(['ssh-keygen','-Y','sign','-f',str(pub),'-n',authz.NAMESPACE,str(msg)],check=True,stdout=subprocess.DEVNULL)
 assert authz.signature_valid(g,sig,A/'allowed-signers')
receipt={'status':'TWO_EXACT_RECORDS_SIGNED_VERIFIED','scope_sha256':digest(s),'expires_utc':s['deadline_utc'],'old_grants_renewed':False,'activation':False}
(A/'signing-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))

