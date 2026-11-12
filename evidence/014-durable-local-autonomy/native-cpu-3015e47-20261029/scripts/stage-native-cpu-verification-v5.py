import hashlib,json,tarfile,os
from pathlib import Path,PurePosixPath
P=Path('/mnt/data/forge-c/production-local-014');archive=P/'deployment/native-core-stop-3015e47-v5.tar';N=P/'deployment/qualification-core-stop-3015e47-v5'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='17dc46c339ae2d978611ab5583f8232116353e20978f887c6ca5f97e971c0ba1'
assert not N.exists();N.mkdir(mode=0o700)
with tarfile.open(archive) as tar:
 members=tar.getmembers();names=[m.name for m in members];assert len(names)==len(set(names))
 for m in members:
  p=PurePosixPath(m.name);assert m.isfile() and not p.is_absolute() and '..' not in p.parts
 manifest=json.load(tar.extractfile('preparation.json'))
 assert set(names)==set(manifest['files'])|{'preparation.json'}
 for m in members:
  raw=tar.extractfile(m).read()
  if m.name!='preparation.json':
   item=manifest['files'][m.name];assert len(raw)==item['bytes'] and hashlib.sha256(raw).hexdigest()==item['sha256']
  path=N/m.name;path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
  with path.open('xb') as f:f.write(raw)
  path.chmod(0o600)
archive.chmod(0o600)
print(json.dumps({'status':'CPU_VERIFICATION_STAGED','source_revision':manifest['source_revision'],'files':len(names),'model_requests':0,'operator_resume':False,'source_activation':False}))

