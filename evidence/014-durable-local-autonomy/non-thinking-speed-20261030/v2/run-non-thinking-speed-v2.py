"""Serial speed pilot through existing qualification intake and Conductor. No direct inference."""
from pathlib import Path
import argparse,json,os,re,subprocess,sys,time,statistics,tempfile
P=Path('/mnt/data/forge-c/production-local-014');R=P/'repo';O=P/'deployment/q38-nonthink-speed-20261030-v2'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo import qualification as Q,qualification_intake as intake,qualification_audit as audit,operations,qualification_state
from forge_factory.afo.queue import Store
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo.mission_ledger import MissionLedger
from forge_factory.afo.durable import digest,immutable_json
from forge_factory.lrtx import stack,provider_process
from forge_factory.common import sha256_file,utc_now
ap=argparse.ArgumentParser();ap.add_argument('--variant',choices=('none','medium','xhigh'),required=True);a=ap.parse_args()
E=O/a.variant;manifest=json.loads((E/'campaign.json').read_text());scope=json.loads((O/'scope.json').read_text());activation=json.loads((E/'activation.json').read_text());epoch=json.loads((E/'benchmark-resume.json').read_text())['operator_epoch'] if (E/'benchmark-resume.json').exists() else activation['operator_epoch'];profile=scope['grants'][a.variant]['profile'];aid=scope['grants'][a.variant]['authorization_ref'];deadline=manifest['mission']['limits']['deadline']
S=Store();I=operations.Intent();X=Executions(S);settings=stack.settings(profile);results=E/'results';metrics=E/'metrics';results.mkdir(exist_ok=True);metrics.mkdir(exist_ok=True)
_,_,inputs=intake.authenticated_inputs(manifest);reference=Path(inputs['reference_report']['path'])
def guard():
 r=I.read();assert r['mode']=='RUNNING' and r['epoch']==epoch,'NEWER_OPERATOR_INTENT'
 assert time.time()<deadline,'BENCHMARK_AUTHORITY_EXPIRED'
 assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()==manifest['source_revision']
def quiet():
 assert not X.pending()
 with S.tx() as c:
  assert not c.execute("SELECT request_id FROM afo_request_ledger WHERE state!='QUIESCENT'").fetchone()
  assert not c.execute('SELECT holder FROM afo_resource_ownership WHERE holder IS NOT NULL').fetchone()
def progress(value):
 path=E/'progress.json';fd,name=tempfile.mkstemp(prefix='.progress-',dir=E)
 with os.fdopen(fd,'w') as f:json.dump({'at':utc_now(),'variant':a.variant,'reasoning':a.variant,'mtp_draft':scope['grants'][a.variant]['mtp_draft'],**value},f);f.flush();os.fsync(f.fileno())
 os.replace(name,path)
