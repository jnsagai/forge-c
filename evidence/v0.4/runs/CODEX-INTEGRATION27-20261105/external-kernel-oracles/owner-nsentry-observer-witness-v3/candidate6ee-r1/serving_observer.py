import json,os,sys,traceback
from pathlib import Path
src,holder,record,backend,result,log,out,metadata=sys.argv[1:]
os.environ['FORGE_REPO_ROOT']=src;sys.path.insert(0,src+'/factory/python')
from forge_factory.lrtx import stack,provider_process as P
rec=json.loads(Path(record).read_text())
def view(pid):
 v={}
 for key,call in [('namespaces',lambda:{k:os.readlink(f'/proc/{pid}/ns/{k}') for k in ['user','net','mnt','pid']}),('uid_map',lambda:Path(f'/proc/{pid}/uid_map').read_text()),('identity',lambda:P.identity(pid)),('owner_view',lambda:P.owner_view(pid))]:
  try:v[key]=call()
  except Exception as exc:v[key]=dict(error_type=type(exc).__name__,errno=getattr(exc,'errno',None))
 return v
v=dict(observer=view(os.getpid()),holder=view(int(holder)),init=view(rec['init_pid']),captured_init=rec['init'],captured_owner_view=rec['init_owner_view'])
Path(metadata).write_text(json.dumps(v,indent=2))
Path(log).touch(exist_ok=False)
try:
 p=stack._in_ns(int(holder),[sys.executable,backend,result],dict(os.environ),Path(log),Path(out),serving=rec)
 raise SystemExit(p.wait(timeout=5))
except Exception:
 with Path(log).open('a') as f:traceback.print_exc(file=f)
 raise SystemExit(42)
