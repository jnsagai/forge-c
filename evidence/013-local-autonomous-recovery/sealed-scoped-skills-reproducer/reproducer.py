"""Frozen single-role workspace black-box check; no model calls or private inputs."""
import sys,inspect,tempfile,subprocess
from pathlib import Path
SIG='single-role recovery workspace advertises unrelated product skills'
def main():
 from forge_factory.fabro.runconfig import create_workspace
 from forge_factory.common import REPO_ROOT
 role='afo-recovery-planner';rel='.fabro/skills/'+role+'/SKILL.md';data=(REPO_ROOT/'factory/skills/afo'/role/'SKILL.md').read_bytes()
 with tempfile.TemporaryDirectory() as tmp:
  ws=Path(tmp)/'workspace';kw={'include_default_skills':False} if 'include_default_skills' in inspect.signature(create_workspace).parameters else {}
  create_workspace(ws,{rel:data},**kw)
  files=sorted(p.relative_to(ws).as_posix() for p in (ws/'.fabro/skills').rglob('SKILL.md'))
  committed=subprocess.run(['git','-C',str(ws),'show','HEAD:'+rel],capture_output=True,check=True).stdout
  if files!=[rel] or committed!=data:
   print('SYMPTOM_PRESENT:'+SIG);return 1
 print('SYMPTOM_ABSENT');return 0
if __name__=='__main__':
 try:sys.exit(main())
 except Exception as e:print('REPRODUCER_ERROR:'+type(e).__name__+':'+str(e)[:160]);sys.exit(2)
