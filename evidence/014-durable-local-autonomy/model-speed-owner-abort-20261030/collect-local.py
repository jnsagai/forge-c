from pathlib import Path
import datetime,hashlib,io,json,os,subprocess,tarfile,time
A=Path(__file__).parent;B=A.parents[2];D=B/'inspection/feature014/2026-10-30-qwen/model-speed-pilot'
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no','-o','ControlMaster=auto','-o','ControlPersist=300','-o','ControlPath='+str(B/'fc014-ssh.sock'),'omniverse2@100.118.28.92','/mnt/data/forge-c/production-local-014/venv/bin/python /mnt/data/forge-c/production-local-014/deployment/export-q38-speed-readonly.py']
D.mkdir(parents=True,exist_ok=True,mode=0o700);deadline=datetime.datetime(2026,10,30,14,2,52,tzinfo=datetime.timezone.utc).timestamp()
while time.time()<deadline:
 try:
  result=subprocess.run(SSH,capture_output=True,timeout=45,check=True);assert len(result.stdout)<64*1024*1024
  with tarfile.open(fileobj=io.BytesIO(result.stdout),mode='r:gz') as t:
   members=t.getmembers();assert all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members)
   manifest=json.load(t.extractfile('transfer-manifest.json'))
   for name,rec in manifest['files'].items():
    raw=t.extractfile(name).read();assert len(raw)==rec['bytes'] and hashlib.sha256(raw).hexdigest()==rec['sha256']
   t.extractall(D,filter='data')
  stamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
  receipt={'at':stamp,'status':'ALL_HASHES_VERIFIED','files':len(manifest['files']),'archive_sha256':hashlib.sha256(result.stdout).hexdigest(),'complete':manifest['complete'],'destination':str(D)}
  with (A/'q38-speed-local-transfer-history.jsonl').open('a') as f:f.write(json.dumps(receipt)+'\n')
  (D/'local-transfer-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
  import importlib.util
  spec=importlib.util.spec_from_file_location('speed_report',A/'report-q38-speed.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.write(D)
  print(json.dumps(receipt),flush=True)
  if all(manifest['complete'].values()):break
 except Exception as exc:print(json.dumps({'status':'TRANSFER_RETRY','error_type':type(exc).__name__}),flush=True)
 time.sleep(30)

