
from pathlib import Path
import sys,json,httpx
R=Path('/mnt/data/forge-c/delivery-first-014-20261030-v1');sys.path.insert(0,str(R/'source/factory/python'))
from forge_factory.afo.durable import immutable_json
from forge_factory.common import utc_now
r=httpx.get('http://127.0.0.1:8786/api/v1/runs',timeout=20)
rid=json.loads((R/'launch.json').read_text())['native_id']
proof={'at':utc_now(),'http_status':r.status_code,'endpoint':'/api/v1/runs','current_native_id':rid,'current_run_visible':rid in r.text,'model_calls':0,'initial_probe_path_corrected_without_service_restart':True}
assert r.status_code==200 and proof['current_run_visible'],proof
immutable_json(R/'dashboard-proof.json',proof);print(json.dumps(proof))

