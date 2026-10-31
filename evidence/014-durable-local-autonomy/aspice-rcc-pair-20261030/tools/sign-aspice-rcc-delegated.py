"""Sign only the exact finite prepared ASPICE scope under standing owner delegation."""
import json,subprocess,sys
from pathlib import Path
A=Path(__file__).parent/'aspice-rcc-pair-signing'
sys.path.insert(0,'/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/operations/feature014/recovery-after-overnight-20261028/factory/python')
from forge_factory.afo import authz
from forge_factory.afo.durable import digest
s=json.loads((A/'scope.json').read_text())
assert digest(s)=='3e60ba7507f085996b6ae838878a37f4bf5ae2d246fe4d4573c8ed137e519b47'
assert s['source_revision']=='b713e354b5c50744c549b1a9cada491c3ca017bd'
assert s['deadline_utc']=='2026-10-30T08:11:56Z'
assert s['standing_signing_delegation']=='always approve it for now on automatically'
approval=json.loads((A/'owner-approval.json').read_text());assert approval['scope_sha256']==digest(s)
label=sys.argv[1];assert label in ('primary','capacity','time','roles')
g=json.loads((A/(label+'-authorization.json')).read_text());assert not authz.schema_errors(g)
assert g['expires_utc']==s['deadline_utc'] and g['policy_sha256']==s['policy_sha256']
if label=='primary':assert g['signed_runbook_ref']=='factory-revision:'+s['source_revision']
elif label in ('capacity','time'):
 doc=json.loads((A/(label+'-document.json')).read_text())
 assert doc['mission_id']==s['mission_id'] and doc['authorization_ref']==g['authorization_id']
 prefix='mission-capacity-amendment-014:' if label=='capacity' else 'mission-deadline-extension-014:'
 assert g['signed_runbook_ref']==prefix+digest(doc)
 if label=='capacity':assert doc['limits']==s['new_non_time_limits']
 else:assert doc['deadline_epoch']==s['deadline_epoch']
else:
 doc=json.loads((A/'trial.json').read_text())
 assert g['signed_runbook_ref']=='qualification-product-014:'+digest(doc)
 assert doc['source_revision']==s['source_revision'] and doc['profile']==s['profile']
 assert doc['deadline_epoch']==s['deadline_epoch'] and doc['order_ids']==[s['ll']['order_id']]
m=A/(label+'-authorization-message.bin');assert m.read_bytes()==authz.message(g)
sig=Path(str(m)+'.sig')
if not sig.exists():
 keys=subprocess.check_output(['ssh-add','-L'],text=True).splitlines();allowed=(A/'allowed-signers').read_text()
 matching=[k for k in keys if k.startswith('ssh-ed25519 ') and k.split()[1] in allowed]
 assert len(matching)==1,'EXACT_ALLOWED_AGENT_KEY_REQUIRED'
 pub=A/'agent-signing.pub';pub.write_text(matching[0]+'\n');pub.chmod(0o600)
 subprocess.run(['ssh-keygen','-Y','sign','-f',str(pub),'-n',authz.NAMESPACE,str(m)],check=True,stdout=subprocess.DEVNULL)
assert authz.signature_valid(g,sig,A/'allowed-signers')
print(json.dumps({'status':'EXACT_RECORD_SIGNED_VERIFIED','label':label,'scope_sha256':digest(s),'deadline_utc':s['deadline_utc'],'activation':False}))
