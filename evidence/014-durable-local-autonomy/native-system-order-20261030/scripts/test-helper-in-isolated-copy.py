from pathlib import Path
import sys,json,subprocess,hashlib,resource,time,shutil,ast
N=Path('/mnt/data/forge-c/native-artifacts-014-20261030-v1');ws=Path(json.loads((N/'launch.json').read_text())['workspace'])
code=N/'private-proposals/swe1_patch.py';tree=ast.parse(code.read_text())
danger={n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)} & {'exec','eval','__import__','compile'}
assert not danger,danger
root=N/'helper-shadow-v1';assert not root.exists(),'PRESERVE_ORIGINAL_SHADOW_RUN'
root.mkdir(mode=0o700);clone=root/'workspace';clone.mkdir(mode=0o700)
rels=['workproducts/SWE.1/software_requirements.md','workproducts/SWE.1/register_effects.json',
      'traceability/requirements_to_tests.csv','traceability/upstream_gaps.md']
before={}
for rel in rels:
 src=ws/rel;raw=src.read_bytes();before[rel]=hashlib.sha256(raw).hexdigest()
 dest=clone/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
argv=['bwrap','--unshare-all','--die-with-parent','--new-session','--cap-drop','ALL',
      '--ro-bind','/usr','/usr','--ro-bind','/lib','/lib','--ro-bind','/lib64','/lib64',
      '--proc','/proc','--dev','/dev','--tmpfs','/tmp']
for parent in reversed(ws.parents):
 if str(parent)!='/':argv+=['--dir',str(parent)]
argv+=['--bind',str(clone),str(ws),'--ro-bind',str(code),'/tmp/swe1_patch.py',
       '--chdir',str(ws),'/usr/bin/python3','-I','/tmp/swe1_patch.py']
def limits():
 resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3));resource.setrlimit(resource.RLIMIT_CPU,(60,60))
 resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
started=time.monotonic()
with (root/'stdout.log').open('wb') as out,(root/'stderr.log').open('wb') as err:
 try:r=subprocess.run(argv,env={'PATH':'/usr/bin:/bin','HOME':'/tmp','LANG':'C.UTF-8'},stdin=subprocess.DEVNULL,
                      stdout=out,stderr=err,timeout=120,preexec_fn=limits);exitcode=r.returncode
 except subprocess.TimeoutExpired:exitcode='TIMEOUT'
changes=[]
for rel in rels:
 p=clone/rel;sha=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
 changes.append({'path':rel,'before_sha256':before[rel],'after_sha256':sha,'changed':sha!=before[rel],
                 'bytes_after':p.stat().st_size if p.is_file() else None})
actual={rel:hashlib.sha256((ws/rel).read_bytes()).hexdigest() for rel in rels}
result={'script_sha256':hashlib.sha256(code.read_bytes()).hexdigest(),'model_authored_script':True,
 'exit_code':exitcode,'wall_ms':round((time.monotonic()-started)*1000,1),'namespace':'private network/PID/user namespace; no host home or GPU mounted',
 'scope':'ISOLATED_COPY_ONLY_NOT_ACTIVE_ARTIFACTS','active_hashes_unchanged_during_probe':actual==before,
 'changes':changes,'new_model_calls':0,'stdout_bytes':(root/'stdout.log').stat().st_size,
 'stderr_bytes':(root/'stderr.log').stat().st_size,'script_outputs_independently_validated':False}
(root/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

