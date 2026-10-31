"""Expose the existing read-only dashboard for the standalone native trial; zero model calls."""
from pathlib import Path
import json,os,sys,subprocess,time
import httpx
N=Path('/mnt/data/forge-c/native-artifacts-014-20261030-v1')
for key in list(os.environ):
 if key.startswith('FORGE_'):os.environ.pop(key)
os.environ.update(FORGE_REPO_ROOT=str(N/'source'),FORGE_LRTX_ROOT=str(N))
sys.path.insert(0,str(N/'source/factory/python'))
from forge_factory.lrtx import profile,stack
from forge_factory.common import utc_now
p=profile.load('local-rtx-v2-omniverse2-q38-qm-native-artifacts')
env={**os.environ,**stack.envmap({'profile':p,'root':N,'ports':p['deployment']['ports']}),
     'FORGE_DURABLE_AUTONOMY':'0','PYTHONDONTWRITEBYTECODE':'1'}
record=N/'run/dashboard.json';url='http://127.0.0.1:8786'
try:active=httpx.get(url+'/api/v1/health/live',timeout=2).status_code==200
except httpx.HTTPError:active=False
if not active:
 log=(N/'logs/native-dashboard.log').open('ab',buffering=0)
 proc=subprocess.Popen([str(N/'venv/bin/python'),'-m','forge_factory.dashboard.app','--host','127.0.0.1',
                        '--host','100.118.28.92','--port','8786'],env=env,cwd=N,
                       stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
 record.write_text(json.dumps({'pid':proc.pid,'started_at':utc_now(),'url':url,'tailscale_url':'http://100.118.28.92:8786',
                              'source_revision':'c221b65ebc011cbed488db83af3e2804790c1129','model_calls':0},indent=2)+'\n')
 for _ in range(60):
  try:
   if httpx.get(url+'/api/v1/health/live',timeout=2).status_code==200:break
  except httpx.HTTPError:pass
  if proc.poll() is not None:raise RuntimeError('DASHBOARD_EXITED')
  time.sleep(1)
r=httpx.get(url+'/api/v1/runs',timeout=20);r.raise_for_status()
items=r.json()['items'];assert any(x['work_order']=='WO-F014-QWEN-NATIVE-ARTIFACTS-20261030-LL-01' for x in items)
print(json.dumps({'status':'PASS','url':'http://100.118.28.92:8786','work_orders':[x['work_order'] for x in items],
                  'access':'existing dashboard local/trusted-device policy; SSH tunnel for other owner devices','model_requests':0}))
