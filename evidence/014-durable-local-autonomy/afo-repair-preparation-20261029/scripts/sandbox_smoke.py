from pathlib import Path
import os,sys,json,hashlib
P=Path('/mnt/data/forge-c/production-local-014');R=P/'deployment/qualification-core-stop-3015e47-v6/repo'
sys.path.insert(0,str(R/'factory/python'));os.environ['FORGE_DATA_ROOT']=str(P)
from forge_factory.reliability import isolation
N=P/'deployment/afo-repair-trial-20261029/operator'
src=N/'sandbox-smoke-src';src.mkdir(mode=0o755)
(src/'source.txt').write_text('read-only synthetic marker\n');(src/'source.txt').chmod(0o444)
scratch=N/'sandbox-smoke-work';scratch.mkdir(mode=0o777);scratch.chmod(0o777)
canary=N/'synthetic-private-canary';canary.write_text('not a real credential\n');canary.chmod(0o600)
code="""import os,json,pathlib
src=pathlib.Path(os.environ['FORGE_REPO_ROOT'])/'source.txt'
result={'uid':os.getuid(),'source_readable':src.read_text().startswith('read-only'),'gpu_devices':list(map(str,pathlib.Path('/dev').glob('nvidia*')))}
try:src.write_text('should be refused');result['source_write_refused']=False
except OSError:result['source_write_refused']=True
try:pathlib.Path(os.environ['CANARY']).read_text();result['private_canary_hidden']=False
except OSError:result['private_canary_hidden']=True
(pathlib.Path(os.environ['HOME'])/'own.txt').write_text('scratch')
result['scratch_writable']=True
print(json.dumps(result))
raise SystemExit(0 if result['uid']==2003 and result['source_readable'] and result['source_write_refused'] and result['private_canary_hidden'] and not result['gpu_devices'] else 2)
"""
env={'PATH':'/usr/bin:/bin','HOME':str(scratch),'FORGE_REPO_ROOT':str(src),'CANARY':str(canary),'PYTHONDONTWRITEBYTECODE':'1'}
p=isolation.execute('maintainer',[str(P/'venv/bin/python'),'-c',code],cwd=scratch,env=env,writable=[scratch],readable=[src],timeout=30)
record={'schema':'forge-c/maintenance-sandbox-smoke/1','backend':isolation.backend(),'isolation':isolation.level(),'exit_code':p.returncode,'model_requests':0,'scope':'SYNTHETIC_CANARY_AND_READONLY_SOURCE_NO_OWNER_CREDENTIAL_ACCESS','stdout':p.stdout.decode()[-2000:],'stderr':p.stderr.decode()[-1000:]}
(N/'sandbox-smoke.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record,indent=2))

