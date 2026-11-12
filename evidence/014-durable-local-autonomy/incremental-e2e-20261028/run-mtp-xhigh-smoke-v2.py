"""Isolated, signed, two-request MTP/xhigh gateway + actual MCP-stdio smoke; no product/deploy claim."""
from pathlib import Path
import os,sys,json,time,hashlib,subprocess,urllib.request,signal,socket,threading,asyncio
P=Path('/mnt/data/forge-c/production-local-014');Q=P/'deployment/mtp-xhigh-d3f0b28-v2-20261028';R=Q/'repo'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#'):
  k,v=line.split('=',1);os.environ[k]=v
os.environ['FORGE_REPO_ROOT']=str(R);sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.operations import Intent,synchronize
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.queue import Store
from forge_factory.afo import authz,policy
from forge_factory.afo.durable import digest
from forge_factory.afo.diagnosis_packet import measure_request
from forge_factory.lrtx import profile,stack,structured
from forge_factory.common import utc_now
scope=json.loads((Q/'scope.json').read_text());grant=json.loads((Q/'authorization.json').read_text())
assert scope['script_sha256']==hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==scope['source_revision']
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'],text=True).strip()
prof=profile.load(scope['profile']);assert prof['_sha256']==scope['profile_sha256']
assert prof['runtime']['llama_server']['slots']==prof['admission']['max_inflight']==1
assert grant['signed_runbook_ref']=='backend-smoke-014:'+digest(scope)
store=Store();intent=Intent();auth={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()}
report={'schema':'forge-c/backend-smoke/1','scope_sha256':digest(scope),'started_at':utc_now(),'requests':[],
 'source_revision':scope['source_revision'],'profile_sha256':prof['_sha256'],'production_deployed':False,
 'scope':'Qwen MTP/xhigh + gateway + actual MCP stdio/ticket; seeded plumbing fixture, not M1/role qualification'}
def save(): (Q/'result.json').write_text(json.dumps(report,indent=2)+'\n')
def authority():
 eff=policy.load(log=False);assert not eff.issues and eff.sha256==grant['policy_sha256']
 decision=authz.verify(grant,policy_sha256=eff.sha256,mode='PILOT',action='qualify_backend',base=Q,
  request={'order_id':scope['scope_id'],'driver_class':'LL','model':scope['model']},revoked=authz.revoked_ids(authz.REVOKED))
 assert decision.allow,decision.code
