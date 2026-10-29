import hashlib,json,os,socket,subprocess,sys,time
from pathlib import Path
P=Path('/mnt/data/forge-c/production-local-014');N=P/'deployment/qualification-archive-319e215';R=N/'repo'
REV='319e215417b8f7e0d329fb3ce71b595f0367f8ef'
assert socket.gethostname()=='omniverse2'
def git(*a):return subprocess.check_output(['git','-C',str(R),*a],text=True).strip()
assert git('rev-parse','HEAD')==REV and not git('status','--porcelain')
Q=N/'qualified';Q.mkdir(mode=0o700)
(N/'data/toolchains').symlink_to(P/'toolchains',target_is_directory=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('FORGE_','FABRO_','OPENAI_','ANTHROPIC_'))}
env.update(PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',FORGE_FABRO_LIVE='0',FABRO_NO_UPGRADE_CHECK='1',
 FORGE_FABRO_BIN='/mnt/data/forge-c/fabro-0.362.0/fabro-x86_64-unknown-linux-musl/fabro',FORGE_FABRO_HOME=str(N/'fabro-home'),
 PYTHONPATH=str(R/'factory/python'),FORGE_REPO_ROOT=str(R),FORGE_DATA_ROOT=str(N/'data'),FORGE_STATE_DIR=str(N/'state'),
 FORGE_EVENTS_DIR=str(N/'events'),FORGE_ARCHIVE_DIR=str(N/'archives'),TMPDIR=str(N/'tmp'))
env['PATH']=':'.join([str(P/'venv/bin'),str(P/'toolchains/LLVM-19.1.7-Linux-X64/bin'),'/usr/local/bin','/usr/bin','/bin',str(P/'toolchains/formal/bin'),str(P/'toolchains/sysroot/usr/bin')])
cmd=[str(P/'venv/bin/python'),'-m','pytest','-q','factory/python/tests/test_archive_inventory.py',
 'factory/python/tests/test_m7_governance_release.py','--junitxml='+str(Q/'pytest.xml')]
record={'source_revision':REV,'host':socket.gethostname(),'command':cmd,'source_clean_before':True,
 'environment':{k:env[k] for k in ('FORGE_DATA_ROOT','FORGE_FABRO_LIVE','FORGE_FABRO_BIN','FORGE_FABRO_HOME','TMPDIR','PATH')},
 'model_requests':0,'production_mutated':False,'authority_created_or_renewed':False,'started_epoch':time.time(),
 'prior_attempt':'../provenance.json','corrected_prerequisite':'Existing PlantUML mapping and native toolchain PATH; no source/test changes'}
with (Q/'pytest.log').open('w') as out:result=subprocess.run(cmd,cwd=R,env=env,stdout=out,stderr=subprocess.STDOUT)
record.update(exit_code=result.returncode,source_clean_after=not git('status','--porcelain'),completed_epoch=time.time())
(Q/'provenance.json').write_text(json.dumps(record,indent=2)+'\n')
assert result.returncode==0 and record['source_clean_after']
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.release.finalize import verify_archive
from forge_factory.common import sha256_file
archive=P/'archives/WO-AFO-5ab4a2eb3e9de743-a1/forge-c-WO-AFO-5ab4a2eb3e9de743-a1-review.zip'
sha=sha256_file(archive)
assert sha=='1a406bbd48e75c163a57207268ccfe774072d36164e77fda5bdbef43f14ab257'
verification=verify_archive(archive)
assert verification['integrity']=='PASS',verification
audit={'auditor_revision':REV,'archive_sha256':sha,'verification':verification,'product_acceptance':'BLOCKED_UNCHANGED',
 'model_requests':0,'production_mutated':False}
(Q/'historical-archive-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
print(json.dumps({'source_revision':REV,'test_exit':result.returncode,'source_clean_after':record['source_clean_after'],
 'historical_archive_integrity':verification['integrity'],'product_acceptance':'BLOCKED_UNCHANGED','model_requests':0}))

