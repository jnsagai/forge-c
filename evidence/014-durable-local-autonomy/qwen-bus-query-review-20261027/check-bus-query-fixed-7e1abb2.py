import ctypes,hashlib,json,subprocess
from pathlib import Path
from types import SimpleNamespace
from forge_factory.afo import bus_audit as B
from forge_factory.knowledge import experience as E
from forge_factory.knowledge.store import LessonStore
q=Path('/mnt/data/forge-c/inspector-014-b309039');o=q/'runs/qwen-bus-query-review-20261027';r=q/'host-control-7e1abb2/repo'
rev=subprocess.check_output(['git','-C',str(r),'rev-parse','HEAD'],text=True).strip();assert rev=='7e1abb2849dfc6272a00c8b56f6be7a8ea0588d1'
lib=ctypes.CDLL('libdbus-1.so.3');lib.dbus_validate_bus_name.argtypes=[ctypes.c_char_p,ctypes.c_void_p];lib.dbus_validate_bus_name.restype=ctypes.c_int
old=B.subprocess.run;checks=[]
for name,value,accept in [('numeric',':1.2',True),('uppercase',':1.ABC',True),('mixed',':Upper_case.part-two',True),('empty-element',':1..a',False),('no-period',':one',False),('colon-only',':',False)]:
 raw=(f'method return time=100.000001 sender=org.freedesktop.DBus -> destination=:1.3 serial=3 reply_serial=2\n   string "{value}"\n').encode()
 def fake_run(argv,**kwargs):kwargs['stdout'].write(raw);return SimpleNamespace(returncode=0)
 B.subprocess.run=fake_run
 try:result=B._query('/usr/bin/dbus-send','user',B.environment('user'),'GetNameOwner')
 finally:B.subprocess.run=old
 actual='value' in result
 assert actual==accept,(name,result)
 checks.append({'case':name,'normative_expected_acceptance':accept,'native_libdbus_accepts':bool(lib.dbus_validate_bus_name(value.encode(),None)),'result':result,'pass':actual==accept})
rec={'scope':'CONTROLLED_NATIVE_REPLY_FIXTURES_AND_LIBDBUS_EXAMPLES_NOT_PRODUCT_OR_COMPLETE_AUDIT','source_revision':rev,'source_sha256':hashlib.sha256(Path(B.__file__).read_bytes()).hexdigest(),'primary_contract':'https://dbus.freedesktop.org/doc/dbus-specification.html#message-protocol-names-bus','checks':checks,'status':'PASS','oracle_limit':'libdbus 1.12 overaccepts degenerate unique names; explicit normative element/period rules remain enforced','new_model_calls':0,'product_success':'NOT_MEASURED','learning_benefit':'NOT_MEASURED'}
p=o/'independent-after-7e1abb2.json';p.write_text(json.dumps(rec,indent=2)+'\n')
def ref(p):return str(p)+'#sha256='+hashlib.sha256(p.read_bytes()).hexdigest()
store=LessonStore();eid=E.capture(store,'external-study-bus-query-helpers-fbd8bc8-20261027','INDEPENDENT_FIXED_PROTOCOL_CHECK','PASS',facts={'scope':rec['scope'],'status':'PASS','checks':len(checks),'source_revision':rev,'oracle_limit':rec['oracle_limit'],'new_model_calls':0,'benefit':'NOT_MEASURED'},source_refs=[ref(p),ref(o/'independent-before.json')],cohort={'study':'bus-query-helpers-fbd8bc8-20261027','evaluation_holdout':True})
E.consolidate(store,limit=32,inference_budget=0)
with store._conn() as c: disposition=json.loads(c.execute('SELECT record FROM learning_dispositions WHERE experience_id=?',(eid,)).fetchone()[0])
(o/'fixed-learning-capture.json').write_text(json.dumps({'experience_id':eid,'disposition':disposition,'qualified_lessons_added':0,'benefit':'NOT_MEASURED'},indent=2)+'\n');print(json.dumps({'status':'PASS','checks':len(checks),'new_model_calls':0}),flush=True)
