"""Owner-authorized AFO limit deployment; retain provider, missions and terminal jobs."""
from pathlib import Path
import json,os,subprocess,sys,time,xml.etree.ElementTree as ET
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo'
Q=P/'deployment/qualification-afo-paging-979dcb4-v2'
O=P/'deployment/afo-paging-activation-20261029'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import operations
from forge_factory.afo.queue import Store
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import immutable_json,digest
from forge_factory.common import utc_now
from forge_factory.lrtx import stack
REV='979dcb406353b5c779cd7b61964e3e5f39add454';OLD='3f1ef1b734f72e868a75488d980a2b4ac7c63998'
PROFILE='local-rtx-v2-omniverse2-q38-afo-repair-mtp'
def git(root,*args):return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
assert git(R,'rev-parse','HEAD')==OLD and not git(R,'status','--porcelain')
assert git(Q/'repo','rev-parse','HEAD')==REV and not git(Q/'repo','status','--porcelain')
provenance=json.loads((Q/'provenance.json').read_text())
assert provenance['source_revision']==REV and provenance['pytest_exit_code']==0
assert provenance['source_clean_before'] and provenance['source_clean_after'] and not provenance['halt']
assert provenance['test_user_mapping']=='current_user_not_namespace_root'
suite=next(ET.parse(Q/'pytest.xml').getroot().iter('testsuite'))
assert suite.get('tests')=='154' and all(suite.get(k)=='0' for k in ('failures','errors'))
assert {c.get('name') for c in suite.iter('testcase') if c.find('skipped') is not None} <= {
 'test_candidate_tests_run_as_sandbox_uid_without_credentials_or_network','test_t018_live_fabro_calls_forge_mcp_through_ticket_gate'}
S=Store();I=operations.Intent();L=MissionLedger(S);settings=stack.settings(PROFILE)
provider=stack.serving_instance(settings)
def quiet():
    assert not Executions(S).pending()
    with S.tx() as c:
        assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
        assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
        assert not c.execute("SELECT job_id FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()
def history():
    with S.tx() as c:mids=[r[0] for r in c.execute('SELECT mission_id FROM afo_missions')]
    return {mid:L.snapshot(mid) for mid in mids}
assert I.read()['mode']=='RUNNING' and I.read()['epoch']==36
quiet();before=history()
assert time.time()<before['F014-IDR-M1-HIGH-20261028']['limits']['deadline']
O.mkdir(mode=0o700)
scope={'schema':'forge-c/afo-paging-deployment/1','source_revision':REV,'previous_source_revision':OLD,
 'owner_request':'increase largely those limits to avoid this problem now',
 'owner_sizing_request':'take a look on the drivers implemented using codex workflow, to check the maximum size of their code files to remap the page size',
 'standing_signing_activation_delegation':'always approve it for now on automatically',
 'limits':{'page_target_characters':32768,'serialized_response_bytes':65536,'tool_calls_per_role':200,'source_read_bytes':4194304},
 'profile':PROFILE,'context_tokens':131072,'deadline_changed':False,'new_run_authorized_or_started':False,
 'measured_sizes':{'codex_workspaces':92,'workflow_output_driver_max_bytes':7278,'delivered_driver_max_bytes':340069,'test_header_max_bytes':3599048},
 'preserve_provider_instance':True,'mission_counters_reset':False,'old_job_limits_rebound':False,
 'model_generation_requests':0,'qualified_native_case_counts':dict(suite.attrib),'at':utc_now()}
immutable_json(O/'scope.json',scope);immutable_json(O/'mission-history-before.json',before)
immutable_json(O/'provider-before.json',provider)
paused=operations.synchronize(S,'pause',str(os.getuid()),'Owner requested larger AFO pages/tool allowances, sized from recorded Codex driver files; activate exact tested source only',
 expected_epoch=36,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
assert paused['epoch']==37
def fenced(effect):
    with I.lock():
        assert I.read()['mode']=='PAUSED' and I.read()['epoch']==37
        quiet();assert stack.serving_instance(settings)==provider
        return effect()
fenced(lambda:subprocess.run(['systemctl','--user','stop',operations.UNIT],check=True,timeout=45))
def promote():
    assert operations.observed_unit().get('ActiveState') in ('inactive','failed')
    subprocess.run(['git','-C',str(R),'fetch',str(Q/'repo'),'HEAD'],check=True,capture_output=True)
    subprocess.run(['git','-C',str(R),'merge','--ff-only',REV],check=True,capture_output=True)
    assert not git(R,'status','--porcelain')
    assert history()==before
    code="from forge_factory.registry.agents import preflight,load_agents; from forge_factory.mcp.servers.afo_payload import PAGE_CHARS,MAX_RESPONSE_BYTES; from forge_factory.afo.maintainer import MAX_SOURCE_READ_BYTES; import json; p=preflight(['afo-recovery-planner','afo-factory-maintainer'],include_afo=True); assert p['status']=='PASS',p; print(json.dumps({'preflight':p['status'],'page_chars':PAGE_CHARS,'response_bytes':MAX_RESPONSE_BYTES,'read_bytes':MAX_SOURCE_READ_BYTES,'roles':{a.id:{'tool_calls':a.max_turns,'response_bytes':a.max_mcp_output_bytes} for a in load_agents(include_afo=True)[0] if a.id.startswith('afo-')}}))"
    checked=subprocess.run([str(P/'venv/bin/python'),'-c',code],cwd=R,
        env={**os.environ,'PYTHONPATH':str(R/'factory/python'),'FORGE_REPO_ROOT':str(R)},capture_output=True,text=True,check=True,timeout=30)
    immutable_json(O/'installed-limits.json',json.loads(checked.stdout))
fenced(promote)
resumed=operations.synchronize(S,'resume',str(os.getuid()),'Exact qualified larger AFO limits installed; retain loaded Qwen and existing deadline/history; no new trial dispatch',
 expected_epoch=37,authentication={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()})
assert resumed['epoch']==38
with I.lock():
    assert I.read()['mode']=='RUNNING' and I.read()['epoch']==38
    quiet();assert history()==before and stack.serving_instance(settings)==provider
    subprocess.run(['systemctl','--user','--no-block','start',operations.UNIT],check=True,timeout=20)
    record={'status':'AFO_LIMITS_ACTIVE_CONDUCTOR_RESTART_REQUESTED','source_revision':REV,'scope_sha256':digest(scope),
      'operator_epoch':38,'provider_instance_unchanged':True,'mission_history_unchanged':True,
      'model_requests':0,'new_orders':0,'deadline_changed':False,'at':utc_now()}
    immutable_json(O/'activation.json',record);print(json.dumps(record),flush=True)
