"""Read-only verified transfer of native preparation; no activation/signing/inference."""
from pathlib import Path
import hashlib,io,json,subprocess,tarfile
A=Path(__file__).parent;B=A.parents[2];D=A/'stepwise-native-prepared'
script="""from pathlib import Path
import hashlib,io,json,sys,tarfile
P=Path('/mnt/data/forge-c/production-local-014');N=P/'deployment/stepwise-preparation-20261030-v1/result.json'
if not N.exists():raise SystemExit(3)
r=json.loads(N.read_text());assert r['status']=='PREPARED_NOT_RUN' and r['model_requests']==0
O=P/'deployment/q38-stepwise-protocol-20261030-v1';files={}
for f in O.rglob('*'):
 if f.is_file() and f.suffix in ('.json','.md','.c'):
  assert not f.is_symlink() and f.stat().st_size<8*1024*1024;files[f.relative_to(O).as_posix()]=f.read_bytes()
assert sum(map(len,files.values()))<64*1024*1024
manifest={'files':{n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in files.items()}}
files['prepared-transfer-manifest.json']=(json.dumps(manifest,indent=2)+'\\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:
 for n,b in files.items():
  h=tarfile.TarInfo(n);h.size=len(b);h.mode=0o600;t.addfile(h,io.BytesIO(b))
"""
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no','-o','ControlPath='+str(B/'fc014-ssh.sock'),'omniverse2@100.118.28.92','/mnt/data/forge-c/production-local-014/venv/bin/python -']
r=subprocess.run(SSH,input=script.encode(),capture_output=True,timeout=45)
if r.returncode==3:print(json.dumps({'status':'NOT_READY_NATIVE_PREPARATION_PENDING'}));raise SystemExit(3)
assert r.returncode==0, r.stderr.decode()[-1000:]
D.mkdir(mode=0o700)
with tarfile.open(fileobj=io.BytesIO(r.stdout),mode='r:gz') as t:
 assert all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in t.getmembers())
 manifest=json.load(t.extractfile('prepared-transfer-manifest.json'))
 for n,ref in manifest['files'].items():
  raw=t.extractfile(n).read();assert len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256']
 t.extractall(D,filter='data')
(A/'stepwise-native-prepared.tar.gz').write_bytes(r.stdout)
print(json.dumps({'status':'PREPARED_NATIVE_INPUTS_HASH_VERIFIED','files':len(manifest['files']),'archive_sha256':hashlib.sha256(r.stdout).hexdigest()}))
