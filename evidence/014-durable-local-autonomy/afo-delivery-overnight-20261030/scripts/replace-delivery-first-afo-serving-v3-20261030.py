"""Retire the complete old serving namespace and start a verified replacement."""
from pathlib import Path
import json,os,sys,time,select
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1')
os.environ.update(json.loads((E/'control/runtime-env-v4.json').read_text()));sys.path.insert(0,str(E/'source/factory/python'))
from forge_factory.afo import operations,authz,policy
from forge_factory.afo.queue import Store
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.durable import immutable_json,immutable_bytes,digest
from forge_factory.common import sha256_file,utc_now
from forge_factory.lrtx import stack,pidfd,provider_process
O=E/'control/delivery-first-afo-authority-20261030-v3';s=json.loads((O/'scope.json').read_text())
assert digest(s)=='0fe46b9d80ac8fe680b2de88304a4621fdcdb3b3beeff5dbe37a50de98a1f3b2'
assert time.time()<s['deadline_epoch'] and sha256_file(E/'control/mission-before-v3.json')==s['mission_before_sha256']
S=Store();assert not Executions(S).pending()
assert MissionLedger(S).snapshot(s['mission_id'])==json.loads((E/'control/mission-before-v3.json').read_text())
assert operations.Intent().read()['mode']=='RUNNING' and operations.Intent().read()['epoch']==2
prod=operations.Intent('/home/omniverse2/.local/state/forge-c-production-014/operations.json').read()
assert prod['mode']=='PAUSED' and prod['epoch']==111
settings=stack.settings(s['profile']);old=stack.serving_instance(settings)
immutable_json(E/'control/services-before-full-retirement-v3.json',json.loads((E/'run/services.json').read_text()))
old_conductor=json.loads((E/'control/conductor.json').read_text());fd=None
if stack.process_identity(old_conductor['pid']) is not None:fd=pidfd.open_pid(old_conductor['pid'])
stopped=stack.stop(settings)
assert operations.Intent().read()['mode']=='STOPPED' and operations.Intent().read()['effective_stop']
proof=provider_process.quiet(old);assert proof
if fd is not None:
 poll=select.poll();poll.register(fd,select.POLLIN);assert poll.poll(20000),'CONDUCTOR_DID_NOT_STOP'
 os.close(fd)
immutable_json(E/'control/whole-provider-retirement-v3.json',{'at':utc_now(),'stop':stopped,'proof':proof,
 'old_conductor_exit_observed':True,'pending_executions':[],'production_unchanged':'PAUSED111'})
g=json.loads((O/'primary-authorization.json').read_text())
assert authz.signature_valid(g,O/'primary-authorization-message.bin.sig',E/'control/allowed-signers')
immutable_json(E/'control/authorizations'/(g['authorization_id']+'.json'),g)
immutable_bytes(E/'control/authorizations'/g['signature_ref'],(O/'primary-authorization-message.bin.sig').read_bytes())
immutable_bytes(E/'control/policy-v3.yaml',(O/'policy.yaml').read_bytes())
env=json.loads((E/'control/runtime-env-v4.json').read_text());env['FORGE_AFO_POLICY']=str(E/'control/policy-v3.yaml')
immutable_json(E/'control/runtime-env-v5.json',env);os.environ.update(env)
eff=policy.load();assert eff.mode=='PILOT' and eff.sha256==s['policy_sha256']
epoch=operations.Intent().read()['epoch']
resume=operations.synchronize(S,'resume','jnsagai-delegated-10h-qualification',
 'Signed V3 retry after complete managed serving retirement; original window and mission unchanged',expected_epoch=epoch)
started=stack.start(stack.settings(s['profile']),recovery=True)
assert all(started['health'].values()),started['health']
assert started['serving_instance']!=old
assert provider_process.quiet(old)
immutable_json(E/'control/started-stack-v3.json',{'at':utc_now(),'scope_sha256':digest(s),'source_revision':s['source_revision'],
 'operations_epoch':resume['epoch'],'health':started['health'],'serving_instance':started['serving_instance'],
 'model_pid':started['processes']['llama_server']['pid'],'new_model_requests':0,'deadline_utc':s['deadline_utc']})
print(json.dumps({'status':'REPLACEMENT_STARTED','operations_epoch':resume['epoch'],'health':started['health'],
 'old_namespace_quiescence_proven':True,'holder_pid':started['holder_pid'],'new_model_requests':0,'deadline_utc':s['deadline_utc']}))

