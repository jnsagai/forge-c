"""Operator private guards only: no actual metadata install/systemd request/remote effects."""
import ast,hashlib,importlib.util,json,os,subprocess,sys,tempfile,time
from pathlib import Path
from types import SimpleNamespace
D=Path(__file__).resolve().parent;OPS=D/'owner-main-ops';S=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/repos/forge-c-014-owner-namespace-history-v6')
os.environ['FORGE_REPO_ROOT']=str(S);sys.path.insert(0,str(S/'factory/python'))
from forge_factory.afo import operations
results=[]
def control(name,fn):
 try:fn();results.append({'name':name,'PASS':True})
 except BaseException as e:results.append({'name':name,'PASS':False,'error':type(e).__name__+':'+str(e)})
def defaults():
 for n in ['install-metadata-reviewed.py','start-main-reviewed.py']:
  r=subprocess.run([sys.executable,str(OPS/n)],capture_output=True,text=True,timeout=3);assert r.returncode==0,r.stderr;assert json.loads(r.stdout)['effects'] is False
control('actual_both_default_plans_no_runtime_effect',defaults)

def binding():
 b=json.loads((OPS/'binding.json').read_text());assert b['source']=='f0c8fc5c8ae83952a05cea578d41e0ff06324afd';assert b['fixed_deadline']==1795057626
 prefix=b['data_path']+'/'
 for path,h in b['files'].items():
  if path.startswith(prefix):assert hashlib.sha256((D/'development-inputs'/path[len(prefix):]).read_bytes()).hexdigest()==h
  else:assert path==b['root']+'/native-header/measurement.json' and h=='aef57c57eb80c91f09b90487f70d479708101362bad1f7e60507372e0fad640e'
 for row in b['inputs']+b['source_files']:assert hashlib.sha256((S/row['path']).read_bytes()).hexdigest()==row['sha256']
 c=json.loads((D/'development-inputs/control/line-recovery-control.development.json').read_text());assert c['source_revision']==b['source'] and c['mission']['limits']=={'deadline':1795057626.0,'max_attempts':4,'max_corrections':4,'max_jobs':4,'max_requests':32,'max_tokens':8388608,'max_tools':256}
control('actual_local_data_all_bound_source_input_measurement_caps_hashes',binding)

def command_contract():
 t=ast.parse((OPS/'start-main-reviewed.py').read_text());fn=next(x for x in t.body if isinstance(x,ast.FunctionDef) and x.name=='main')
 node=next(n for n in ast.walk(fn) if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='command' for x in n.targets))
 strings=[n.value for n in ast.walk(node.value) if isinstance(n,ast.Constant) and isinstance(n.value,str)]
 for flag in ['--no-block','--bootstrap-managed-profile','--reconcile-bootstrap-intent','--reconcile-bootstrap-result-sha256','--reconcile-bootstrap-evidence','--reconcile-bootstrap-evidence-sha256']:assert strings.count(flag)==1
 assert '--max-cycles' not in strings and '--no-block' in strings
 assert 'D.guardian_alive=' not in (OPS/'start-main-reviewed.py').read_text() and 'D.guardian_alive = ' not in (OPS/'start-main-reviewed.py').read_text()
 assert "HARDENING=FAILED_R/" in (OPS/'start-main-reviewed.py').read_text()
control('actual_main_command_complete4reconciliation_flags_no_restart_or_false_dead_predicate',command_contract)

# Compile the exact nested final request/freshness functions, not reimplementations.
tree=ast.parse((OPS/'start-main-reviewed.py').read_text());main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
request=next(n for n in ast.walk(main) if isinstance(n,ast.FunctionDef) and n.name=='request_start');fresh=next(n for n in ast.walk(main) if isinstance(n,ast.FunctionDef) and n.name=='evidence_fresh')
def actual_fenced_request(change=None):
 with tempfile.TemporaryDirectory() as t:
  root=Path(t);root.chmod(0o700);intent=root/'intent.json';old=os.environ.get('FORGE_OPERATIONS_INTENT');os.environ['FORGE_OPERATIONS_INTENT']=str(intent)
  try:
   initial=operations.Intent(intent).set('RUNNING',actor='PRIVATE_CONTROL',reason='Private operator guard control',initialize=True)
   evidence={'intent_epoch':initial['epoch'],'observed_monotonic':time.monotonic()-(61 if change=='stale' else 0),'observed_boottime':time.clock_gettime(time.CLOCK_BOOTTIME)-(61 if change=='stale' else 0)}
   calls=[]
   def need(ok,code):
    if not ok:raise RuntimeError(code)
   def ticket_leaf(*args):
    calls.append('PRIVATE_TICKET_LEAF')
    if change=='ticket':raise RuntimeError('PRIVATE_TICKET_REFUSED')
   env={'time':time,'need':need,'evidence':evidence,'D':SimpleNamespace(validate_expiry_ticket=ticket_leaf),'ticket':{'PRIVATE_ONLY':True},'subprocess':subprocess,'command':[sys.executable,'-c',"print('PRIVATE_EFFECT')"]}
   exec(compile(ast.fix_missing_locations(ast.Module(body=[fresh,request],type_ignores=[])),'exact_final_request','exec'),env)
   if change=='stop':operations.Intent(intent).set('STOPPED',actor='PRIVATE_CONTROL',reason='Private STOP before final request')
   try:r=operations.fenced_call(initial['epoch'],env['request_start'])
   except Exception as e:
    assert change in ['stale','stop','ticket'],str(e)
    if change=='stop':assert calls==[] and 'OPERATIONS_ADMISSION_FENCED' in str(e)
    if change=='stale':assert 'RECONCILIATION_EVIDENCE_STALE' in str(e)
    if change=='ticket':assert 'PRIVATE_TICKET_REFUSED' in str(e)
   else:assert change is None and r.returncode==0 and r.stdout.strip()=='PRIVATE_EFFECT'
  finally:
   if old is None:os.environ.pop('FORGE_OPERATIONS_INTENT',None)
   else:os.environ['FORGE_OPERATIONS_INTENT']=old
control('exact_request_AST_actual_private_Intent_and_harmless_effect_positive',actual_fenced_request)
for c in ['stop','stale','ticket']:control('exact_request_AST_refuses_'+c,lambda c=c:actual_fenced_request(c))
report={'schema':'forge-c/f0-owner-main-private-fence-controls/1','PASS':sum(r['PASS'] for r in results),'FAIL':sum(not r['PASS'] for r in results),'results':results,'scope':'Private tempIntent+exactASTrequest with explicit ticket validation leaf; harmless localPython effect insteadofsystemd command. Wholeapply/start/canonicalmetadataNOT_RUN.','actual_remote_source_jobs_models_GPU_or_services':False,'no_actual_start_or_install':True,'all_private_handles_closed':True}
with(D/'private-fence-controls-r1.json').open('x') as f:json.dump(report,f,sort_keys=True,indent=2)
print(json.dumps(report));raise SystemExit(bool(report['FAIL']))
