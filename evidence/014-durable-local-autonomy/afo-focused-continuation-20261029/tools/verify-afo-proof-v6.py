"""Operator qualification only: frozen external checks of a quiescent submitted candidate."""
from pathlib import Path
import json,os,sys,subprocess,time,xml.etree.ElementTree as ET
P=Path('/mnt/data/forge-c/production-local-014');O=P/'deployment/afo-repair-live-20261029-v6'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo import maintainer as M
from forge_factory.afo.durable import immutable_json
from forge_factory.common import sha256_file,utc_now
from forge_factory.reliability import isolation
scope=json.loads((O/'scope.json').read_text())
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as db:
    with db.tx() as c:
        rows=c.execute('SELECT record FROM afo_local_agent_jobs WHERE order_id=?',(scope['new_order_id'],)).fetchall();assert len(rows)==1
        job=json.loads(rows[0][0]);jid=job['job_id']
        execution=json.loads(c.execute('SELECT record FROM afo_execution_liveness WHERE job_id=?',(jid,)).fetchone()[0])
        busy=c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchall()
        if execution['execution_liveness']!='QUIESCENT' or execution['resource_lease']!='RELEASED' or busy:
            print(json.dumps({'status':'NOT_READY','model_or_existing_verifier_still_live':True}));raise SystemExit(3)
        if c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone():
            print(json.dumps({'status':'NOT_READY','another_inference_owner':True}));raise SystemExit(3)
        proposals=[r[0] for r in c.execute('SELECT status FROM afo_maintainer_proposals WHERE order_id=? ORDER BY seq',(scope['new_order_id'],))]
case=json.loads(Path(job['case']).read_text())
if not (Path(job['case']).parent/'submission.json').is_file():
    print(json.dumps({'status':'NO_SUBMITTED_CANDIDATE','job_state':job['state'],'error':job.get('error')}));raise SystemExit(4)
sub,receipt=M.submission(case,require_receipt=True)
repo=Path(case['repo']);paths=M.changed_paths(case['base'],sub['candidate'],repo)
assert not sub['veto']
assert paths and all(p=='factory/python/forge_factory/fabro/runconfig.py' or p.startswith('factory/python/tests/afo_candidate/') for p in paths),paths
G=P/'deployment/afo-repair-trial-20261029-v2/verifier/test_tool_context.py'
inv=json.loads((P/'deployment/afo-repair-trial-20261029-v2/inventory.json').read_text())
assert sha256_file(G)==inv['verifier/test_tool_context.py']['sha256']
out=O/'independent-candidate-check';out.mkdir(mode=0o700)
# Recover immutable submitted content even if the broker quarantined its mutable worktree.
import io,tarfile
src=out/'candidate-source';src.mkdir(mode=0o700)
archive=subprocess.check_output(['git','-C',str(repo),'archive',sub['candidate']])
with tarfile.open(fileobj=io.BytesIO(archive)) as tf:tf.extractall(src,filter='data')
(out/'candidate.patch').write_bytes(subprocess.check_output(['git','-C',str(repo),'diff','--binary',case['base'],sub['candidate']]))
for f in src.rglob('*'):
 if not f.is_symlink():f.chmod(f.stat().st_mode & ~0o222)

scratch=out/'scratch';scratch.mkdir(mode=0o777);scratch.chmod(0o777)
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:2]);os.nice(10)
env={'PATH':str(P/'venv/bin')+':/usr/bin:/bin','LANG':'C.UTF-8','PYTHONPATH':str(src/'factory/python'),
 'FORGE_REPO_ROOT':str(src),'FORGE_DATA_ROOT':str(scratch),'FORGE_STATE_DIR':str(scratch/'state'),
 'TMPDIR':str(scratch),'HOME':str(scratch),'PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','FORGE_FABRO_LIVE':'0'}
command=[str(P/'venv/bin/python'),'-m','pytest','-q','-p','no:cacheprovider','--rootdir',str(G.parent),str(G),
 '--junitxml='+str(scratch/'pytest.xml')]
start=time.time()
r=isolation.execute('verifier',command,cwd=scratch,env=env,writable=[scratch],readable=[src,G.parent],timeout=90)
(out/'pytest.log').write_bytes(r.stdout+r.stderr)
xml=scratch/'pytest.xml';suite=next(ET.parse(xml).getroot().iter('testsuite')) if xml.exists() else None
passed=r.returncode==0 and suite is not None and suite.get('tests')=='2' and all(suite.get(k)=='0' for k in ('errors','failures','skipped'))
report={'schema':'forge-c/afo-independent-candidate-check/1','status':'PASS_FROZEN_SCOPE_CHECK' if passed else 'FAIL_FROZEN_SCOPE_CHECK',
 'candidate':sub['candidate'],'case_sha256':sha256_file(Path(job['case'])),'submission_receipt_sha256':sha256_file(Path(job['case']).parent/'submission-receipt.json'),
 'job_id':jid,'native_run_id':job['run_id'],'scope_sha256':sha256_file(O/'scope.json'),'paths':paths,
 'checker_sha256':sha256_file(G),'command':command,'exit_code':r.returncode,'tests':dict(suite.attrib) if suite is not None else None,
 'sandbox_backend':isolation.backend(),'network':False,'gpu_devices_exposed':False,'cpu_affinity':sorted(os.sched_getaffinity(0)),
 'existing_cre_status_history':proposals,'started_epoch':start,'finished_at':utc_now(),
 'claim':'Frozen external context/scope checks only; full self-healing requires existing CRE acceptance and external deployment boundary',
 'model_requests':0,'production_source_changed':False,'candidate_source_basis':'git archive of broker receipt-bound immutable commit; no quarantined worktree resurrection'}
immutable_json(out/'result.json',report);print(json.dumps(report),flush=True)
raise SystemExit(0 if passed else 2)
