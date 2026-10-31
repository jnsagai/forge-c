"""Independent recovery check using the actual two originally failing SWE.3 diagrams."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,tomllib
from forge_factory.fabro.runconfig import render_run_toml
N=Path('/mnt/data/forge-c/production-local-014/deployment/qualification-swe6-stop-3015e47-v4')
out=Path(sys.argv[1]);out.mkdir(exist_ok=True)
config=tomllib.loads(render_run_toml('qualification.fabro','historical SWE.3 recovery check',out/'unused-binding.json',{'forge-evidence-mcp':{'module':'forge_factory.mcp.servers.evidence'}},binding_id='f014-independent-render'))
server=config['run']['agent']['mcps']['forge_evidence_mcp']
env={**server['env'],'TMPDIR':str(out),'PYTHONDONTWRITEBYTECODE':'1'}
code=r'''
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
from forge_factory.common import data_root
from forge_factory.inspection import swtrace,views
N=Path(sys.argv[1]);out=Path(sys.argv[2]);jar=swtrace._plantuml_jar();rows=[]
for fn,sha in [('SWU-LL-01.puml','f57d475219464d8821d643d71310caad8a08126993d90b673c1787f60991f6ba'),('SWU-LL-02.puml','af4e98b4114ee9d19801d8831d0adc4acff67575fe9ff53cdb5754e86c8b9599')]:
 p=N/'real-unit-cases'/fn;assert hashlib.sha256(p.read_bytes()).hexdigest()==sha
 ok,why=swtrace.render_ok(p);row={'file':fn,'source_sha256':sha,'rendered':ok,'detail':why}
 if ok and jar:
  svg=subprocess.run(['java','-jar',str(jar),'-tsvg','-pipe'],input=p.read_bytes(),capture_output=True,timeout=30)
  q=out/(fn+'.svg');q.write_bytes(svg.stdout);row.update(svg_exit=svg.returncode,svg_sha256=hashlib.sha256(svg.stdout).hexdigest(),svg_bytes=len(svg.stdout));assert svg.returncode==0 and b'<svg' in svg.stdout
 rows.append(row)
r={'root':str(data_root()),'jar':str(jar),'views_jar':str(views.plantuml_jar()),'java':shutil.which('java'),'jar_sha256':hashlib.sha256(jar.read_bytes()).hexdigest() if jar else None,'cases':rows,'generation_requests':0}
print(json.dumps(r));raise SystemExit(0 if jar and jar==views.plantuml_jar() and all(x['rendered'] for x in rows) else 2)
'''
r=subprocess.run([server['command'][0],'-c',code,str(N),str(out)],env=env,capture_output=True,text=True,timeout=85)
(out/'child.stderr').write_text(r.stderr)
record=json.loads(r.stdout) if r.stdout else {'error':'ISOLATED_CHILD_NO_RESULT'}
record.update(exit_code=r.returncode,generated_mcp_environment_keys=sorted(server['env']),child_context_ambient_inherited=False,scope='Original SWE.3 diagram/tool-context path only; no whole-driver pipeline or release claim')
(out/'result.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));raise SystemExit(r.returncode)
