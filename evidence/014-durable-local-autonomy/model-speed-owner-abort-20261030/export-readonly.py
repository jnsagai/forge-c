"""Read-only, content-addressed export of frozen speed inputs and completed designated results."""
from pathlib import Path
import hashlib,io,json,sys,tarfile
O=Path('/mnt/data/forge-c/production-local-014/deployment/q38-reasoning-speed-20261030-v1')
files={}
def add(path,name=None):
 if not path.exists():return
 assert path.is_file() and not path.is_symlink()
 raw=path.read_bytes();assert len(raw)<8*1024*1024
 files[name or path.relative_to(O).as_posix()]=raw
for name in ('scope.json','owner-approval.json','preparation.json','medium-comparison-plan.json'):add(O/name)
for p in (O/'controls').glob('*.json'):add(p)
for effort in ('xhigh','medium'):
 E=O/effort
 for name in ('campaign.json','inputs.json','policy.yaml','authorization.json','authorization-message.bin.sig','protocol-report.json','completion.json','progress.json','effective-native-settings.json','activation.json','benchmark-resume.json','activation-exit.json','driver-exit.json'):add(E/name)
 for group in ('metrics','results','cases'):
  for p in sorted((E/group).rglob('*')):
   if p.is_file() and p.suffix in ('.json','.md','.c'):add(p)
 for p in (E/'reference').glob('*'):
  if p.is_file() and p.suffix in ('.json','.c'):add(p)
 for p in (E/'metrics').glob('*.json'):
  r=json.loads(p.read_text());ref=r.get('independent_audit') or {}
  if ref.get('path'):
   audit=Path(ref['path']);assert audit.resolve().is_relative_to(Path('/mnt/data/forge-c/production-local-014/state/lrtx/qualification-audits'));assert hashlib.sha256(audit.read_bytes()).hexdigest()==ref['sha256'];add(audit,'independent-audits/'+effort+'/'+audit.name)
assert sum(map(len,files.values()))<64*1024*1024
manifest={'schema':'forge-c/private-speed-transfer/1','scope':'FROZEN_INPUTS_DESIGNATED_RESULTS_NUMERIC_TIMING_NO_HIDDEN_REASONING','complete':{e:(O/e/'completion.json').exists() for e in ('xhigh','medium')},'files':{n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in files.items()}}
files['transfer-manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:
 for n,b in files.items():
  h=tarfile.TarInfo(n);h.size=len(b);h.mode=0o600;t.addfile(h,io.BytesIO(b))

