from pathlib import Path
import os,sys,json
P=Path('/mnt/data/forge-c/production-local-014');O=P/'deployment/afo-repair-live-20261029-v2'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.afo import operations,authority,policy
from forge_factory.afo.queue import Store
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.durable import immutable_json
from forge_factory.common import utc_now,sha256_file
scope=json.loads((O/'scope.json').read_text());S=Store();I=operations.Intent()
answer=json.loads((O/'final-answer.json').read_text());body=json.loads(answer['text'])
assert body['status']=='BLOCKED' and answer['contract_ok'] is False
assert 'MCP tool budget exhausted (22>20)' in body['issues'][0]
with I.lock():
    state=I.read();assert state['mode']=='RUNNING' and state['epoch']==36
    eff=policy.load(log=False)
    d=authority.decide('finalize_blocked',{'order_id':scope['request_id'],'driver_class':'LL','model':scope['model']},afo=eff)
    assert d.allow,d
    ex=Executions(S).get('afo-agent-53b65adbaf6e80cb0886ded1')
    assert ex['execution_liveness']=='QUIESCENT' and ex['resource_lease']=='RELEASED'
    assert ex['task_outcome']=='FAILED_PROTOCOL'
    with S.tx() as c:
        assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
    old=S.order(scope['new_order_id'])
    if old['state']=='WAITING_EXTERNAL_CHANGE':
        S.transition(old['order_id'],'BLOCKED','Actual Qwen final answer reports MCP tool budget exhaustion; no candidate or valid completion receipt',
            expect_version=old['version'],terminal_reason='MAINTENANCE_TOOL_BUDGET_EXHAUSTED_NO_CANDIDATE')
    else:assert old['state']=='BLOCKED'
    report={'status':'BLOCKED_NO_CANDIDATE','order_id':scope['new_order_id'],'native_run_id':'01M64FPV6Y2DYK3BKRRJQSR0NC',
      'actual_final_answer_sha256':sha256_file(O/'final-answer.json'),'native_facts_sha256':sha256_file(O/'native-result.json'),
      'model_reported_block':'MCP tool budget exhausted (22>20)','model_output_contract_valid':False,
      'model_output_contract_issue':'next_action must be an enum, not a free-text re-dispatch instruction',
      'candidate_submission':False,'patch_authored':False,'independent_candidate_check':'NOT_RUN_NO_CANDIDATE',
      'self_healing':'NOT_DEMONSTRATED','operator_mode':'RUNNING','operator_epoch':36,'model_stop_requested':False,
      'automatic_retry_started':False,'historical_charges_reset':False,'at':utc_now()}
    immutable_json(O/'final-result.json',report);print(json.dumps(report),flush=True)
