
from pathlib import Path
import subprocess,json,shutil,hashlib
N=Path('/mnt/data/forge-c/native-artifacts-014-20261030-v1');D=Path('/mnt/data/forge-c/delivery-first-014-20261030-v1')
Q=D/'source';base=N/'source-gateway-71906039';bundle=N/'delivery-first-155553dd.bundle'
rev='155553dd43da45d7ab1a7bbfb5367123494e2d85';D.mkdir(mode=0o700,exist_ok=True)
def git(*args):return subprocess.check_output(['git',*args],text=True).strip()
if not Q.exists():
 subprocess.run(['git','clone','--shared','--no-checkout',str(base),str(Q)],check=True,capture_output=True)
 subprocess.run(['git','-C',str(Q),'fetch',str(bundle),'HEAD'],check=True,capture_output=True)
 subprocess.run(['git','-C',str(Q),'checkout','--detach',rev],check=True,capture_output=True)
assert git('-C',str(Q),'rev-parse','HEAD')==rev
example=Q/'examples/0014g-st-crc-idr-qwen-delivery';spec=json.loads((example/'workorder.json').read_text());copied=[]
for item in spec['inputs']:
 p=(example/item['path']).resolve()
 assert p.is_relative_to(Q.resolve())
 if not p.is_file():
  rel=p.relative_to(Q);src=base/rel
  assert src.is_file(),str(rel)
  p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,p)
 copied.append({'path':str(p.relative_to(Q)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size})
assert not git('-C',str(Q),'status','--porcelain','--untracked-files=no')
out={'source_revision':rev,'source_clean':True,'input_files':copied,'model_calls':0,'new_inference_started':False}
(D/'source-preparation.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))