def quiet():
 assert not Executions(store).pending(),'LIVE_EXECUTION'
 with store.tx() as c:
  assert not any(r[0] for r in c.execute('SELECT holder FROM afo_resource_ownership')),'RESOURCE_HELD'
  assert c.execute("SELECT count(*) FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()[0]==0,'REQUEST_UNSETTLED'
  assert c.execute("SELECT count(*) FROM afo_verification_jobs WHERE state IN ('READY','DISPATCHING','RUNNING','CANCELLING')").fetchone()[0]==0,'VERIFICATION_PENDING'
authority();quiet()
for port in (32577,32578):
 with socket.socket() as probe:probe.bind(('127.0.0.1',port))
old=intent.read();assert old['mode']=='RUNNING' and old['epoch']==20,old
paused=None
children=[];stop_watch=threading.Event();halt=[];deadline=min(scope['deadline_epoch'],time.time()+900)
def stop_children():
 for child in reversed(children):
  if child.poll() is None:
   child.terminate()
   try:child.wait(timeout=5)
   except subprocess.TimeoutExpired:child.kill();child.wait(timeout=3)
def fence():
 current=intent.read()
 assert current['mode']=='PAUSED' and current['epoch']==paused['epoch'],'OPERATOR_INTENT_CHANGED'
 assert time.time()<deadline,'SMOKE_DEADLINE'
def watch():
 while not stop_watch.wait(.5):
  try:fence()
  except BaseException as exc:
   halt.append(type(exc).__name__+':'+str(exc));stop_children();return
thread=threading.Thread(target=watch,daemon=True)
clean={k:v for k,v in os.environ.items() if not k.startswith(('FORGE_','FABRO_','OLLAMA_'))}
clean['PATH']=str(P/'venv/bin')+':'+str(P/'toolchains/LLVM-19.1.7-Linux-X64/bin')+':/usr/local/bin:/usr/bin:/bin'
ws=Q/'workspace';(ws/'software/src').mkdir(parents=True,exist_ok=True);(ws/'software/src/probe.c').write_text('int backend_probe(void){return 0;}\n')
toolenv={**clean,'PYTHONPATH':str(R/'factory/python'),'FORGE_REPO_ROOT':str(R),'FORGE_STATE_DIR':str(Q/'tool-state'),
 'FORGE_DATA_ROOT':str(Q/'tool-data'),'FORGE_BINDING_ID':scope['scope_id']}
def request(body):
 from forge_factory.llm_gateway import sanitize_request
 fence();authority()
 effective=sanitize_request(body,policy=prof['gateway']['reasoning'])
 measured=measure_request(effective);bound=measured['input_tokens']+effective['max_tokens']
 assert bound<=65536 and len(report['requests'])<2
 assert sum(x['conservative_reservation'] for x in report['requests'])+bound<=scope['max_conservative_tokens']
 rec={'request_sha256':digest(body),'measurement':measured,'effective_output_cap':effective['max_tokens'],
 'reasoning_effort':effective['reasoning_effort'],'conservative_reservation':bound,'state':'SENT','reported_usage':None}
 report['requests'].append(rec);save();started=time.monotonic()
 req=urllib.request.Request('http://127.0.0.1:32578/v1/chat/completions',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=max(1,deadline-time.time())) as response:out=json.load(response)
 rec.update(state='QUIESCENT',wall_seconds=time.monotonic()-started,reported_usage=out.get('usage'));save()
 return out
async def protocol():
 from mcp import ClientSession,StdioServerParameters
 from mcp.client.stdio import stdio_client
 from forge_factory.policy.authz import Binding,Authorizer
 from forge_factory.mcp import sdk
 from forge_factory.registry.mcp_registry import fabro_tool_name
 binding=Binding(scope['scope_id'],str(ws),{'swe3_author':{'role':'swe3-author','phase':'SWE.3'}})
 old_state=os.environ.get('FORGE_STATE_DIR');os.environ['FORGE_STATE_DIR']=toolenv['FORGE_STATE_DIR']
 try:
  params=StdioServerParameters(command=str(P/'venv/bin/python'),args=['-m','forge_factory.mcp.servers.build'],env=toolenv)
  with (Q/'mcp-server.log').open('w') as err:
   async with stdio_client(params,errlog=err) as (reader,writer):
    async with ClientSession(reader,writer) as session:
     await session.initialize();listed=await session.list_tools()
     configure=next(t for t in listed.tools if t.name=='configure')
     name=fabro_tool_name('forge-build-mcp.configure')
     tools=[{'type':'function','function':{'name':name,'description':configure.description,'parameters':configure.input_schema}}]
     messages=[{'role':'system','content':structured.skill('swe3-author')['text']+'\nUse skill_name swe3-author. This is a seeded backend protocol qualification, not a driver implementation. Call only the provided configure tool exactly once with profile host-clang. After its actual result, return only JSON with status and observed_sources. Do not invent a tool result.'},
               {'role':'user','content':'Check the host-clang toolchain on this seeded workspace, using the provided tool. The actual tool result determines the source count.'}]
     first={'model':scope['model'],'messages':messages,'tools':tools,'tool_choice':{'type':'function','function':{'name':name}},
            'temperature':0,'stream':False,'max_tokens':2048}
     out=await asyncio.to_thread(request,first)
     message=out['choices'][0]['message'];calls=message.get('tool_calls') or []
     assert len(calls)==1 and calls[0]['function']['name']==name,'TOOL_CALL_PROTOCOL_FAILED'
     args=calls[0]['function']['arguments'];args=json.loads(args) if isinstance(args,str) else args
     assert args=={'profile':'host-clang'},'TOOL_ARGUMENT_PROTOCOL_FAILED'
     decision=Authorizer(binding).decide('swe3_author',name,args);assert decision.allow,decision.code
     ticket=sdk.issue_ticket(scope['scope_id'],name,args,'swe3-author','swe3_author','SWE.3',str(ws))
     returned=await session.call_tool('configure',arguments=args)
     result=json.loads(next(c.text for c in returned.content if getattr(c,'type',None)=='text'))
     assert result['status']=='PASS' and result['metrics']['sources']==1,'INDEPENDENT_TOOL_CHECK_FAILED'
     assert not ticket.exists(),'TICKET_NOT_CONSUMED'
     report['tool_result']=result;report['tool_schema_sha256']=digest(configure.input_schema);report['normal_mcp_ticket_consumed']=True
     assistant={'role':'assistant','content':message.get('content') or '', 'tool_calls':calls}
     messages += [assistant,{'role':'tool','tool_call_id':calls[0]['id'],'content':json.dumps(result)}]
     schema={'type':'object','additionalProperties':False,'required':['status','observed_sources'],
      'properties':{'status':{'type':'string','enum':['PASS','BLOCKED']},'observed_sources':{'type':'integer','minimum':0,'maximum':100}}}
     second={'model':scope['model'],'messages':messages,'stream':False,'temperature':0,'max_tokens':2048,
      'response_format':{'type':'json_schema','json_schema':{'name':'backend_smoke_result','strict':True,'schema':schema}}}
     out=await asyncio.to_thread(request,second);content=out['choices'][0]['message'].get('content') or ''
     report['visible_final_sha256']=hashlib.sha256(content.encode()).hexdigest()
     import jsonschema
     value=json.loads(content);jsonschema.validate(value,schema)
     assert value=={'status':'PASS','observed_sources':1},'TOOL_RESULT_NOT_REFLECTED'
     report['independent_result_check']='PASS';report['visible_final']=value;save()
 finally:
  if old_state is None:os.environ.pop('FORGE_STATE_DIR',None)
  else:os.environ['FORGE_STATE_DIR']=old_state
try:
 def interrupted(signum,frame): raise InterruptedError('QUALIFICATION_SIGNAL_OR_WALL_BOUND')
 signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGALRM,interrupted);signal.alarm(900)
 authority();quiet()
 paused=synchronize(store,'pause',str(os.getuid()),'Owner selected MTP; signed bounded xhigh backend smoke',authentication=auth,expected_epoch=20)
 report['pause_epoch']=paused['epoch'];save();thread.start()
 argv,penv,health,models=stack.llama_server_spec(P,prof,{'llama':32577},clean)
 report['server_argv']=argv
 child=subprocess.Popen(argv,env=penv,stdout=(Q/'server.log').open('w'),stderr=subprocess.STDOUT);children.append(child)
 gwenv={**clean,'PYTHONPATH':str(R/'factory/python'),'FORGE_REPO_ROOT':str(R),
  'FORGE_GATEWAY_MAX_INFLIGHT':'1','FORGE_GATEWAY_DROP_RETRIES':'0',
  'FORGE_GATEWAY_REASONING':json.dumps(prof['gateway']['reasoning']),'FORGE_GATEWAY_REQUEST_TIMEOUT_S':'900'}
 gateway=subprocess.Popen([str(P/'venv/bin/python'),'-m','forge_factory.llm_gateway','--port','32578','--upstream','http://127.0.0.1:32577','--meter',str(Q/'usage.jsonl')],
  env=gwenv,stdout=(Q/'gateway.log').open('w'),stderr=subprocess.STDOUT);children.append(gateway)
 start=time.monotonic()
 for url in (health,'http://127.0.0.1:32578/health'):
  while time.monotonic()-start<120:
   fence();assert all(p.poll() is None for p in children),'BACKEND_PROCESS_EXITED'
   try:
    with urllib.request.urlopen(url,timeout=1) as response:
     if response.status==200:break
   except Exception:time.sleep(.5)
  else:raise RuntimeError('BACKEND_START_TIMEOUT')
 asyncio.run(protocol());report['status']='PASS_BACKEND_PROTOCOL_SMOKE'
