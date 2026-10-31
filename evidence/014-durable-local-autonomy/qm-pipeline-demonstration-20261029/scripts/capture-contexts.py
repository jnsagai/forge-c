"""Model-free Fabro request capture. Only a scripted read-only use_skill reply; never a model endpoint."""
from pathlib import Path
import os,sys,json,time,subprocess,threading,signal,urllib.request,re
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
P=Path('/mnt/data/forge-c/production-local-014');Q=P/'deployment/qualification-qm-demo-15b0fa5';R=Q/'repo'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#'):
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.afo.operations import Intent
from forge_factory.afo.queue import ReadSnapshot
from forge_factory.afo.execution_lifecycle import Executions
intent=Intent()
def pending():
 with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as production:
  return Executions(production).pending()
assert intent.read()['mode']=='RUNNING' and intent.read()['epoch']==26
assert not pending()
sys.path.pop(0)
for k in list(sys.modules):
 if k=='forge_factory' or k.startswith('forge_factory.'):del sys.modules[k]
for k in list(os.environ):
 if k.startswith(('FORGE_','FABRO_','OLLAMA_')):os.environ.pop(k)
O=Q/'role-context-preflight-high-v1';O.mkdir(mode=0o700)
os.environ.update(FORGE_REPO_ROOT=str(R),FORGE_DATA_ROOT=str(Q/'data'),FORGE_STATE_DIR=str(O/'state'),FORGE_EVENTS_DIR=str(O/'events'),PYTHONDONTWRITEBYTECODE='1')
sys.path.insert(0,str(R/'factory/python'))
from forge_factory import workorder as W,provided_requirements as PR,acp
from forge_factory.common import pretty_json
from forge_factory.afo.durable import digest,immutable_json
from forge_factory.lrtx import profile,stack
from forge_factory.llm_gateway import sanitize_request,detect_role
from forge_factory.afo.diagnosis_packet import measure_request
from forge_factory.policy.authz import Binding
from forge_factory.fabro.runconfig import write_run,fabro_env
from forge_factory.mcp.preflight import fabro_mcp_config,preflight as mcp_preflight
from forge_factory.fabro.client import FabroClient,load_token,run_status
source=subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()
assert source=='15b0fa59a5eb71dc7b921e8dcf67352520dd8de4'
assert not subprocess.check_output(['git','-C',str(R),'status','--porcelain'],text=True).strip()
prof=profile.load('local-rtx-v2-omniverse2-q38-qm-demo-mtp');model=prof['models']['default']
root=O/'stack';root.mkdir()
subprocess.run(['cp','-a','--reflink=auto',str(P/'venv'),str(root/'venv')],check=True)
settings={'profile':prof,'root':root,'ports':{'fabro':32591,'gateway':32592,'ollama':32593,'llama':32594}}
stack.init(settings)
env={**os.environ,**stack.envmap(settings),'FORGE_FABRO_BIN':'/mnt/data/forge-c/fabro-0.362.0/fabro-x86_64-unknown-linux-musl/fabro','FABRO_NO_UPGRADE_CHECK':'1'}
for line in (root/'fabro/storage/server.env').read_text().splitlines():
 k,v=line.split('=',1);env[k]=v
