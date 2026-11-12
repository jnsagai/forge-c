from pathlib import Path
import os,sys,json,subprocess,time
P=Path('/mnt/data/forge-c/production-local-014');O=P/'deployment/afo-repair-live-20261029-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.afo import operations
from forge_factory.afo.queue import Store
from forge_factory.afo.durable import immutable_json
from forge_factory.common import utc_now
scope=json.loads((O/'scope.json').read_text());I=operations.Intent();S=Store()
with I.lock():
    assert I.read()['mode']=='RUNNING' and I.read()['epoch']==34
    assert time.time()<scope['deadline_epoch']
    assert S.order(scope['new_order_id'])['state']=='WAITING_EXTERNAL_CHANGE'
    assert (O/'enrolment.json').is_file()
    observed=operations.observed_unit()
    assert observed.get('ActiveState') in ('inactive','failed'),observed
    result=subprocess.run(['systemctl','--user','--no-block','start',operations.UNIT,
        'forge-afo-watchdog-014-omniverse2.timer'],check=True,capture_output=True,text=True,timeout=20)
    record={'status':'EXISTING_CONDUCTOR_START_REQUESTED','order_id':scope['new_order_id'],
        'operator_epoch':34,'host_systemd_precheck':observed,'returncode':result.returncode,'at':utc_now()}
    immutable_json(O/'conductor-start.json',record);print(json.dumps(record),flush=True)
