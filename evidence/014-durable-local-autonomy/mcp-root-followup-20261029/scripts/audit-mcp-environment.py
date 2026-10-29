from pathlib import Path
import os,json,shutil
P=Path('/mnt/data/forge-c/production-local-014')
rows=[]
for proc in Path('/proc').iterdir():
 if not proc.name.isdigit():continue
 try:
  if proc.stat().st_uid!=os.getuid():continue
  cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  if 'forge_factory.mcp' not in cmd or ' -m ' not in cmd:continue
  env=dict(v.split('=',1) for v in (proc/'environ').read_bytes().decode(errors='replace').split('\0') if '=' in v)
  if not env.get('FORGE_STATE_DIR','').startswith(str(P)):continue
  root=env.get('FORGE_DATA_ROOT')
  rows.append({'pid':int(proc.name),'role':env.get('FORGE_ROLE'),
   'FORGE_DATA_ROOT':root,'FORGE_STATE_DIR':env.get('FORGE_STATE_DIR'),
   'java_available':shutil.which('java',path=env.get('PATH','')) is not None,
   'jars_at_explicit_root':len(list((Path(root)/'toolchains/plantuml').glob('*.jar'))) if root else None,
   'jars_at_state_parent':len(list((Path(env['FORGE_STATE_DIR']).parent/'toolchains/plantuml').glob('*.jar')))})
 except (OSError,ValueError):continue
print(json.dumps({'read_only':True,'environment_fields':'only root/state/role/java lookup, never credentials','processes':rows},indent=2))
