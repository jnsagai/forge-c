"""Owner-requested sequential Q8 MTP microbenchmark. No production deployment."""
import os,sys,json,time,subprocess,urllib.request,hashlib,signal,re
from pathlib import Path
P=Path('/mnt/data/forge-c/production-local-014'); R=P/'repo'
Q=P/'deployment/mtp-q38-20261028'; Q.mkdir(mode=0o700,exist_ok=True)
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#'):
  k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(R/'factory/python'))
from forge_factory.afo.operations import Intent,synchronize
from forge_factory.afo.queue import Store
from forge_factory.afo.execution_lifecycle import Executions
from forge_factory.afo import policy,authz
from forge_factory.common import canonical_json,sha256_bytes,utc_now
import yaml
store=Store(); intent=Intent(); auth={'method':'OS_STATE_DIRECTORY_OWNER','uid':os.getuid()}
report={'schema':'forge-c/mtp-microbenchmark/1','started_at':utc_now(),'owner_instruction':'test option 3',
 'model':'qwen3.8:27b-q8_0','model_manifest_sha256':'8f5fb6b71ea00052cbe8545738c55ce61112c4e571cb60ca4dad00b131766039',
 'purpose':'Sequential raw decode microbenchmark; not xhigh role or product qualification',
 'production_configuration_changed':False,'cases':[],'max_wall_seconds':660,'max_generated_tokens':4096}
def save(): (Q/'result.json').write_text(json.dumps(report,indent=2)+'\n')
def quiet():
 assert not Executions(store).pending(),'ACTIVE_EXECUTION'
 with store.tx() as c:
  assert not any(r[0] for r in c.execute('SELECT holder FROM afo_resource_ownership')),'HELD_RESOURCE'
  assert c.execute("SELECT count(*) FROM afo_request_ledger WHERE state NOT IN ('QUIESCENT','RESERVED')").fetchone()[0]==0,'ACTIVE_REQUEST'
def fence():
 x=intent.read()
 assert x['mode']=='PAUSED' and x['epoch']==paused['epoch'],'NEW_OPERATOR_INTENT'
quiet(); old=intent.read(); assert old['mode']=='RUNNING' and old['epoch']==16,old
paused=synchronize(store,'pause',str(os.getuid()),'Owner requested bounded sequential Qwen3.8 Q8 MTP comparison',authentication=auth,expected_epoch=16)
report['operator_pause_epoch']=paused['epoch'];save()
proc=None
def interrupted(signum,frame): raise InterruptedError('BOUND_OR_SIGNAL')
signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGALRM,interrupted);signal.alarm(660)
lib='/mnt/data/forge-c/ollama-0.34.0/lib/ollama'
blob='/mnt/data/forge-c/ollama-models/blobs/sha256-2bb22714289826d7b9e0ba376c3ce47d08bce39abe598745857c44d88c09bdbf'
env={**os.environ,'LD_LIBRARY_PATH':lib+':'+lib+'/cuda_v13','GGML_BACKEND_PATH':lib+'/cuda_v13/libggml-cuda.so'}
for k in list(env):
 if k.startswith(('FORGE_','FABRO_','OLLAMA_')): env.pop(k)
prompts=[
 ('crc8','Write a C11 function named crc8 taking const unsigned char *data and unsigned long n, returning unsigned char. Use initial value 0, polynomial 0x07, non-reflected MSB-first, no final xor. Output only the complete C function, no markdown or explanation.'),
 ('popcount','Write a C11 function named popcount32 taking unsigned int x and returning unsigned int. Count all 32 bits by shifting x. Output only the complete C function, no markdown or explanation.')]
base=['--model',blob,'--host','127.0.0.1','--port','32577','--no-webui','--offline','-c','65536','-np','1','-ngl','all','--flash-attn','on','--cache-type-k','f16','--cache-type-v','f16','-b','2048','-ub','2048','--no-warmup']
def post(payload):
 req=urllib.request.Request('http://127.0.0.1:32577/completion',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=100) as r:return json.load(r)
def stop():
 global proc
 if proc is not None and proc.poll() is None:
  proc.terminate()
  try:proc.wait(timeout=8)
  except subprocess.TimeoutExpired: proc.kill();proc.wait(timeout=5)
 proc=None
