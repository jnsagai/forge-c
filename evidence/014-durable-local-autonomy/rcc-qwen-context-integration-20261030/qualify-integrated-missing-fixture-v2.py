"""Rerun one unchanged test after supplying existing private input fixture bytes; retain first error."""
from pathlib import Path
import hashlib,json,os,resource,subprocess,sys,time,xml.etree.ElementTree as ET
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';N=P/'deployment/qualification-integrated-qwen-e21aa74-v1';Q=N/'repo';V=N/'private-input-fixture-recheck-v2';REV='e21aa74411d01458bab45fee8af6d59f710fad03'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(Q/'factory/python'))
from forge_factory.afo.operations import Intent
from forge_factory.afo.durable import immutable_json
from forge_factory.common import sha256_file
from forge_factory.reliability import isolation
assert Intent().read()['mode']=='RUNNING' and Intent().read()['epoch']==56
suite=next(ET.parse(N/'scratch/pytest.xml').getroot().iter('testsuite'));assert suite.get('tests')=='125' and suite.get('errors')=='1' and suite.get('failures')==suite.get('skipped')=='0'
failed=[t for t in suite if t.find('error') is not None];assert len(failed)==1 and failed[0].get('name')=='test_preflight_cli_persists_missing_review_without_launching'
V.mkdir(mode=0o700);rows=[];ex=Path('examples/0014d-st-cube-crc-idr-assisted')
for item in json.loads((R/ex/'workorder.json').read_text())['inputs']:
 src=(R/ex/item['path']).resolve();dst=(Q/ex/item['path']).resolve();assert src.is_relative_to(R) and dst.is_relative_to(Q) and src.is_file()
 if dst.exists():
  assert sha256_file(src)==sha256_file(dst)
  continue
 rel=str(dst.relative_to(Q));assert subprocess.run(['git','-C',str(Q),'check-ignore','-q',rel]).returncode==0
 raw=src.read_bytes();dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw);dst.chmod(0o444)
 rows.append({'path':rel,'source':str(src),'sha256':sha256_file(dst),'bytes':len(raw),'read_only':True})
immutable_json(V/'private-input-provenance.json',{'source':'EXISTING_PRODUCTION_BASELINED_INPUTS','files':rows,'raw_inputs_published':False})
assert subprocess.check_output(['git','-C',str(Q),'rev-parse','HEAD'],text=True).strip()==REV and not subprocess.check_output(['git','-C',str(Q),'status','--porcelain'])
T=V/'scratch';T.mkdir(mode=0o777);T.chmod(0o777)
env={'PATH':str(P/'toolchains/formal/bin')+':'+str(P/'toolchains/LLVM-19.1.7-Linux-X64/bin')+':'+str(P/'venv/bin')+':/usr/bin:/bin','HOME':str(T),'TMPDIR':str(T),'LANG':'C.UTF-8','PYTHONPATH':str(Q/'factory/python'),'FORGE_REPO_ROOT':str(Q),'FORGE_DATA_ROOT':str(P),'FORGE_STATE_DIR':str(T/'state'),'FORGE_EVENTS_DIR':str(T/'events'),'FORGE_FABRO_LIVE':'0','PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1'}
command=[str(P/'venv/bin/python'),'-m','pytest','-vv','-p','no:cacheprovider','--rootdir',str(Q),'factory/python/tests/test_da014_product_role_trial.py::test_preflight_cli_persists_missing_review_without_launching','--junitxml='+str(T/'pytest.xml')]
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[-4:]);os.nice(5);resource.setrlimit(resource.RLIMIT_AS,(1536*1024**2,1536*1024**2));resource.setrlimit(resource.RLIMIT_CPU,(120,120))
delivery=json.loads((R/ex/'workorder.json').read_text())['delivery']
os.environ['FORGE_DATA_ROOT']=str(P)
sources=[delivery['source']]+[d['source'] for d in delivery.get('dependencies',[]) if d.get('source')]
vendor=[Path(os.path.expandvars(value)).resolve() for value in sources]
assert all(p.is_dir() and p.is_relative_to(P/'inputs/st') for p in vendor)
immutable_json(V/'vendor-mount-provenance.json',{'read_only_paths':[str(p) for p in vendor],'broad_inputs_or_state_exposed':False})
argv=isolation.bubblewrap_argv('verifier',command,cwd=Q,env=env,writable=[T],readable=[Q,*vendor]);marker=argv.index('--chdir');argv[marker:marker]=['--ro-bind',str(N/'fixture-passwd'),'/etc/passwd','--ro-bind',str(N/'fixture-group'),'/etc/group']
started=time.time();r=subprocess.run(argv,capture_output=True,timeout=180);(V/'pytest.log').write_bytes(r.stdout+r.stderr)
assert not subprocess.check_output(['git','-C',str(Q),'status','--porcelain'])
if r.returncode==0:
 second=next(ET.parse(T/'pytest.xml').getroot().iter('testsuite'));assert second.get('tests')=='1' and all(second.get(k)=='0' for k in ('errors','failures','skipped'))
 immutable_json(N/'qualification-complete.json',{'source_revision':REV,'source_clean_before':True,'source_clean_after':True,'pytest_exit_code':0,'unique_tests_passed':125,'initial_cohort':{'tests':125,'passed':124,'errors':1,'xml_sha256':sha256_file(N/'scratch/pytest.xml'),'provenance_sha256':sha256_file(N/'provenance.json')},'affected_test_recheck':{'tests':1,'passed':1,'xml_sha256':sha256_file(T/'pytest.xml'),'log_sha256':sha256_file(V/'pytest.log'),'started':started,'finished':time.time()},'private_fixture_provenance_sha256':sha256_file(V/'private-input-provenance.json'),'initial_error_retained':True,'unchanged_test_source':True,'model_requests':0,'network':False,'gpu_exposed':False,'runtime_changed':False})
print(json.dumps({'status':'PASS_PRIVATE_FIXTURE_RECHECK' if r.returncode==0 else 'FAIL_PRIVATE_FIXTURE_RECHECK','pytest_exit_code':r.returncode,'missing_private_inputs':len(rows)}));raise SystemExit(r.returncode)
