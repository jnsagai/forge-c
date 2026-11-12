"""Independent offline checks of hash-bound Qwen artifacts, explicitly NOT a broker submission or CRE decision."""
from pathlib import Path
import io,json,os,subprocess,sys,tarfile,xml.etree.ElementTree as ET
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/afo-repair-live-20261029-v6';S=O/'written-artifacts'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.durable import immutable_json
from forge_factory.common import sha256_file,utc_now
from forge_factory.reliability import isolation
proof=json.loads((S/'provenance.json').read_text())
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as db:
 with db.tx() as c:
  x=json.loads(c.execute('SELECT record FROM afo_execution_liveness WHERE job_id=?',(proof['job_id'],)).fetchone()[0]);assert x['execution_liveness']=='QUIESCENT' and x['resource_lease']=='RELEASED'
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
G=P/'deployment/afo-repair-trial-20261029-v2/verifier/test_tool_context.py';inv=json.loads((G.parent.parent/'inventory.json').read_text());assert sha256_file(G)==inv['verifier/test_tool_context.py']['sha256']
D=O/'independent-unsubmitted-check';D.mkdir(mode=0o700);reproducer='factory/python/tests/afo_candidate/test_swe3_10_data_root.py';sealed=D/'sealed';sealed.mkdir();(sealed/'reproducer.py').write_bytes((S/reproducer).read_bytes());(sealed/'reproducer.py').chmod(0o444)
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);os.nice(10);rows=[]
for label in ('baseline','qwen_written_candidate'):
 src=D/(label+'-src');src.mkdir()
 with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','-C',str(R),'archive',proof['base']]))) as tf:tf.extractall(src,filter='data')
 if label=='qwen_written_candidate':
  for rel,meta in proof['files'].items():
   assert sha256_file(S/rel)==meta['sha256'];p=src/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((S/rel).read_bytes())
 scratch=D/(label+'-scratch');scratch.mkdir(mode=0o777);scratch.chmod(0o777)
 env={'PATH':str(P/'venv/bin')+':'+str(P/'toolchains/LLVM-19.1.7-Linux-X64/bin')+':/usr/bin:/bin','LANG':'C.UTF-8','PYTHONPATH':str(src/'factory/python'),'FORGE_REPO_ROOT':str(src),'FORGE_DATA_ROOT':str(P),'FORGE_STATE_DIR':str(scratch/'state'),'TMPDIR':str(scratch),'HOME':str(scratch),'PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','FORGE_FABRO_LIVE':'0'}
 cmd=[str(P/'venv/bin/python'),'-m','pytest','-q','-p','no:cacheprovider','--rootdir',str(G.parent),str(G),'--junitxml='+str(scratch/'pytest.xml')]
 r=isolation.execute('verifier',cmd,cwd=scratch,env=env,writable=[scratch],readable=[src,G.parent],timeout=90);(D/(label+'-frozen.log')).write_bytes(r.stdout+r.stderr);suite=next(ET.parse(scratch/'pytest.xml').getroot().iter('testsuite')) if (scratch/'pytest.xml').exists() else None
 repro=isolation.execute('verifier',[str(P/'venv/bin/python'),str(sealed/'reproducer.py')],cwd=scratch,env=env,writable=[scratch],readable=[src,sealed],timeout=90);(D/(label+'-sealed-reproducer.log')).write_bytes(repro.stdout+repro.stderr)
 lines=[x for x in repro.stdout.decode(errors='replace').splitlines() if x.strip()];expected='SYMPTOM_PRESENT:SWE3-10-PLANTUML_NOT_AVAILABLE-DATA-ROOT-NOT-PROPAGATED' if label=='baseline' else 'SYMPTOM_ABSENT'
 rows.append({'variant':label,'frozen_exit':r.returncode,'frozen_tests':dict(suite.attrib) if suite is not None else None,'frozen_log_sha256':sha256_file(D/(label+'-frozen.log')),'sealed_reproducer_exit':repro.returncode,'sealed_reproducer_last_line':lines[-1][:200] if lines else None,'sealed_reproducer_contract_ok':bool(lines and lines[-1]==expected and repro.returncode==(1 if label=='baseline' else 0))})
report={'schema':'forge-c/unsubmitted-candidate-independent-check/1','at':utc_now(),'source_provenance_sha256':sha256_file(S/'provenance.json'),'checker_sha256':sha256_file(G),'rows':rows,'model_requests':0,'broker_receipt':False,'candidate_commit_created':False,'production_source_changed':False,'existing_cre_decision':'NOT_RUN_NO_VALID_SUBMISSION','scope':'Independent checks of actual Qwen-written bytes only; no acceptance or promotion implied'};immutable_json(D/'result.json',report);print(json.dumps(report,indent=2))
