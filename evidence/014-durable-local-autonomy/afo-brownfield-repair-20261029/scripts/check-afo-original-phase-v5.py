"""Replay the original SWE.3 deterministic phase through candidate-generated isolated MCP context."""
from pathlib import Path
import json,os,subprocess,sys,tomllib
from forge_factory.fabro.runconfig import render_run_toml
ws=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(exist_ok=True)
conf=tomllib.loads(render_run_toml('qualification.fabro','original SWE.3 independent recovery check',out/'unused-binding.json',{'forge-evidence-mcp':{'module':'forge_factory.mcp.servers.evidence'}},binding_id='independent-swe3-replay'))
server=conf['run']['agent']['mcps']['forge_evidence_mcp'];env={**server['env'],'TMPDIR':str(out),'PYTHONDONTWRITEBYTECODE':'1'}
code='''from pathlib import Path
import json,sys
from forge_factory.inspection.swtrace import check_phase
from forge_factory.common import data_root
x=check_phase(Path(sys.argv[1]),'SWE.3');print(json.dumps({'phase':'SWE.3','result':x,'resolved_data_root':str(data_root()),'scope':'Independent deterministic phase replay on a copy; not a new product inspection or release'}));raise SystemExit(0 if x['verdict']=='PASS' else 2)
'''
r=subprocess.run([server['command'][0],'-c',code,str(ws)],env=env,capture_output=True,text=True,timeout=180)
(out/'child.stdout').write_text(r.stdout);(out/'child.stderr').write_text(r.stderr)
try:record=json.loads(r.stdout)
except ValueError:record={'error':'PHASE_CHILD_NO_VALID_RESULT'}
record.update(exit_code=r.returncode,generated_environment_keys=sorted(server['env']),ambient_context_inherited=False)
(out/'result.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record));raise SystemExit(r.returncode)
