from pathlib import Path
import os,sys,json,subprocess,socket,signal,time
import httpx
N=Path('/mnt/data/forge-c/native-artifacts-014-20261030-v1');Q=N/'source-gateway-71906039'
for key in list(os.environ):
 if key.startswith('FORGE_'):os.environ.pop(key)
os.environ.update(FORGE_REPO_ROOT=str(Q),FORGE_DATA_ROOT=str(N),FORGE_LRTX_ROOT=str(N))
sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.lrtx import stack,profile,pidfd
from forge_factory.afo.operations import Intent
from forge_factory.afo.durable import immutable_json
from forge_factory.common import utc_now,sha256_file
rev='719060396f3b9172465af7fab2d81e9987024842'
assert subprocess.check_output(['git','-C',str(Q),'rev-parse','HEAD'],text=True).strip()==rev
qualification=json.loads((N/'native-system-order-qualification.json').read_text())
assert qualification['result']=='PASS' and qualification['gateway_source_sha256']==sha256_file(Q/'factory/python/forge_factory/llm_gateway.py')
record=N/'run/services.json';services=json.loads(record.read_text());old=services['gateway'];oldpid=old['pid']
cmdline=Path('/proc/'+str(oldpid)+'/cmdline').read_bytes().split(b'\0')
assert b'forge_factory.llm_gateway' in cmdline and b'11458' in cmdline and str(N/'state/llm-gateway/usage.jsonl').encode() in cmdline
I=Intent('/home/omniverse2/.local/state/forge-c-production-014/operations.json')
p=profile.load('local-rtx-v2-omniverse2-q38-qm-native-artifacts')
env={**os.environ,**stack.envmap({'profile':p,'root':N,'ports':p['deployment']['ports']})}
env.update(FORGE_DURABLE_AUTONOMY='0',FORGE_DURABLE_NATIVE_HEADER='0',PYTHONDONTWRITEBYTECODE='1',
 FORGE_GATEWAY_REASONING=stack.gateway_reasoning(p),FORGE_GATEWAY_REQUEST_TIMEOUT_S='86400',
 FORGE_GATEWAY_ROUTES=json.dumps({p['models']['default']:'http://127.0.0.1:11457'}),FORGE_GATEWAY_REQUEST_MEASUREMENT='{}')
for key in ('FORGE_GATEWAY_MAX_INFLIGHT','FORGE_OPERATIONS_INTENT','FORGE_AFO_POLICY','FORGE_AFO_AUTH_DIR','FORGE_AFO_ALLOWED_SIGNERS'):
 env.pop(key,None)
# Prefer handing off while the one native model request is already processing.
for _ in range(100):
 slots=httpx.get('http://127.0.0.1:11457/slots',timeout=3).json()
 if any(s.get('is_processing') for s in slots):break
 time.sleep(.05)
else:raise RuntimeError('NO_ACTIVE_REQUEST_DRAIN_WINDOW')
operation=N/'gateway-handoff-71906039.json'
assert not operation.exists(),'DO_NOT_REPEAT_HANDOFF'
with I.lock():
 assert I.read()['mode']=='PAUSED' and I.read()['epoch']==111
 fd=pidfd.open_pid(oldpid)
 try:pidfd.send_signal(fd,signal.SIGTERM)
 finally:os.close(fd)
start=time.monotonic()
for _ in range(200):
 probe=socket.socket();probe.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
 try:probe.bind(('127.0.0.1',11458));probe.close();break
 except OSError:probe.close();time.sleep(.025)
else:raise RuntimeError('OLD_GATEWAY_LISTENER_NOT_CLOSED')
log=(N/'logs/native-gateway-71906039.log').open('ab',buffering=0)
with I.lock():
 assert I.read()['mode']=='PAUSED' and I.read()['epoch']==111
 child=subprocess.Popen(old['argv'],env=env,cwd=N,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
for _ in range(100):
 try:
  if httpx.get('http://127.0.0.1:11458/health',timeout=.5).status_code==200:break
 except httpx.HTTPError:pass
 if child.poll() is not None:raise RuntimeError('NEW_GATEWAY_EXITED')
 time.sleep(.05)
else:raise RuntimeError('NEW_GATEWAY_NOT_READY')
services.setdefault('retiring_gateways',[]).append({**old,'retirement':'GRACEFUL_SIGTERM_DRAIN','at':utc_now()})
services['gateway']={**old,'pid':child.pid,'started_at':utc_now(),'source_revision':rev,'profile_version':p['version'],'system_message_order':'merge_first'}
record.write_text(json.dumps(services,indent=2)+'\n');record.chmod(0o600)
result={'at':utc_now(),'source_revision':rev,'old_gateway_pid':oldpid,'new_gateway_pid':child.pid,
 'profile_version':p['version'],'system_message_order':'merge_first','handoff_ms':round((time.monotonic()-start)*1000,1),
 'gateway_health':'PASS','old_gateway_still_draining':Path('/proc/'+str(oldpid)).exists(),
 'provider_signals_sent':0,'native_runs_restarted':0,'old_gateway_active_request_allowed_to_finish':True,
 'operator_mode':'PAUSED','operator_epoch':111,'runtime_graph_source_still':'c221b65ebc011cbed488db83af3e2804790c1129'}
immutable_json(operation,result);print(json.dumps(result))

