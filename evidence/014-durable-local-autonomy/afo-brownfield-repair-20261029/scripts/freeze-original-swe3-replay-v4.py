"""Freeze existing failed-phase inputs for independent replay; never modify original workproducts."""
from pathlib import Path
import hashlib,json,os,shutil,sys,time
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/afo-repair-live-20261029-v4';W=P/'state/workorders/WO-AFO-774900b297bdde37-a1/workspace'
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.durable import immutable_json
from forge_factory.common import sha256_file,utc_now
F=P/'deployment/afo-repair-trial-20261029-v2/model-input/source-evidence/frozen-swe3-transfer.json';frozen=json.loads(F.read_text());assert frozen['current_baseline_verified']
assert frozen['baseline']['phase']=='SWE.3' and frozen['factory_revision']['commit']=='9b4c390e1605d11c4865bdeea382df74a0078692'
assert all(sha256_file(W/rel)==sha for rel,sha in frozen['baseline']['files'].items())
files=[]
for rel in ('workproducts/SWE.1','workproducts/SWE.2','workproducts/SWE.3','software','configuration','inputs'):
 root=W/rel
 if not root.exists():continue
 for p in root.rglob('*'):
  assert not p.is_symlink(),str(p)
  if p.is_file():files.append(p)
files.append(W/'.forge-run/manifest.json');assert sum(p.stat().st_size for p in files)<256*1024**2
D=O/'original-swe3-replay-input';D.mkdir(mode=0o700);out=D/'workspace';rows=[]
for p in files:
 rel=p.relative_to(W);q=out/rel;q.parent.mkdir(parents=True,exist_ok=True);raw=p.read_bytes();q.write_bytes(raw);q.chmod(0o444);rows.append({'path':str(rel),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
assert all(sha256_file(out/rel)==sha for rel,sha in frozen['baseline']['files'].items())
report={'schema':'forge-c/original-swe3-replay-input/1','at':utc_now(),'source_workspace':str(W),'source_order_id':frozen['order_id'],'source_job_id':frozen['job_id'],'source_runtime_revision':frozen['factory_revision']['commit'],'frozen_phase_record_sha256':sha256_file(F),'frozen_baseline_hash':frozen['baseline']['baseline_hash'],'baseline_files_verified':len(frozen['baseline']['files']),'files':rows,'bytes':sum(r['bytes'] for r in rows),'input_root':str(out),'original_source_modified':False,'model_requests':0,'grader_results':'NOT_RUN','scope':'Private independent replay input; no reference repair, grader or previous correctness outcome sent to Qwen'}
immutable_json(D/'inventory.json',report);print(json.dumps({k:v for k,v in report.items() if k!='files'}))
