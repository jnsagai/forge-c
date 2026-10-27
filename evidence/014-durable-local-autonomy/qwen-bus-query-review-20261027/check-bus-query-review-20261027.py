import ctypes,hashlib,json,subprocess,time
from pathlib import Path
from types import SimpleNamespace
from forge_factory.afo import bus_audit as B
from forge_factory.knowledge import experience as E
from forge_factory.knowledge.store import LessonStore
q=Path('/mnt/data/forge-c/inspector-014-b309039');o=q/'runs/qwen-bus-query-review-20261027'
rev=subprocess.check_output(['git','-C',str(q/'host-bus-fbd8bc8/repo'),'rev-parse','HEAD'],text=True).strip()
assert rev=='fbd8bc89967b68ed4e99e4c63fe12784f135e62f'
lib=ctypes.CDLL('libdbus-1.so.3');lib.dbus_validate_bus_name.argtypes=[ctypes.c_char_p,ctypes.c_void_p];lib.dbus_validate_bus_name.restype=ctypes.c_int
major=ctypes.c_int();minor=ctypes.c_int();micro=ctypes.c_int();lib.dbus_get_version(ctypes.byref(major),ctypes.byref(minor),ctypes.byref(micro))
old=B.subprocess.run
checks=[]
for name,value,member in [('numeric',':1.2','GetNameOwner'),('uppercase',':1.ABC','GetNameOwner'),('mixed',':Upper_case.part-two','GetNameOwner'),('get-id','a'*32,'GetId'),('output-bound','x'*8192,'GetId')]:
 raw=(f'method return time=100.000001 sender=org.freedesktop.DBus -> destination=:1.3 serial=3 reply_serial=2\n   string "{value}"\n').encode() if name!='output-bound' else value.encode()
 def fake_run(argv,**kwargs):kwargs['stdout'].write(raw);return SimpleNamespace(returncode=0)
 B.subprocess.run=fake_run
 try:result=B._query('/usr/bin/dbus-send','user',B.environment('user'),member)
 finally:B.subprocess.run=old
 oracle=bool(lib.dbus_validate_bus_name(value.encode(),None)) if member=='GetNameOwner' else None
 checks.append({'case':name,'member':member,'input_sha256':hashlib.sha256(raw).hexdigest(),'input_bytes':len(raw),'native_bus_name_oracle':oracle,'result':result})
rec={'scope':'INDEPENDENT_NATIVE_LIBRARY_AND_CONTROLLED_SUBPROCESS_FIXTURES_NOT_PRODUCT_OR_NATIVE_CAMPAIGN','source_revision':rev,'source_sha256':hashlib.sha256(Path(B.__file__).read_bytes()).hexdigest(),'oracle':'libdbus-1.so.3.dbus_validate_bus_name','oracle_version':f'{major.value}.{minor.value}.{micro.value}','primary_contract':'https://dbus.freedesktop.org/doc/dbus-specification.html#message-protocol-names-bus','checks':checks,'conclusion':'8KiB refusal is the intended bound; valid nonnumeric unique names reveal an independently reproduced compatibility defect. Model second source quote was not literal; proposal reference validation remains FAIL.'}
path=o/'independent-before.json';path.write_text(json.dumps(rec,indent=2)+'\n')
def ref(p):return str(p)+'#sha256='+hashlib.sha256(p.read_bytes()).hexdigest()
store=LessonStore();ids=[]
ids.append(E.capture(store,'external-study-bus-query-helpers-fbd8bc8-20261027','HARNESS_PREFLIGHT','BLOCKED',facts={'scope':'EXTERNAL_ENGINEERING_STUDY','initial_exit':1,'client_calls_attempted':0,'cause':'identity comparison crossed a user namespace; preserved original counter and source','budget_max_calls_unchanged':1},source_refs=[ref(o/'initial-accounting.json'),ref(o/'initial-preflight.log')],cohort={'study':'bus-query-helpers-fbd8bc8-20261027','evaluation_holdout':True}))
ids.append(E.capture(store,'external-study-bus-query-helpers-fbd8bc8-20261027','INDEPENDENT_PROTOCOL_CHECK','FAIL',facts={'scope':rec['scope'],'oracle':rec['oracle'],'oracle_version':rec['oracle_version'],'supported_numeric_reply':'PASS','valid_nonnumeric_names':'FALSE_BLOCK_REPRODUCED','buffer_ceiling':'CORRECT_REFUSAL','model_reference_check':'FAIL','product_success':'NOT_MEASURED'},source_refs=[ref(path),ref(o/'proposal.json')],cohort={'study':'bus-query-helpers-fbd8bc8-20261027','evaluation_holdout':True}))
E.consolidate(store,limit=32,inference_budget=0)
with store._conn() as c: dispositions=[{'experience_id':i,**json.loads(c.execute('SELECT record FROM learning_dispositions WHERE experience_id=?',(i,)).fetchone()[0])} for i in ids]
(o/'independent-learning-capture.json').write_text(json.dumps({'experience_ids':ids,'dispositions':dispositions,'qualified_lessons_added':0,'benefit':'NOT_MEASURED'},indent=2)+'\n')
print(json.dumps({'oracle_version':rec['oracle_version'],'cases':[(x['case'],x['native_bus_name_oracle'],x['result'].get('error')) for x in checks],'new_model_calls':0}),flush=True)
