"""Use the existing SSH agent only for the exact prepared delegated continuation."""
import json,os,subprocess,sys
from pathlib import Path
A=Path(__file__).parent/'rcc-context-repair-signing'
sys.path.insert(0,'/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/operations/feature014/recovery-after-overnight-20261028/factory/python')
from forge_factory.afo import authz
from forge_factory.afo.durable import digest
s=json.loads((A/'scope.json').read_text());assert digest(s)=='0ef563a5f5e45f82ddf1d80d75dec19503535c1acdb847ac1ce748daa38bd00a';approval=json.loads((A/'owner-approval.json').read_text())
assert digest(s)==approval['scope_sha256'] and s['new_order_id']=='afo-7ab1af2aa4e1d7b4'
assert s['source_revision']=='b713e354b5c50744c549b1a9cada491c3ca017bd' and s['deadline_utc']=='2026-10-30T08:11:56Z'
assert s['standing_signing_delegation']=='always approve it for now on automatically'
keys=subprocess.check_output(['ssh-add','-L'],text=True).splitlines()
allowed=(A/'allowed-signers').read_text()
matching=[k for k in keys if k.startswith('ssh-ed25519 ') and k.split()[1] in allowed]
assert len(matching)==1,'EXACT_ALLOWED_AGENT_KEY_REQUIRED'
pub=A/'agent-signing.pub';pub.write_text(matching[0]+'\n');pub.chmod(0o600)
for label in ('primary','roles'):
 g=json.loads((A/(label+'-authorization.json')).read_text());assert not authz.schema_errors(g)
 m=A/(label+'-authorization-message.bin');assert m.read_bytes()==authz.message(g)
 assert g['policy_sha256']==s['policy_sha256'] and g['expires_utc']==s['deadline_utc']
 assert not Path(str(m)+'.sig').exists()
 subprocess.run(['ssh-keygen','-Y','sign','-f',str(pub),'-n',authz.NAMESPACE,str(m)],check=True,stdout=subprocess.DEVNULL)
 assert authz.signature_valid(g,Path(str(m)+'.sig'),A/'allowed-signers')
print(json.dumps({'status':'EXACT_TWO_RECORDS_SIGNED_AND_VERIFIED','scope_sha256':digest(s),'deadline_utc':s['deadline_utc'],'delegation':s['standing_signing_delegation'],'activation':False,'model_requests':0}))
