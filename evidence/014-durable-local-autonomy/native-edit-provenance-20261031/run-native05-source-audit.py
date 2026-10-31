from pathlib import Path
import json,os,subprocess,hashlib
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1');S=E/'control/source-auditor-30371da5';Q=E/'source'
ws=E/'state/workorders/WO-AFO-ee4282b25001a15d-a1/workspace'
env={**os.environ,**json.loads((E/'control/runtime-env-v6.json').read_text()),
 'PYTHONPATH':str(S/'factory/python'),'FORGE_REPO_ROOT':str(S),'PYTHONDONTWRITEBYTECODE':'1'}
services=json.loads((E/'run/services.json').read_text())
before=subprocess.check_output(['git','-C',str(Q),'rev-parse','HEAD'],text=True).strip()
assert before=='0e342eef3c68786d29e5b9843606892c4ab68b60'
assert subprocess.check_output(['git','-C',str(S),'rev-parse','HEAD'],text=True).strip()=='30371da548bad2790a9f3c21dafc8964047ce06d'
r=subprocess.run(['nsenter','-t',str(services['holder_pid']),'-U','-n','--preserve-credentials',str(E/'venv/bin/python'),
 '-m','forge_factory.delivery_first','--workspace',str(ws),'--step','source-provenance'],env=env,capture_output=True,text=True,timeout=40)
if r.returncode:
 print(r.stdout,end='');print(r.stderr,end='',file=__import__('sys').stderr);raise SystemExit(r.returncode)
d=json.loads(r.stdout)
assert d['auditor_factory_revision']['commit']=='30371da548bad2790a9f3c21dafc8964047ce06d'
assert d['producer_factory_revision']['commit']==before
assert d['auditor_module_sha256']=='8ceca6bdbe5d181b0e65f48b4cda3835540dc3ca587011ebc8e6e3879a304cd5'
assert d['candidate_unchanged_during_audit'] and d['model_generation_calls_by_auditor']==0
assert subprocess.check_output(['git','-C',str(Q),'rev-parse','HEAD'],text=True).strip()==before
d['runtime_source_unchanged']=True
print(json.dumps(d))
