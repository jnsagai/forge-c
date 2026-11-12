"""Manual, model-free qualification after terminal mission reconciliation; never auto-deploy."""
from pathlib import Path
import os,sys,json,subprocess,shutil,time,signal
if sys.argv[1:]!=['--run-when-quiescent']:
 print('Prepared only. Use --run-when-quiescent after physical lease reconciliation.')
 raise SystemExit(0)
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';D=P/'deployment'
clean_env={k:v for k,v in os.environ.items() if not k.startswith(('FORGE_','FABRO_'))}
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#'):
  key,value=line.split('=',1);os.environ[key]=value
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.queue import Store
from forge_factory.afo.operations import Intent
from forge_factory.afo.execution_lifecycle import Executions
S=Store();I=Intent();expected_epoch=18
def quiet():
 state=I.read()
 if state['epoch']!=expected_epoch or state['mode']!='RUNNING':return 'OPERATOR_INTENT_CHANGED'
 if Executions(S).pending():return 'NATIVE_EXECUTIONS_PENDING'
 with S.tx() as c:
  if c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone():return 'RESOURCE_HELD'
  if c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone():return 'PROVIDER_REQUEST_UNSETTLED'
  if c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone():return 'INDEPENDENT_VERIFICATION_PENDING'
 return None
assert not Executions(S).pending(), 'ACTIVE_NATIVE_EXECUTION'
assert quiet() is None,quiet()
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
assert git(R,'rev-parse','HEAD')=='fcb15cba0bbc1b5e6e7c91c86aba08db244b5c61'
assert not git(R,'status','--porcelain')
Q=D/'qualification-aspice-resume-98d066d';Q.mkdir(mode=0o700)
subprocess.run(['git','clone','--shared','--no-checkout',str(R),str(Q/'repo')],check=True)
subprocess.run(['git','-C',str(Q/'repo'),'fetch',str(D/'aspice-resume-98d066d-incremental.bundle'),'HEAD'],check=True)
candidate='98d066dfe519c5ea2b23cec7d8f9681aff1f71d0'
git(Q/'repo','checkout','--detach',candidate)
# Exact ignored owner inputs only; no private keys, logs or production authority copied.
for src in (R/'examples').rglob('*'):
 if not src.is_file() or src.suffix.lower() not in ('.md','.json','.h','.c','.yaml','.yml'):continue
 dst=Q/'repo'/src.relative_to(R)
 if dst.exists():continue
 ignored=subprocess.run(['git','-C',str(Q/'repo'),'check-ignore','--quiet',str(dst.relative_to(Q/'repo'))]).returncode==0
 if ignored:dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
env=dict(clean_env,PYTHONPATH=str(Q/'repo/factory/python'),FORGE_REPO_ROOT=str(Q/'repo'),
 FORGE_DATA_ROOT=str(Q/'data'),FORGE_STATE_DIR=str(Q/'data/state'),FORGE_EVENTS_DIR=str(Q/'data/events'),
 FORGE_CPU_JOBS='16',TMPDIR=str(Q),PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1',
 FORGE_FABRO_BIN='/mnt/data/forge-c/fabro-0.362.0/fabro-x86_64-unknown-linux-musl/fabro',FABRO_NO_UPGRADE_CHECK='1')
env['PATH']=':'.join([str(P/'venv/bin'),str(P/'toolchains/LLVM-19.1.7-Linux-X64/bin'),'/usr/local/bin','/usr/bin','/bin',str(P/'toolchains/formal/bin'),str(P/'toolchains/sysroot/usr/bin')])
(Q/'data').mkdir();(Q/'data/toolchains').symlink_to('/mnt/data/forge-c/toolchains',target_is_directory=True)
subprocess.run([str(P/'venv/bin/python'),'-c','from pathlib import Path; from forge_factory.afo.host import init; init(Path('+repr(str(Q/'data'))+'))'],env=env,cwd=Q/'repo',check=True)
names=['test_aspice_development.py','test_development_safety_policy.py','test_da014_holdout_runtime.py',
 'test_da014_required_scope_coverage.py','test_lrtx_swe1.py','test_m7_governance_release.py',
 'test_da014_product_role_trial.py','test_lrtx_coherent_obligations.py']
crc=['test_the_crc_profile_validates_and_names_the_rm0486_instance',
 'test_the_input_manifest_records_the_converted_pages_and_hashes',
 'test_rm0486_chapter_26_parses_into_the_five_crc_registers',
 'test_the_crc_model_computes_the_stm32_crc32_and_honours_reset_init_and_reversal',
 'test_the_crc_model_reproduces_the_rm0486_reversal_examples']
cmd=[str(P/'venv/bin/python'),'-m','pytest','-q',
 *[str(Path('factory/python/tests')/n) for n in names],
 'factory/python/tests/test_brownfield_resume.py::test_aspice_resume_preserves_evidence_and_historical_scope_across_attempt_ids',
 'factory/python/tests/test_brownfield_resume.py::test_aspice_resume_rechecks_destination_contract_before_copying',
 *['factory/python/tests/test_peripheral_crc.py::'+n for n in crc],
 '--basetemp='+str(Q/'tmp'),'--junitxml='+str(Q/'tests.xml')]
assert quiet() is None,quiet()
inv={'revision':git(Q/'repo','rev-parse','HEAD'),'command':cmd,'scope':'ISOLATED_NATIVE_FIXTURES_ZERO_MODEL_CALLS',
 'start_dirty':git(Q/'repo','status','--porcelain'),'started_epoch':time.time(),
 'production_source_unchanged':git(R,'rev-parse','HEAD'),'expected_operator_epoch':expected_epoch,
 'safety':'No production service start/stop, grant/policy/mission edit, inference request or source promotion.'}
assert inv['revision']==candidate and not inv['start_dirty']
(Q/'invocation.json').write_text(json.dumps(inv))
p=subprocess.Popen(cmd,cwd=Q/'repo',env=env,start_new_session=True)
aborted=None
while p.poll() is None:
 reason=quiet()
 if reason or time.time()-inv['started_epoch']>600:
  aborted=reason or 'QUALIFICATION_TIMEBOX'
  try:os.killpg(p.pid,signal.SIGTERM)
  except ProcessLookupError:pass
  try:p.wait(timeout=10)
  except subprocess.TimeoutExpired:
   try:os.killpg(p.pid,signal.SIGKILL)
   except ProcessLookupError:pass
   p.wait()
  break
 time.sleep(0.5)
inv.update(exit_code=p.returncode,aborted=aborted,finished_epoch=time.time(),
 end_dirty=git(Q/'repo','status','--porcelain'),production_source_end=git(R,'rev-parse','HEAD'))
(Q/'invocation.json').write_text(json.dumps(inv))
print(json.dumps(inv))
raise SystemExit(p.returncode if p.returncode is not None and not aborted else 2)
