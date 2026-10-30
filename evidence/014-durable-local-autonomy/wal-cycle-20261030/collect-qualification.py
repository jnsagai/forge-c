"""Collect the one post-MTP CPU qualification privately; no remote write or model authority."""
from pathlib import Path
import datetime,hashlib,io,json,subprocess,tarfile,time
A=Path(__file__).parent;B=A.parents[2];D=B/'inspection/feature014/2026-10-30-qwen/wal-session-qualification'
script="""from pathlib import Path
import io,json,sys,tarfile,hashlib
P=Path('/mnt/data/forge-c/production-local-014');N=P/'deployment/wal-session-followup-a7804054-v1'
if not (N/'result.json').exists():raise SystemExit(3)
roots=[N,P/'deployment/wal-session-qualification-window-epoch94-v1',P/'deployment/qualification-wal-session-a7804054-epoch95-v1']
files={}
for root in roots:
 for relative in ('result.json','window.log','qualification.log','provenance.json','pytest.log','receipts/pytest.xml'):
  p=root/relative
  if p.is_file():
   assert not p.is_symlink();files[root.name+'/'+relative]=p.read_bytes()
manifest={'files':{n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in files.items()}}
files['transfer-manifest.json']=(json.dumps(manifest,indent=2)+'\\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:
 for n,b in files.items():
  h=tarfile.TarInfo(n);h.size=len(b);h.mode=0o600;t.addfile(h,io.BytesIO(b))
"""
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no','-o','ControlMaster=auto','-o','ControlPersist=300','-o','ControlPath='+str(B/'fc014-ssh.sock'),'omniverse2@100.118.28.92','/mnt/data/forge-c/production-local-014/venv/bin/python -']
deadline=datetime.datetime(2026,10,30,14,15,tzinfo=datetime.timezone.utc).timestamp()
while time.time()<deadline:
 result=subprocess.run(SSH,input=script.encode(),capture_output=True,timeout=45)
 if result.returncode==0:
  D.mkdir(parents=True,exist_ok=True,mode=0o700)
  with tarfile.open(fileobj=io.BytesIO(result.stdout),mode='r:gz') as t:
   members=t.getmembers();assert all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members)
   manifest=json.load(t.extractfile('transfer-manifest.json'))
   for name,ref in manifest['files'].items():
    raw=t.extractfile(name).read();assert len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256']
   t.extractall(D,filter='data')
  (D/'qualification-results.tar.gz').write_bytes(result.stdout)
  print(json.dumps({'status':'ALL_QA_ARTIFACT_HASHES_VERIFIED','files':len(manifest['files']),'destination':str(D)}),flush=True);break
 if result.returncode not in (0,3):print(json.dumps({'status':'READ_ONLY_TRANSFER_RETRY','returncode':result.returncode}),flush=True)
 time.sleep(30)