def gpu():
 try:
  r=subprocess.run(['nvidia-smi','--query-gpu=timestamp,utilization.gpu,memory.used,temperature.gpu,power.draw,power.limit,clocks.sm','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
  return {'columns':['timestamp','utilization_percent','memory_MiB','temperature_C','power_W','power_limit_W','sm_clock_MHz'],'rows':[x.split(', ') for x in r.stdout.splitlines()],'exit_code':r.returncode}
 except Exception as exc:return {'error':type(exc).__name__}
def observed_settings():
 instance=stack.serving_instance(settings);assert not provider_process.quiet(instance)
 found=[];gateway=[]
 for base in Path('/proc').iterdir():
  if not base.name.isdigit():continue
  try:
   if base.stat().st_uid!=os.getuid() or os.readlink(base/'ns/pid')!=instance['init']['pid_namespace']:continue
   argv=(base/'cmdline').read_bytes().decode().split('\0');argv=[v for v in argv if v]
   if argv and Path(argv[0]).name=='llama-server':found.append((int(base.name),argv))
   if 'forge_factory.llm_gateway' in argv:
    env=dict(x.split('=',1) for x in (base/'environ').read_bytes().decode().split('\0') if '=' in x)
    gateway.append(json.loads(env['FORGE_GATEWAY_REASONING']))
  except (FileNotFoundError,ProcessLookupError,PermissionError):continue
 assert len(found)==1 and len(gateway)==1,'NATIVE_SETTINGS_NOT_UNIQUE'
 pid,argv=found[0];flags=['-c','-np','--cache-type-k','--cache-type-v','--spec-type','--spec-draft-n-max','--reasoning','--reasoning-effort','--gpu-layers','--flash-attn','-b','-ub']
 values={f:(argv[argv.index(f)+1] if f in argv else None) for f in flags}
 assert values['-c']=='262144' and values['-np']=='1' and values['--cache-type-k']==values['--cache-type-v']=='f16'
 assert values['--spec-type']=='draft-mtp' and values['--spec-draft-n-max']==str(scope['grants'][a.variant]['mtp_draft']) and values['--reasoning-effort']==(None if a.variant=='none' else a.variant)
 assert gateway[0]['qwen3.8:27b-q8_0']['effort']==a.variant
 assert values['--reasoning']==('off' if a.variant=='none' else 'on')
 return {'source':'KERNEL_PROCFS_PROVIDER_PID_NAMESPACE','identity':manifest['identity'],'llama_pid':pid,'flags':values,'gateway_reasoning':gateway[0],'provider_instance_sha256':digest(instance),'profile_sha256':settings['profile']['_sha256']}
def verify_template():
 from forge_factory.llm_gateway import sanitize_request
 body=sanitize_request({'model':'qwen3.8:27b-q8_0','messages':[{'role':'user','content':'Return a JSON object.'}]},policy=settings['profile']['gateway']['reasoning'])
 expected_off=a.variant=='none'
 assert (body.get('chat_template_kwargs') or {}).get('enable_thinking') is False if expected_off else body['reasoning_effort']==a.variant
 code="import json,urllib.request,hashlib; body="+repr(body)+"; req=urllib.request.Request('http://127.0.0.1:11457/apply-template',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'}); p=json.load(urllib.request.urlopen(req,timeout=8))['prompt']; print(json.dumps({'rendered_prompt_sha256':hashlib.sha256(p.encode()).hexdigest(),'ends_closed_empty_thinking':p.endswith('<think>\\n\\n</think>\\n\\n'),'ends_open_thinking':p.endswith('<think>\\n'),'generation_requests':0}))"
 probe=subprocess.run(stack._nsenter(stack._holder(settings))+[str(P/'venv/bin/python'),'-c',code],capture_output=True,text=True,timeout=15,check=True)
 result=json.loads(probe.stdout)
 assert result['ends_closed_empty_thinking'] is expected_off and result['ends_open_thinking'] is not expected_off
 return {'wire_effort':body['reasoning_effort'],'wire_enable_thinking':(body.get('chat_template_kwargs') or {}).get('enable_thinking'),**result}
guard();tools=json.loads((O/'execution-tools.json').read_text());assert sha256_file(Path(__file__))==tools['run-non-thinking-speed-v2.py']['sha256'];native=observed_settings();native['template_probe']=verify_template();immutable_json(E/'effective-native-settings.json',native)
timing=re.compile(r'task\s+(\d+)\s*\|\s*(prompt eval|eval) time\s*=\s*([0-9.]+) ms /\s*(\d+) tokens')
for index,trial in enumerate(Q.frozen_trials(manifest['cases'])):
 guard();path=results/(trial.replace(':','-')+'.json');mp=metrics/(trial.replace(':','-')+'.json')
 if mp.exists():continue
 startpath=metrics/(trial.replace(':','-')+'-start.json')
 log=P/'logs/llama_server.log';meter=P/'state/llm-gateway/usage.jsonl'
 if not startpath.exists():
  quiet();immutable_json(startpath,{'started_at':time.time(),'log_offset':log.stat().st_size,'meter_offset':meter.stat().st_size,'gpu':gpu(),'operator_epoch':epoch,'settings_sha256':sha256_file(E/'effective-native-settings.json')})
 start=json.loads(startpath.read_text());binding=manifest['jobs'][trial]
 guard();enrollment=intake.enroll(manifest,aid,store=S,trial_ids=[trial],limit=1)
 if enrollment.get('blockers'):raise RuntimeError(json.dumps(enrollment))
 while not path.exists():
  guard()
  provision=Q.provision(manifest,aid,store=S,trial_ids=[trial])
  if provision.get('blockers'):raise RuntimeError(json.dumps(provision))
  with S.tx() as c:exists=c.execute('SELECT 1 FROM afo_local_agent_jobs WHERE job_id=?',(binding['job_id'],)).fetchone()
  if exists:
   with S.tx() as c:job=json.loads(c.execute('SELECT record FROM afo_local_agent_jobs WHERE job_id=?',(binding['job_id'],)).fetchone()[0])
   recorded=qualification_state.record_completed(S,job,destination=results)
   step={'status':'RECORDED' if recorded else 'EXISTING_CONDUCTOR_OWNS_DISPATCH_AND_POLL'}
  else:step={'status':'WAITING_EXISTING_CONDUCTOR_ADMISSION'}
  progress({'status':'RUNNING','trial':trial,'trial_number':index+1,'total_trials':len(manifest['jobs']),'step':step.get('status'),'elapsed_seconds':time.time()-start['started_at']})
  if not path.exists():time.sleep(5)
 row=json.loads(path.read_text());live=X.get(binding['job_id'])
 while not live or live['execution_liveness'] not in ('QUIESCENT','NOT_STARTED') or live['resource_lease']!='RELEASED':
  guard();time.sleep(2);live=X.get(binding['job_id'])
 guard();quiet()
 independent=audit.audit(S,manifest,trial,path,reference_path=reference,revision=manifest['source_revision'])
 with S.tx() as c:requests=[json.loads(x[0]) for x in c.execute('SELECT record FROM afo_request_ledger WHERE job_id=?',(binding['job_id'],))]
 request_ids={x['request_id'] for x in requests};usage=[]
 with meter.open('rb') as f:
  f.seek(start['meter_offset'])
  for line in f:
   item=json.loads(line)
   if (item.get('local') or {}).get('request_id') in request_ids:usage.append(item)
 with log.open('rb') as f:f.seek(start['log_offset']);raw=f.read().decode(errors='replace')
 native_timings=[{'task_id':int(m[0]),'kind':m[1],'milliseconds':float(m[2]),'tokens':int(m[3])} for m in timing.findall(raw)]
 decodes=[x for x in native_timings if x['kind']=='eval'];correlated=bool(requests) and len(decodes)==len(requests)==len(usage) and all(x['state']=='QUIESCENT' for x in requests)
 decode_seconds=sum(x['milliseconds'] for x in decodes)/1000;decode_tokens=sum(x['tokens'] for x in decodes)
 output=sum(x['tokens_output'] for x in usage) if usage and all(type(x.get('tokens_output')) is int for x in usage) else None
 latency=sum(x['latency_ms'] for x in usage)/1000 if usage else None
 record={'schema':'forge-c/non-thinking-speed-trial/1','variant':a.variant,'reasoning':a.variant,'mtp_draft':scope['grants'][a.variant]['mtp_draft'],'trial_id':trial,'source_revision':manifest['source_revision'],'manifest_sha256':digest(manifest),'native_run_id':row.get('native_run_id'),'job_id':binding['job_id'],'requests':requests,'gateway_numeric_usage':usage,'native_numeric_timings':native_timings,'native_timing_correlation':'SERIAL_EXCLUSIVE_ONE_TRIAL_WINDOW' if correlated else 'UNKNOWN','backend_decode_tokens_per_second':decode_tokens/decode_seconds if correlated and decode_seconds>0 else None,'completion_output_tokens':output,'gateway_total_seconds':latency,'end_to_end_output_tokens_per_second':output/latency if output is not None and latency and latency>0 else None,'trial_wall_seconds':time.time()-start['started_at'],'effective_settings_ref':{'path':str(E/'effective-native-settings.json'),'sha256':sha256_file(E/'effective-native-settings.json')},'independent_audit':independent,'observed':row['observed'],'expected':row['expected'],'gpu_before':start['gpu'],'gpu_after':gpu(),'reasoning_content_collected':False,'product_acceptance':False,'formal_controlled_comparison_measurement':'NOT_ESTABLISHED_BY_THIS_SPEED_PILOT'}
 immutable_json(mp,record)
 progress({'status':'TRIAL_RECORDED','trial':trial,'trial_number':index+1,'total_trials':len(manifest['jobs']),'backend_decode_tokens_per_second':record['backend_decode_tokens_per_second'],'observed':row['observed']})
 if not requests and (row.get('job_error') or '').startswith('NATIVE_LAUNCH_NOT_STARTED'):raise RuntimeError('STOP_AFTER_INFRASTRUCTURE_REFUSAL_NO_MODEL_MEASUREMENT')
 print(json.dumps({'variant':a.variant,'reasoning':a.variant,'mtp_draft':scope['grants'][a.variant]['mtp_draft'],'trial':trial,'backend_decode_tokens_per_second':record['backend_decode_tokens_per_second'],'gateway_total_seconds':latency,'output_tokens':output,'observed':row['observed']}),flush=True)
guard();quiet();rows=Q.load_rows(results);report=Q.protocol_report(manifest,rows);immutable_json(E/'protocol-report.json',report)
allmetrics=[json.loads(p.read_text()) for p in sorted(metrics.glob('*.json')) if not p.name.endswith('-start.json')]
speeds=[r['backend_decode_tokens_per_second'] for r in allmetrics if r['backend_decode_tokens_per_second'] is not None]
summary={'status':'COMPLETED_MEASUREMENTS_NOT_PRODUCT_QUALIFICATION','variant':a.variant,'reasoning':a.variant,'mtp_draft':scope['grants'][a.variant]['mtp_draft'],'source_revision':manifest['source_revision'],'expected_trials':len(manifest['jobs']),'observed_trials':len(allmetrics),'median_backend_decode_tokens_per_second':statistics.median(speeds) if speeds else None,'native_decode_measurement_count':len(speeds),'protocol_report_status':report['status'],'mission':MissionLedger(S).snapshot(manifest['mission']['mission_id']),'product_success':'NOT_RUN','author_inspector_qualification':'NOT_RUN','learning_benefit':'NOT_RUN','operational_availability':'UNPROVEN','old_driver_run_resumed':False,'finished_utc':utc_now()}
immutable_json(E/'completion.json',summary);progress(summary);print(json.dumps(summary),flush=True)

