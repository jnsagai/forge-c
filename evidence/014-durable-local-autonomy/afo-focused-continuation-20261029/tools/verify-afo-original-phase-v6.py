"""Run frozen independent candidate check, then compare baseline/candidate on original failed diagrams."""
from pathlib import Path
import hashlib,io,json,os,subprocess,sys,tarfile,time
P=Path('/mnt/data/forge-c/production-local-014');O=P/'deployment/afo-repair-live-20261029-v6';R=P/'repo'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import maintainer as M
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.durable import immutable_json
from forge_factory.common import sha256_file,utc_now
from forge_factory.reliability import isolation
s=json.loads((O/'scope.json').read_text())
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as db:
 with db.tx() as c:
  j=json.loads(c.execute('SELECT record FROM afo_local_agent_jobs WHERE order_id=?',(s['new_order_id'],)).fetchone()[0]);x=json.loads(c.execute('SELECT record FROM afo_execution_liveness WHERE job_id=?',(j['job_id'],)).fetchone()[0])
  assert x['execution_liveness']=='QUIESCENT' and x['resource_lease']=='RELEASED'
  assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
case=json.loads(Path(j['case']).read_text());sub,receipt=M.submission(case,require_receipt=True)
assert not sub['veto']
root=O/'original-swe3-phase-recovery';root.mkdir(mode=0o700)
checker=O/'check-afo-original-phase-v6.py';immutable_json(root/'frozen-checker.json',{'sha256':sha256_file(checker),'candidate':sub['candidate'],'case_sha256':sha256_file(Path(j['case'])),'submission_receipt_sha256':sha256_file(Path(j['case']).parent/'submission-receipt.json')})
actual=P/'deployment/qualification-swe6-stop-3015e47-v4';frozen=P/'deployment/afo-repair-live-20261029-v4/original-swe3-replay-input';assert (frozen/'inventory.json').is_file();inventory=json.loads((frozen/'inventory.json').read_text());assert all(sha256_file(frozen/'workspace'/r['path'])==r['sha256'] for r in inventory['files'])
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);os.nice(10)
rows=[]
for label,rev in [('baseline',case['base']),('candidate',sub['candidate'])]:
 src=root/(label+'-source');src.mkdir(mode=0o700)
 with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','-C',case['repo'],'archive',rev]))) as tf:tf.extractall(src,filter='data')
 for f in src.rglob('*'):
  if not f.is_symlink():f.chmod(f.stat().st_mode & ~0o222)
 scratch=root/(label+'-scratch');scratch.mkdir(mode=0o777);scratch.chmod(0o777)
 env={'PATH':str(P/'venv/bin')+':/usr/bin:/bin','LANG':'C.UTF-8','PYTHONPATH':str(src/'factory/python'),'FORGE_REPO_ROOT':str(src),'FORGE_DATA_ROOT':str(actual/'data'),'FORGE_STATE_DIR':str(scratch/'state'),'TMPDIR':str(scratch),'HOME':str(scratch),'PYTHONDONTWRITEBYTECODE':'1','FORGE_FABRO_LIVE':'0'}
 import shutil
 ws=scratch/'workspace';shutil.copytree(frozen/'workspace',ws)
 for f in ws.rglob('*'):
  if f.is_file() and not f.is_symlink():f.chmod(0o644)
 command=[str(P/'venv/bin/python'),str(checker),str(ws),str(scratch)]
 run=isolation.execute('verifier',command,cwd=scratch,env=env,writable=[scratch],readable=[src,actual/'data',checker],timeout=200)
 (root/(label+'.log')).write_bytes(run.stdout+run.stderr)
 result=json.loads((scratch/'result.json').read_text()) if (scratch/'result.json').exists() else None
 rows.append({'label':label,'revision':rev,'exit_code':run.returncode,'result':result,'log_sha256':sha256_file(root/(label+'.log'))})
passed=rows[0]['exit_code']==2 and rows[1]['exit_code']==0 and rows[1]['result'] and rows[1]['result'].get('result',{}).get('verdict')=='PASS'
report={'schema':'forge-c/afo-original-workflow-recovery-check/1','status':'PASS_ORIGINAL_SWE3_DETERMINISTIC_PHASE_RECOVERED' if passed else 'FAIL_OR_INCOMPLETE','runs':rows,'candidate':sub['candidate'],'job_id':j['job_id'],'native_run_id':j['run_id'],'model_requests':0,'production_changed':False,'independent_checker_sha256':sha256_file(checker),'at':utc_now(),'scope':'Original SWE.3 deterministic phase on exact frozen input copies, via generated MCP child environment. Not complete SWE.1-6 product acceptance.','sandbox':isolation.backend(),'network':False,'gpu':False}
immutable_json(root/'result.json',report);print(json.dumps(report));raise SystemExit(0 if passed else 2)
