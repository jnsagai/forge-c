import ast,hashlib,json,os,subprocess,threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from forge_factory.afo import operations as O
from forge_factory.afo.queue import Store
root=Path.cwd();out=Path(__file__).resolve().parent/'control-race-7e1abb2';out.mkdir(mode=0o700)
private=out/'intent';private.mkdir(mode=0o700)
os.environ['FORGE_OPERATIONS_INTENT']=str(private/'intent.json')
os.environ.pop('FORGE_DURABLE_AUTONOMY',None)
O.Intent().set('RUNNING',actor='fixture-owner',reason='independent counterexample',initialize=True)
source=subprocess.check_output(['git','show','7f77e38125300eb1eb2c67ce097964de456b0927:factory/python/forge_factory/afo/operations.py'],text=True)
node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='synchronize')
raw=''.join(source.splitlines(keepends=True)[node.lineno-1:node.end_lineno])
ns={'Intent':O.Intent};exec(compile(raw,'pinned-old-synchronize','exec'),ns)
old=ns['synchronize'];store=Store(out/'counterexample.sqlite3')
entered,release=threading.Event(),threading.Event();real=store.set_control

def delayed(key,value,actor,reason):
 if actor=='older-resume' and key=='paused':
  entered.set();assert release.wait(3)
 return real(key,value,actor,reason)
store.set_control=delayed
with ThreadPoolExecutor(max_workers=1) as executor:
 prior=executor.submit(old,store,'resume','older-resume','older request')
 assert entered.wait(3)
 try:stopped=old(store,'shutdown','newer-stop','newer request')
 finally:release.set()
 resumed=prior.result(timeout=3)
intent=O.Intent().read();controls=store.control()
assert stopped['epoch']>resumed['epoch'] and intent['mode']=='STOPPED' and controls=={'paused':'0','draining':'0'}
rec={'status':'OLD_ORDERING_DEFECT_REPRODUCED','scope':'PINNED_OLD_SYNCHRONIZE_WITH_COMPATIBLE_CURRENT_INTENT_AND_STORE_NOT_A_FULL_HISTORICAL_FACTORY_RUN','old_revision':'7f77e38125300eb1eb2c67ce097964de456b0927','old_function_sha256':hashlib.sha256(raw.encode()).hexdigest(),'harness_revision':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'older_resume_epoch':resumed['epoch'],'newer_stop_epoch':stopped['epoch'],'final_intent_mode':intent['mode'],'incorrect_final_controls':controls,'independent_fixed_case':'test_da014_control_context.py::test_newer_stop_cannot_be_overwritten_by_old_resume_database_effects'}
(out/'result.json').write_text(json.dumps(rec,indent=2)+'\n');print(json.dumps(rec))