captures=[];lock=threading.Lock()
class Fake(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def send_json(self,code,value):
  raw=json.dumps(value).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_GET(self):self.send_json(200,{'data':[{'id':model,'object':'model'}],'models':[{'name':model}]})
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers['Content-Length'])));role=detect_role(body.get('messages') or [])
  if not body.get('messages'):
   self.send_json(429,{'error':{'message':'PREFLIGHT_ONLY_NO_GENERATION'}});return
  with lock:
   idx=len(captures);immutable_json(O/f'request-{idx:03d}.json',body)
   effective=sanitize_request(body,policy=prof['gateway']['reasoning']);measurement=measure_request(effective)
   cap=effective.get('max_tokens',effective.get('max_completion_tokens'))
   record={'index':idx,'role':role,'supplied_sha256':digest(body),'measurement':measurement,'effective_output_cap':cap,'total':measurement['input_tokens']+(cap or 0),'scripted_read_only_reply':False}
   captures.append(record);(O/'captures.json').write_text(pretty_json(captures))
  tools=body.get('tools') or [];tool=next((t for t in tools if t.get('function',{}).get('name')=='use_skill'),None)
  has_skill=any(m.get('role')=='tool' for m in body.get('messages') or [])
  if role and tool and not has_skill:
   record['scripted_read_only_reply']=True
   chunk={'id':'preflight-skill','object':'chat.completion.chunk','model':model,'choices':[{'index':0,'delta':{'role':'assistant','tool_calls':[{'index':0,'id':'preflight-skill-call','type':'function','function':{'name':'use_skill','arguments':json.dumps({'skill_name':role})}}]},'finish_reason':None}]}
   end={'id':'preflight-skill','object':'chat.completion.chunk','model':model,'choices':[{'index':0,'delta':{},'finish_reason':'tool_calls'}],'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}}
   raw=('data: '+json.dumps(chunk)+'\n\ndata: '+json.dumps(end)+'\n\ndata: [DONE]\n\n').encode()
   self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
  else:self.send_json(429,{'error':{'message':'PREFLIGHT_CAPTURE_COMPLETE_NO_GENERATION','type':'preflight_only'}})
http=ThreadingHTTPServer(('127.0.0.1',32592),Fake);threading.Thread(target=http.serve_forever,daemon=True).start()
fb=env['FORGE_FABRO_BIN'];child=None;started=time.monotonic();halt=[]
def guard():
 while time.monotonic()-started<600:
  now=intent.read()
  if now['mode']!='RUNNING' or now['epoch']!=26 or pending():
   halt.append('NEW_OPERATOR_INTENT_OR_EXECUTION');break
  time.sleep(.5)
 else:halt.append('PREFLIGHT_TIMEBOX')
 if child and child.poll() is None:child.terminate()
threading.Thread(target=guard,daemon=True).start()
try:
 child=subprocess.Popen([fb,'server','start','--foreground','--no-web','--no-upgrade-check','--config',str(root/'fabro/settings.toml'),'--storage-dir',str(root/'fabro/storage')],env=env,stdout=(O/'fabro.log').open('w'),stderr=subprocess.STDOUT)
 os.environ.update(env)
 for _ in range(120):
  try:
   with urllib.request.urlopen('http://127.0.0.1:32591/health',timeout=1) as r:
    if r.status==200:break
  except Exception:time.sleep(.5)
 else:raise RuntimeError('PREFLIGHT_FABRO_START_FAILED')
 ws,man=W.prepare(R/'examples/0014f-st-cube-crc-idr-qm','WO-AFO-d9ddb6d7a1c4e025-a1',purpose='QM',execution_policy=prof['development_execution_policy'])
 Binding('idr-context-preflight',str(ws),{'swe1_author':{'role':'swe1-author','phase':'SWE.1'}}).dump(ws/'.forge-run/binding.json')
 PR.materialize(ws)
 from forge_factory.inspection.engine import Store as InspectionStore
 from forge_factory.lrtx import review
 st=InspectionStore(ws);st.freeze('SWE.1','swe1-author')
 bl,srcs=review.evidence(ws,'SWE.1');structured=[]
 for item in st.applicable(st.checklist('SWE.1'))['checks']:
  if not item.get('required') or item.get('deterministic_check'):continue
  packet=review.item_packet(ws,'SWE.1',item,bl,srcs,model)
  body=dict(model=model,messages=packet['_messages'],stream=True,max_tokens=packet['output_reserve'],stream_options={'include_usage':True},response_format={'type':'json_schema','json_schema':{'name':'packet_output','strict':True,'schema':packet['output_schema']}},**packet.get('sampling',{}))
  structured.append({'role':'swe1-inspector','body':body})
 immutable_json(O/'structured-requests.json',structured)
 secmap={}
 for line in (ws/'inputs/index.md').read_text().splitlines():
  parts=[x.strip() for x in line.split(' | ')]
  if len(parts)==4 and parts[0][:1].isdigit() and parts[0] not in secmap:secmap[parts[0]]=parts[3]
 graph_goal=f"{man['driver']} for {man['target'].get('part_number')} (offline review)"
 graph,nodes=W.build(man['work_order'],goal=graph_goal,sections=secmap,chunk_lines=40,layer=man.get('layer','LL+HAL'),trace=man.get('trace_profile')==W.TRACE_PROFILE,isolation=man.get('hal_unit_isolation')==W.HAL_UNIT_ISOLATION,brownfield=man.get('code_mode') if man.get('delivery') else None,peripheral=man.get('peripheral'),operation_scope=man.get('operation_scope'),execution_policy=man.get('development_execution'),assessment_manifest=man,delivery_style=((man.get('delivery') or {}).get('build') or {}).get('style'),structured=W.local_profile_structured(prof,man,model))
 binding=Binding('idr-context-preflight',str(ws),nodes)
 mcp=fabro_mcp_config(mcp_preflight(sorted({x['role'] for x in nodes.values()}),live=False)['servers'])
 complete_toml=write_run(ws,graph,f"{man['work_order']} {man['driver']}",binding,mcp,model=model)
 validated=subprocess.run([fb,'validate',str(complete_toml)],cwd=ws,env=fabro_env(),capture_output=True,text=True,timeout=60)
 (O/'complete-workflow-validation.log').write_text(validated.stdout+validated.stderr)
 assert validated.returncode==0 and 'Validation: OK' in validated.stdout+validated.stderr
 (O/'complete-workflow.fabro').write_text(graph)
 statements=[(name,graph[a:b]) for a,b,_,name,attrs in acp.statements(graph) if name in nodes and 'prompt=' in attrs]
 # Native phase bodies use exact builder node statements; no engineering answer or tool mutation is scripted.
 selected=statements[:1] if os.environ.get('FC014_CAPTURE_FIRST_ONLY')=='1' else statements
 output=['digraph Preflight {',' graph [goal='+json.dumps(graph_goal)+', default_fidelity="compact"]',' start [shape=Mdiamond]',' exit [shape=Msquare]']
 prev='start'
 for name,stmt in selected:
  output.append(re.sub(r'timeout="[^"]+"','timeout="20s"',stmt));output.append(f' {prev} -> {name}');prev=name
 output += [f' {prev} -> exit','}']
 binding=Binding('idr-context-preflight',str(ws),nodes);toml=write_run(ws,'\n'.join(output),f"{man['work_order']} {man['driver']}",binding,fabro_mcp_config(mcp_preflight(sorted({x['role'] for x in nodes.values()}),live=False)['servers']),model=model)
 result=subprocess.run([fb,'run',str(toml),'--detach','--environment','local','--label','forge=IDR-PREFLIGHT-NO-MODEL'],cwd=ws,env=fabro_env(),capture_output=True,text=True,timeout=60)
 assert result.returncode==0,(result.stderr or result.stdout)[-2000:]
 rid=result.stdout.strip().splitlines()[-1]
 client=FabroClient(base_url='http://127.0.0.1:32591',token=load_token(str(root/'fabro/storage')))
 deadline=time.monotonic()+min(500,25*len(selected)+30)
 while time.monotonic()<deadline and not halt:
  if run_status(client.get_run(rid)) in ('SUCCEEDED','FAILED','CANCELLED'):break
  time.sleep(1)
 else:client.cancel(rid)
 report={'source_revision':source,'native_run_id':rid,'status':run_status(client.get_run(rid)),'captures':captures,'expected_native_nodes':[n for n,_ in selected],'native_nodes':len(selected),'halt':halt,'model_generation_requests':0,'complete_native_workflow_validation':'PASS','scripted_provider':'use_skill read-only then typed rejection; preflight only, no product verdict','production_policy_or_mission_changed':False,'work_order':man['work_order'],'section_count':len(secmap),'graph_goal':graph_goal,'assessment_purpose':man['purpose'],'capture_scope':'Actual generated native prompt statements, inputs section map, work-order and goals; linear isolated initial and skill-load capture only. Later tool histories remain subject to normal gateway admission.'}
 immutable_json(O/'result.json',report);print(json.dumps(report))
finally:
 http.shutdown()
 if child and child.poll() is None:
  child.terminate()
  try:child.wait(timeout=10)
  except subprocess.TimeoutExpired:child.kill();child.wait()
