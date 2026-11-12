from pathlib import Path
import os,sys,json,subprocess,shutil,time
P=Path('/mnt/data/forge-c/production-local-014');Q=P/'deployment/qualification-aspice-fcb15cb'
Q.mkdir(mode=0o700)
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
subprocess.run(['git','clone','--shared','--no-checkout',str(P/'repo'),str(Q/'repo')],check=True)
subprocess.run(['git','-C',str(Q/'repo'),'fetch',str(P/'deployment/fcb15cb.bundle'),'HEAD'],check=True)
git(Q/'repo','checkout','--detach','FETCH_HEAD')
revision=git(Q/'repo','rev-parse','HEAD');assert revision.startswith('fcb15cb')
# Only copy ignored owner inputs needed by inherited real preparation fixtures.
for rel in ['examples/0002a-arm_55_rcc_ll','examples/0002-arm_55_rcc_st','examples/0003a-arm_55_iwdg_ll','examples/0014c-st-cube-crc']:
 for src in (P/'repo'/rel).rglob('*'):
  if not src.is_file():continue
  dst=Q/'repo'/rel/src.relative_to(P/'repo'/rel)
  if dst.exists():continue
  if src.suffix.lower() not in ('.md','.h','.c','.yaml','.yml'):continue
  if git(Q/'repo','check-ignore',str(dst.relative_to(Q/'repo'))) == str(dst.relative_to(Q/'repo')):
   dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
env=dict(os.environ,PYTHONPATH=str(Q/'repo/factory/python'),FORGE_REPO_ROOT=str(Q/'repo'),
 FORGE_DATA_ROOT=str(Q/'data'),FORGE_STATE_DIR=str(Q/'data/state'),FORGE_EVENTS_DIR=str(Q/'data/events'),
 TMPDIR=str(Q),PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1',
 FORGE_FABRO_BIN='/mnt/data/forge-c/fabro-0.362.0/fabro-x86_64-unknown-linux-musl/fabro',
 FABRO_NO_UPGRADE_CHECK='1')
for key in ['FORGE_DURABLE_AUTONOMY','FORGE_OPERATIONS_INTENT','FORGE_AFO_POLICY','FORGE_FABRO_TOKEN']:
 env.pop(key,None)
env['PATH']=':'.join([str(P/'venv/bin'),str(P/'toolchains/LLVM-19.1.7-Linux-X64/bin'),'/usr/local/bin','/usr/bin','/bin',str(P/'toolchains/formal/bin'),str(P/'toolchains/sysroot/usr/bin')])
(Q/'data').mkdir()
(Q/'data/toolchains').symlink_to('/mnt/data/forge-c/toolchains',target_is_directory=True)
subprocess.run([str(P/'venv/bin/python'),'-c','from pathlib import Path; from forge_factory.afo.host import init; init(Path('+repr(str(Q/'data'))+'))'],env=env,cwd=Q/'repo',check=True)
names=['test_aspice_development.py','test_development_safety_policy.py','test_da014_holdout_runtime.py',
 'test_da014_required_scope_coverage.py','test_lrtx_swe1.py','test_m7_governance_release.py','test_da014_product_role_trial.py']
cmd=[str(P/'venv/bin/python'),'-m','pytest','-q',*[str(Path('factory/python/tests')/n) for n in names],
 '--basetemp='+str(Q/'tmp'),'--junitxml='+str(Q/'tests.xml')]
inv={'revision':revision,'command':cmd,'scope':'ISOLATED_NATIVE_FIXTURES_ZERO_MODEL_CALLS','started_epoch':time.time(),
 'start_dirty':git(Q/'repo','status','--porcelain')}
assert not inv['start_dirty'];(Q/'invocation.json').write_text(json.dumps(inv))
r=subprocess.run(cmd,cwd=Q/'repo',env=env,timeout=600)
inv.update(exit_code=r.returncode,end_dirty=git(Q/'repo','status','--porcelain'),finished_epoch=time.time())
(Q/'invocation.json').write_text(json.dumps(inv));raise SystemExit(r.returncode)
