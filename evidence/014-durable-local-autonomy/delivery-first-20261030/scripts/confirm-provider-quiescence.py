
from pathlib import Path
import json,httpx,sys
N=Path('/mnt/data/forge-c/native-artifacts-014-20261030-v1')
sys.path.insert(0,str(N/'source/factory/python'))
from forge_factory.afo.durable import immutable_json
from forge_factory.common import utc_now
from forge_factory.fabro.client import FabroClient,load_token,run_status
d=json.loads((N/'launch.json').read_text())
with FabroClient(base_url='http://127.0.0.1:32401',token=load_token(str(N/'fabro/storage'))) as c:
 status=run_status(c.get_run(d['native_id']))
assert status in ('SUCCEEDED','FAILED','CANCELLED','CANCELED')
s=httpx.get('http://127.0.0.1:11457/slots').json()
assert len(s)==1 and not s[0]['is_processing']
rec={'at':utc_now(),'native_id':d['native_id'],'native_status':status,'retired_gateway_absent':not Path('/proc/3902127').exists(),'provider_task_id':s[0].get('id_task'),'provider_slot':s[0]['id'],'inference_quiescent':True,'model_server_signalled':False,'new_job_started':False}
immutable_json(N/'delivery-first-handoff-v1/quiescence.json',rec);print(json.dumps(rec))

