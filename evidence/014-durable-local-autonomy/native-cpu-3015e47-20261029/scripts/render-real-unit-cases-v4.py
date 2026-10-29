"""Render the two actual failed Qwen unit diagrams through generated MCP context."""
from pathlib import Path
import os,sys,json,tomllib,subprocess
from forge_factory.fabro.runconfig import render_run_toml
N=Path('/mnt/data/forge-c/production-local-014/deployment/qualification-swe6-stop-3015e47-v4')
config=tomllib.loads(render_run_toml('qualification.fabro','zero-model tool context qualification',
 N/'binding-not-used.json',{'forge-evidence-mcp':{'module':'forge_factory.mcp.servers.evidence'}}))
server=config['run']['agent']['mcps']['forge_evidence_mcp']
env={**server['env'],'TMPDIR':str(N/'tmp'),'PYTHONDONTWRITEBYTECODE':'1'}
code=r"""
from pathlib import Path
import sys,json,hashlib,shutil,subprocess
from forge_factory.common import data_root
from forge_factory.inspection import swtrace,views
N=Path(sys.argv[1]);R=N/'repo'
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()=='3015e47f93de7bfd1e81c8dd7bf4426d8c13ddc6'
jar=swtrace._plantuml_jar()
assert data_root()==N/'data' and jar is not None and jar==views.plantuml_jar()
rows=[]
for filename,expected in (
 ('SWU-LL-01.puml','f57d475219464d8821d643d71310caad8a08126993d90b673c1787f60991f6ba'),
 ('SWU-LL-02.puml','af4e98b4114ee9d19801d8831d0adc4acff67575fe9ff53cdb5754e86c8b9599')):
 p=N/'real-unit-cases'/filename
 assert hashlib.sha256(p.read_bytes()).hexdigest()==expected
 ok,why=swtrace.render_ok(p)
 rows.append({'path':filename,'sha256':expected,'rendered':ok,'detail':why})
print(json.dumps({'source_revision':'3015e47f93de7bfd1e81c8dd7bf4426d8c13ddc6',
 'root':str(data_root()),'jar':str(jar),'jar_sha256':hashlib.sha256(jar.read_bytes()).hexdigest(),
 'java':shutil.which('java'),'cases':rows,'generation_requests':0,'production_changed':False,
 'scope':'Actual failed diagram syntax/render only; not new product inspection or Qwen capability'},indent=2))
raise SystemExit(0 if all(r['rendered'] for r in rows) else 2)
"""
run=subprocess.run([server['command'][0],'-c',code,str(N)],env=env,capture_output=True,text=True,timeout=85)
(N/'real-render.stderr').write_text(run.stderr)
if run.stdout:
 record=json.loads(run.stdout);record['exit_code']=run.returncode
 (N/'real-render.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps(record),flush=True)
else:print(json.dumps({'status':'NATIVE_RENDER_CHILD_FAILED','exit_code':run.returncode}),flush=True)
raise SystemExit(run.returncode)
