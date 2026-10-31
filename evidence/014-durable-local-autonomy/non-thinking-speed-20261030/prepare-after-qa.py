"""Freeze owner-requested non-thinking comparison after native QA; never activate or infer."""
from pathlib import Path
import json,os,subprocess,time
P=Path('/mnt/data/forge-c/production-local-014')
D=P/'deployment';Q=D/'qualification-non-thinking-12e601e4-epoch87-v1';F=D/'non-thinking-followup-12e601e4-v1/result.json'
O=D/'q38-nonthink-speed-20261030-v1';N=D/'non-thinking-preparation-12e601e4-v1';N.mkdir(mode=0o700)
while not F.exists():
 if time.time()>=1793368372.0:
  (N/'result.json').write_text(json.dumps({'status':'NOT_RUN_QA_NOT_COMPLETE_BEFORE_EXISTING_DEADLINE','model_requests':0})+'\n');raise SystemExit(3)
 time.sleep(15)
followup=json.loads(F.read_text());assert followup['exit_code']==0 and followup['window_result']['owned_verifier_quiescent']
proof=json.loads((Q/'provenance.json').read_text())
assert proof['source_revision']=='12e601e4f53ab71b6d184ae19379faa1dd8f6e97' and proof['pytest_exit_code']==0
assert proof['source_clean_before'] and proof['source_clean_after'] and proof['operator_intent_unchanged'] and proof['model_requests']==0
assert proof['summary']['tests']>=150 and not any(proof['summary'][k] for k in ('failures','errors','skipped'))
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:k,v=line.split('=',1);os.environ[k]=v
intent=json.loads(Path('/home/omniverse2/.local/state/forge-c-production-014/operations.json').read_text());assert intent['mode']=='RUNNING' and intent['epoch']==88
os.environ.update(FORGE_REPO_ROOT=str(Q/'repo'),PYTHONPATH=str(Q/'repo/factory/python'),PYTHONDONTWRITEBYTECODE='1')
command=[str(P/'venv/bin/python'),'-m','forge_factory.lrtx.reasoning_comparison','--out',str(O),'--compiler',str(P/'toolchains/LLVM-19.1.7-Linux-X64/bin/clang'),'--capabilities',str(Q/'repo/evidence/014-durable-local-autonomy/reasoning-speed-20261030/native-template-preflight.json'),'--non-thinking-proof',str(Q/'repo/evidence/014-durable-local-autonomy/reasoning-speed-20261030/reasoning-disabled-template-preflight.json'),'--campaign-prefix','q38-nothink-20261030-v1']
with (N/'preparation.json').open('xb') as out,(N/'preparation-error.log').open('xb') as err:
 r=subprocess.run(command,cwd=Q/'repo',env=os.environ.copy(),stdout=out,stderr=err,timeout=180)
(N/'result.json').write_text(json.dumps({'status':'PREPARED_NOT_RUN' if r.returncode==0 else 'PREPARATION_FAILED','exit_code':r.returncode,'source_revision':proof['source_revision'],'model_requests':0,'grants_created':0,'source_activated':False,'operator_intent_changed':False})+'\n')
raise SystemExit(r.returncode)