try:
 for mode in ['baseline','mtp']:
  fence();quiet()
  gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader'],text=True).strip()
  report.setdefault('gpu_before',{})[mode]=gpu
  args=[lib+'/llama-server',*base]+(['--spec-type','draft-mtp','--spec-draft-n-max','3'] if mode=='mtp' else ['--spec-type','none'])
  report.setdefault('commands',{})[mode]=args
  logfile=open(Q/(mode+'-server.log'),'w')
  proc=subprocess.Popen(args,env=env,stdout=logfile,stderr=subprocess.STDOUT)
  start=time.monotonic()
  while time.monotonic()-start<100:
   fence()
   if proc.poll() is not None:raise RuntimeError(mode+'_SERVER_EXIT_'+str(proc.returncode))
   try:
    with urllib.request.urlopen('http://127.0.0.1:32577/health',timeout=1) as r:
     if r.status==200:break
   except Exception:time.sleep(.5)
  else:raise RuntimeError(mode+'_START_TIMEOUT')
  report.setdefault('load_wall_seconds',{})[mode]=time.monotonic()-start
  for name,instruction in prompts:
   for repeat in range(2):
    fence();quiet()
    prompt='<|im_start|>user\n'+instruction+'<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
    payload={'prompt':prompt,'n_predict':512,'temperature':0,'seed':42,'cache_prompt':False,'stream':False,'stop':['<|im_end|>']}
    start=time.monotonic(); out=post(payload);wall=time.monotonic()-start
    content=out.get('content','');(Q/(mode+'-'+name+'-'+str(repeat)+'.txt')).write_text(content)
    report['cases'].append({'mode':mode,'case':name,'repeat':repeat,'wall_seconds':wall,'timings':out.get('timings'),
      'tokens_predicted':out.get('tokens_predicted'),'stop':{k:out.get(k) for k in ['stopped_eos','stopped_limit','stopped_word','stop_type']},
      'content_sha256':hashlib.sha256(content.encode()).hexdigest(),'content_length':len(content)})
    save()
  stop();logfile.close()
 for name,_ in prompts:
  for repeat in range(2):
   a=(Q/('baseline-'+name+'-'+str(repeat)+'.txt')).read_text()
   b=(Q/('mtp-'+name+'-'+str(repeat)+'.txt')).read_text()
   report.setdefault('paired_output_equal',{})[name+'-'+str(repeat)]=a==b
 for mode in ['baseline','mtp']:
  for name,_ in prompts:
   for repeat in range(2):
    content=(Q/(mode+'-'+name+'-'+str(repeat)+'.txt')).read_text()
    content=re.sub(r'^\s*\x60\x60\x60(?:c|C)?\s*\n','',content);content=re.sub(r'\n\x60\x60\x60\s*$','',content)
    test='\nint main(void){const unsigned char d[]="123456789";return crc8(d,9)!=0xf4 || crc8(d,0)!=0;}\n' if name=='crc8' else '\nint main(void){return popcount32(0)!=0 || popcount32(0xffffffffu)!=32 || popcount32(0x80000001u)!=2;}\n'
    source=Q/(mode+'-'+name+'-'+str(repeat)+'.c');source.write_text(content+test);exe=source.with_suffix('.test')
    compile_result=subprocess.run(['/mnt/data/forge-c/toolchains/LLVM-19.1.7-Linux-X64/bin/clang','-std=c11','-Wall','-Wextra','-Werror',str(source),'-o',str(exe)],capture_output=True,text=True,timeout=15)
    check={'compiled':compile_result.returncode==0,'compiler_error':compile_result.stderr[:1000]}
    if compile_result.returncode==0:check['test_exit']=subprocess.run([str(exe)],timeout=5).returncode
    report.setdefault('independent_output_checks',{})[mode+'-'+name+'-'+str(repeat)]=check
 report['status']='COMPLETED'
except BaseException as e:
 report['status']='FAILED';report['error']=type(e).__name__+':'+str(e)
finally:
 signal.alarm(0);stop()
 try:
  with intent.lock():
   fence()
   original=(P/'deployment/aspice-window-20261028/original-production-policy.yaml').read_bytes()
   saved=yaml.safe_load(original); original_sha=sha256_bytes(canonical_json(saved))
   assert original_sha=='83e78088c66df61e6513c466b9221e85f54ba34adbcddf0dcae48b69d91a96ad'
   current=policy.load(log=False)
   scope=json.loads((P/'deployment/aspice-window-20261028/scope.json').read_text())
   assert current.sha256 in (scope['policy_sha256'],original_sha),'POLICY_CHANGED'
   assert authz.find('PILOT',original_sha,ref=saved['authorization_ref'],action='read_status').allow
   path=Path(os.environ['FORGE_AFO_POLICY']);tmp=path.with_name(path.name+'.mtp-restore')
   fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
   with os.fdopen(fd,'wb') as f:f.write(original);f.flush();os.fsync(f.fileno())
   os.replace(tmp,path);fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
   report['policy_restoration']={'sha256':policy.load(log=False).sha256,'grant_renewed':False,'mission_allowances_modified':False}
  resumed=synchronize(store,'resume',str(os.getuid()),'MTP bounded comparison finished; original signed production policy restored',authentication=auth,expected_epoch=paused['epoch'])
  report['operator_resume_epoch']=resumed['epoch']
 except Exception as e:report['restoration_error']=type(e).__name__+':'+str(e)
 report['finished_at']=utc_now();save()
print(json.dumps(report))
