from pathlib import Path
import os,sys
P=Path('/mnt/data/forge-c/production-local-014')
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.lrtx import stack
raise SystemExit(stack.exec_in(stack.settings('local-rtx-v2-omniverse2-q38-aspice-max-mtp'),[str(P/'venv/bin/python'),str(P/'deployment/observe-aspice-rcc.py'),'--native']))