except BaseException as exc:
 report['status']='FAILED_BACKEND_PROTOCOL_SMOKE';report['error']=type(exc).__name__+':'+str(exc)[:300]
 def leaves(e):
  return [x for c in getattr(e,'exceptions',[]) for x in leaves(c)] if getattr(e,'exceptions',None) else [{'type':type(e).__name__,'error':str(e)[:300]}]
 report['error_leaves']=leaves(exc)
finally:
 signal.alarm(0);stop_watch.set();stop_children()
 if thread.ident is not None:thread.join(timeout=2)
 report['halt_reason']=halt
 for rec in report['requests']:
  if rec['state']=='SENT':rec['state']='QUIESCENT_AFTER_OWN_PROVIDER_EXIT_USAGE_UNKNOWN'
 try:
  current=intent.read()
  if paused is not None and current['mode']=='PAUSED' and current['epoch']==paused['epoch']:
   resumed=synchronize(store,'resume',str(os.getuid()),'Bounded MTP/xhigh backend smoke settled; no production changes',authentication=auth,expected_epoch=paused['epoch'])
   report['resume_epoch']=resumed['epoch']
  else:report['resume_fenced_by_newer_intent']={'mode':current['mode'],'epoch':current['epoch']}
 except Exception as exc:report['resume_error']=type(exc).__name__+':'+str(exc)
 report['finished_at']=utc_now();report['conservative_total']=sum(x['conservative_reservation'] for x in report['requests'])
 report['old_mission_or_policy_modified']=False;save()
print(json.dumps({k:report.get(k) for k in ['status','error','finished_at','resume_epoch','conservative_total']}))
