"""Run one CPU-only qualification after the frozen MTP sweep; preserve newer operator intent."""
from pathlib import Path
import os,sys,json,subprocess,time
P=Path('/mnt/data/forge-c/production-local-014');O=P/'deployment/q38-mtp-speed-20261030-v1';N=P/'deployment/diagnosis-context-followup-017-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.afo.operations import Intent
from forge_factory.afo.durable import immutable_json
I=Intent();N.mkdir(mode=0o700);deadline=1793368972.0
while not (O/'continuation-complete.json').exists():
 if time.time()>=deadline:
  immutable_json(N/'result.json',{'status':'NOT_RUN_MTP_SWEEP_NOT_COMPLETE','model_requests':0,'deployment':False});raise SystemExit(3)
 time.sleep(15)
current=I.read()
if current['mode']!='RUNNING' or current['epoch']!=86:
 immutable_json(N/'result.json',{'status':'NOT_RUN_NEWER_OPERATOR_INTENT_PRESERVED','mode':current['mode'],'epoch':current['epoch'],'model_requests':0,'deployment':False});raise SystemExit(3)
with (N/'window.log').open('xb') as log:
 run=subprocess.run([str(P/'venv/bin/python'),str(P/'deployment/qualify-diagnosis-context-after-mtp.py'),'--expected-epoch','86'],stdout=log,stderr=subprocess.STDOUT,timeout=720)
result_path=P/'deployment/diagnosis-context-qualification-window-epoch86-v1/result.json'
result=json.loads(result_path.read_text()) if result_path.exists() else {'exit_code':run.returncode,'status':'WINDOW_RESULT_MISSING'}
immutable_json(N/'result.json',{'status':'CPU_ONLY_QUALIFICATION_ENDED','exit_code':run.returncode,'window_result':result,'model_requests':0,'deployment':False})
raise SystemExit(run.returncode)

