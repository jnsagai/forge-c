
from pathlib import Path
import json,sys,time,os
R=Path('/mnt/data/forge-c/delivery-first-014-20261030-v1');Q=R/'source';N=R/'fixture-only'
os.environ['FORGE_REPO_ROOT']=str(Q);sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.fabro.client import FabroClient,load_token,run_status
from forge_factory.afo.durable import immutable_json
from forge_factory.common import utc_now
d=json.loads((N/'launch.json').read_text());out=N/'context-overflow-stop.json'
with FabroClient(base_url='http://127.0.0.1:32403',token=load_token(str(N/'fabro/storage')),timeout=15) as c:
 if out.exists():print(out.read_text());raise SystemExit(0)
 immutable_json(N/'context-overflow-stop-intent.json',{'at':utc_now(),'native_id':d['native_id'],'reason':'MEASURED_INITIAL_CONTEXT_OUTPUT_RESERVE_OVERFLOW','real_qwen_generation_calls':0})
 status=run_status(c.get_run(d['native_id']))
 response=c.cancel(d['native_id']) if status=='RUNNING' else None
 for _ in range(20):
  status=run_status(c.get_run(d['native_id']))
  if status in ('SUCCEEDED','FAILED','CANCELLED','CANCELED'):break
  time.sleep(0.5)
 rec={'at':utc_now(),'native_id':d['native_id'],'response':response,'native_status':status,
 'reason':'EXTERNAL_SUPERSESSION_OF_FIXTURE_CONTEXT_CONFIGURATION','real_qwen_generation_calls':0,
 'fixture_shim_generation_calls':len((N/'fixture-requests.jsonl').read_text().splitlines()) if (N/'fixture-requests.jsonl').is_file() else 0}
 immutable_json(out,rec);print(json.dumps(rec))
 if status not in ('SUCCEEDED','FAILED','CANCELLED','CANCELED'):raise SystemExit(2)
from forge_factory.lrtx import stack,profile
prof=profile.load('local-rtx-v2-omniverse2-q38-delivery-first')
ports={**prof['deployment']['ports'],'gateway':11460,'fabro':32403}
os.environ.update(stack.envmap({'profile':prof,'root':N,'ports':ports}))
from forge_factory.release.finalize import finalize,verify_archive
package=finalize(Path(d['workspace']),d['work_order'],d['native_id'])
immutable_json(N/'context-overflow-package.json',{'package':package,'integrity':verify_archive(Path(package['archive'])),'classification':'FIXTURE_ONLY_INFRA_CONTEXT_NOT_QWEN_MODEL_FAILURE'})
print(json.dumps({'package_status':package['package_status'],'gap_count':package['gap_count'],'archive_sha256':package['archive_sha256']}))

