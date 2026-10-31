"""Use the existing SSH agent only for the exact prepared delegated continuation."""
import json,os,subprocess,sys
from pathlib import Path
A=Path(__file__).parent/'rcc-context-completion-signing'
sys.path.insert(0,'/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/operations/feature014/recovery-after-overnight-20261028/factory/python')
from forge_factory.afo import authz
from forge_factory.afo.durable import digest
s=json.loads((A/'scope.json').read_text());assert digest(s)=='858bd287930424bbbb9b9cc2879641a8aa4221d4135377dd9be30d15c39228bf';approval=json.loads((A/'owner-approval.json').read_text())
assert digest(s)==approval['scope_sha256'] and s['new_order_id']=='afo-7e653513a54375a5'
assert s['source_revision']=='ab46545c1cfb7ffd90fb09715b6715b7d21ad242' and s['deadline_utc']=='2026-10-30T08:11:56Z'
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
