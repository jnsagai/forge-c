
from pathlib import Path
import sys,os,json,signal,time,subprocess,httpx
N=Path('/mnt/data/forge-c/native-artifacts-014-20261030-v1');R=Path('/mnt/data/forge-c/delivery-first-014-20261030-v1');Q=R/'source'
os.environ['FORGE_REPO_ROOT']=str(Q);sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.lrtx import profile,stack,pidfd
from forge_factory.afo.durable import immutable_json
from forge_factory.common import utc_now
out=R/'run/dashboard.json'
if out.exists():print(out.read_text());raise SystemExit(0)
old=json.loads((N/'run/dashboard.json').read_text());pid=int(old['pid']);proc=Path('/proc')/str(pid)
argv=[x.decode() for x in (proc/'cmdline').read_bytes().split(b'\0') if x]
assert 'forge_factory.dashboard.app' in argv and argv[-1]=='8786'
prof=profile.load('local-rtx-v2-omniverse2-q38-delivery-first')
env=stack.envmap({'profile':prof,'root':R,'ports':prof['deployment']['ports']})
env['FORGE_DURABLE_AUTONOMY']='0'
fd=pidfd.open_pid(pid)
try:
 assert [x.decode() for x in (proc/'cmdline').read_bytes().split(b'\0') if x]==argv
 pidfd.send_signal(fd,signal.SIGTERM)
 for _ in range(20):
  if not proc.exists():break
  time.sleep(.2)
 assert not proc.exists(),'OLD_DASHBOARD_STOP_PENDING'
finally:os.close(fd)
log=(R/'logs/dashboard.log').open('ab',buffering=0)
cmd=[str(R/'venv/bin/python'),'-m','forge_factory.dashboard.app','--host','127.0.0.1','--host','100.118.28.92','--port','8786']
child=subprocess.Popen(cmd,env=env,cwd=R,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
rec={'pid':child.pid,'started_at':utc_now(),'source_revision':subprocess.check_output(['git','-C',str(Q),'rev-parse','HEAD'],text=True).strip(),
 'url':'http://127.0.0.1:8786','tailscale_url':'http://100.118.28.92:8786','model_calls':0,'old_dashboard_pid':pid,
 'old_root':str(N),'root':str(R),'data_source':'CURRENT_DELIVERY_FIRST_NATIVE_JOB','existing_access_policy_unchanged':True}
immutable_json(out,rec)
for _ in range(45):
 try:
  response=httpx.get(rec['url']+'/api/v1/runs',timeout=2)
  if response.status_code==200:
   payload=response.json();rid=json.loads((R/'launch.json').read_text())['native_id']
   proof={'at':utc_now(),'status':response.status_code,'current_native_id':rid,'current_run_visible':rid in response.text,'model_calls':0}
   immutable_json(R/'dashboard-proof.json',proof);print(json.dumps({'dashboard':rec,'proof':proof}));break
 except (httpx.HTTPError,ValueError):pass
 assert child.poll() is None,'NEW_DASHBOARD_EXITED'
 time.sleep(.5)
else:raise RuntimeError('DASHBOARD_NOT_READY_YET')

