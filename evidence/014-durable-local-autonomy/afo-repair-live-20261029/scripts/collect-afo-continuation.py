from pathlib import Path
import json,os,sys,hashlib,sqlite3,subprocess
P=Path('/mnt/data/forge-c/production-local-014');O=P/'deployment/afo-repair-live-20261029-v2'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
    if line and not line.startswith('#') and '=' in line:
        k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.fabro.client import FabroClient,load_token
from forge_factory.afo.durable import immutable_json
from forge_factory.common import utc_now
rid='01M64FPV6Y2DYK3BKRRJQSR0NC';jid='afo-agent-53b65adbaf6e80cb0886ded1'
rows=[];calls=[]
with FabroClient(token=load_token(),timeout=10) as client:
    usage=client.usage(rid)
    for e in client.iter_events(rid):
        name=e['event'];p=e['properties'];inner=p.get('event') or {}
        if name=='agent.tool.started':
            v=inner['ToolCallStarted'];args=v.get('arguments') or {}
            row={'seq':e['seq'],'at':e['ts'],'event':name,'tool':v['tool_name'],
                 'arguments':{k:args[k] for k in ('path','offset','skill_name') if k in args}}
            rows.append(row);calls.append(row)
        elif name=='agent.tool.completed':
            v=inner['ToolCallCompleted'];raw=v.get('output','');summary={}
            if v['tool_name']!='use_skill':
                try:
                    data=json.loads(raw);metrics=data.get('metrics') or {}
                    summary={k:data.get(k) for k in ('status','summary','issues','provenance')}
                    summary['page']={k:metrics.get(k) for k in ('offset','total_chars','next_offset','data_sha256')}
                except (ValueError,TypeError,AttributeError):summary={'parse_status':'NON_JSON_TOOL_OUTPUT'}
            rows.append({'seq':e['seq'],'at':e['ts'],'event':name,'tool':v['tool_name'],
                'is_error':v.get('is_error'),'output_sha256':hashlib.sha256(raw.encode()).hexdigest(),
                'output_bytes':len(raw.encode()),'summary':summary})
        elif name=='agent.error':rows.append({'seq':e['seq'],'at':e['ts'],'event':name,'error':inner.get('Error')})
        elif name in ('stage.failed','run.completed'):
            rows.append({'seq':e['seq'],'at':e['ts'],'event':name,'properties':p})
db=P/'state/knowledge/lessons.sqlite3';learning=[]
if db.exists():
    c=sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True)
    try:
        for r in c.execute('SELECT e.experience_id,e.execution_id,e.phase,e.outcome,e.source_hash,d.state FROM job_experience e JOIN learning_dispositions d USING(experience_id) WHERE e.execution_id IN (?,?)',('controller-agent:'+jid,rid)):
            learning.append(dict(zip(('experience_id','execution_id','phase','outcome','source_hash','disposition'),r)))
    finally:c.close()
case=json.loads((P/'state/afo/maintainer/mnt-2cd016a83d71c57d-a1/case.json').read_text());src=Path(case['src'])
report={'schema':'forge-c/afo-repair-trial-native-result/1','at':utc_now(),'native_run_id':rid,'job_id':jid,
 'result':'FAILED_BEFORE_AUTHORING_NATIVE_AGENT_ERROR','request_count':18,
 'tool_calls':calls,'candidate_submission':False,'candidate_dirty':bool(subprocess.check_output(['git','-C',str(src),'status','--porcelain'])),
 'candidate_target_sha256':hashlib.sha256((src/'factory/python/forge_factory/fabro/runconfig.py').read_bytes()).hexdigest(),
 'native_status_is_not_task_success':True,'reported_usage':usage,'event_facts':rows,'learning':learning,
 'hidden_reasoning_saved':False,'model_requests_by_collector':0}
immutable_json(O/'native-result.json',report);print(json.dumps({'result':report['result'],'tools':len(calls),'learning':learning,'candidate_dirty':report['candidate_dirty']}))
