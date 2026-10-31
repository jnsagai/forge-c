import hashlib,json,tarfile,os
from pathlib import Path,PurePosixPath
P=Path('/mnt/data/forge-c/production-local-014');archive=P/'deployment/native-swe6-stop-3015e47-v4.tar';N=P/'deployment/qualification-swe6-stop-3015e47-v4'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='fa5a155426b21b967feb8708cc33d38f3afa6d5df1e78be70bef0db452491c9b'
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

