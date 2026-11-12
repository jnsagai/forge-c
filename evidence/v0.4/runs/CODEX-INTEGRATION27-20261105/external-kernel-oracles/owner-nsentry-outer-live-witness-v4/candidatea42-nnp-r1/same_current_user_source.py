import os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1]+'/factory/python');os.environ['FORGE_REPO_ROOT']=sys.argv[1]
from forge_factory.lrtx import stack
p=stack._in_ns(int(sys.argv[2]),[sys.executable,sys.argv[3],sys.argv[4]],dict(os.environ),Path(sys.argv[5]),Path(sys.argv[6]));raise SystemExit(p.wait(timeout=5))
