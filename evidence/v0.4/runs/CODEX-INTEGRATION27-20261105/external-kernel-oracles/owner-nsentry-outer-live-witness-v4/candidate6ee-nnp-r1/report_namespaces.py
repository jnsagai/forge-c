import json,os,sys
from pathlib import Path
p=Path('/proc/self')
v={k:os.readlink(p/'ns'/k) for k in ['user','net','mnt','pid']}
v.update(uid=os.getuid(),pid_local=os.getpid(),uid_map=Path('/proc/self/uid_map').read_text())
Path(sys.argv[1]).write_text(json.dumps(v))
