"""One-shot expiry cleanup for the externally prepared qualification window.

Restore only the exact previously signed production policy, under the unchanged
operator epoch. Never signal workers, release capacity, change mission allowances
or resume a newer stop. Existing Conductor/watchdog own deadline reconciliation.
"""
from pathlib import Path
import os,sys,json,time
import yaml
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/aspice-window-20261028'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
    if line and not line.startswith('#'):
        key,value=line.split('=',1);os.environ[key]=value
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import authz,policy
from forge_factory.afo.operations import Intent
from forge_factory.afo.durable import immutable_json,digest
from forge_factory.common import canonical_json,sha256_bytes,utc_now

scope=json.loads((O/'scope.json').read_text());assert digest(scope)=='cef1df07c885ae4b35d823bb04fe803a7fa3b38d7e04010728408ff23ff3f26b'
assert time.time()>=scope['deadline_epoch']
if not (O/'activation.json').is_file():
    print(json.dumps({'status':'WINDOW_NOT_ACTIVATED_NO_POLICY_CHANGE'}));raise SystemExit(0)
activation=json.loads((O/'activation.json').read_text());intent=Intent()
with intent.lock():
    current=intent.read()
    if current['epoch']!=activation['operator_epoch'] or current['mode']!='RUNNING':
        print(json.dumps({'status':'CLEANUP_FENCED_BY_NEWER_OPERATOR_INTENT','epoch':current['epoch']}));raise SystemExit(0)
    current_policy=policy.load(log=False)
    if current_policy.sha256!=scope['policy_sha256']:
        print(json.dumps({'status':'POLICY_ALREADY_CHANGED_NO_OVERWRITE','policy_sha256':current_policy.sha256}));raise SystemExit(0)
    original=(O/'original-production-policy.yaml').read_bytes();saved=yaml.safe_load(original)
    original_sha=sha256_bytes(canonical_json(saved))
    assert saved['authorization_ref']=='AUTH-014-OMNIVERSE2-Q38-GOLIVE-20261028-V2'
    assert original_sha=='83e78088c66df61e6513c466b9221e85f54ba34adbcddf0dcae48b69d91a96ad'
    assert not policy.schema_errors(saved) and not policy.floor_violations(saved)
    verified=authz.find('PILOT',original_sha,ref=saved['authorization_ref'],action='read_status')
    assert verified.allow,verified.code
    path=Path(os.environ['FORGE_AFO_POLICY']);tmp=path.with_name(path.name+'.e2e-expiry-restore')
    fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(original);stream.flush();os.fsync(stream.fileno())
    os.replace(tmp,path);parent=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(parent)
    finally:os.close(parent)
    assert policy.load(log=False).sha256==original_sha
    result={'status':'ORIGINAL_PRODUCTION_POLICY_RESTORED_AT_WINDOW_EXPIRY','at':utc_now(),
            'operator_epoch':current['epoch'],'policy_sha256':original_sha,'authorization_ref':saved['authorization_ref'],
            'original_grant_expiry':'2026-10-29T05:00:00Z','mission_allowances_modified':False,
            'worker_signals':0,'inference_capacity_released_by_cleanup':False,'factory_services':'LEFT_RUNNING'}
    immutable_json(O/'expiry-restoration.json',result);print(json.dumps(result))
