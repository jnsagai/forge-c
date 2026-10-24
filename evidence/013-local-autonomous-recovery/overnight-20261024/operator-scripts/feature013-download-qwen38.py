#!/usr/bin/python3
"""Pull-only official Ollama artifact, one rate-limited stream; never starts a model server or inference."""
import os,json,time,hashlib,re,shutil,subprocess,urllib.request,fcntl
from pathlib import Path
from datetime import datetime,timezone
root=Path('/mnt/data/forge-c/downloads/qwen3.8-27b-q8_0');root.mkdir(parents=True,exist_ok=True)
lock=(root/'download.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
store=Path('/mnt/data/forge-c/lrtx-v2/ollama-models');blobs=store/'blobs';blobs.mkdir(parents=True,exist_ok=True)
url='https://registry.ollama.ai/v2/library/qwen3.8/manifests/27b-q8_0'
def status(state,**kw):
 d=dict(state=state,model='qwen3.8:27b-q8_0',source_url='https://ollama.com/library/qwen3.8:27b-q8_0',updated_utc=datetime.now(timezone.utc).isoformat(),inference_started=False,rate_limit_bytes_per_second=8*1024*1024,**kw)
 p=root/'status.tmp';p.write_text(json.dumps(d,indent=2)+'\n');os.replace(p,root/'status.json')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
try:
 req=urllib.request.Request(url,headers={'Accept':'application/vnd.docker.distribution.manifest.v2+json'})
 with urllib.request.urlopen(req,timeout=30) as r:raw=r.read(65537)
 assert len(raw)<=65536
 manifest=json.loads(raw);md=hashlib.sha256(raw).hexdigest()
 assert md.startswith('8f5fb6b71ea0'),'Registry tag changed from verified official artifact; review before resuming'
 (root/'registry-manifest.json').write_bytes(raw)
 layers=[manifest['config']]+manifest['layers'];total=sum(x['size'] for x in layers)
 assert shutil.disk_usage(root).free>total+10*1024**3
 assert sum(x.get('mediaType')=='application/vnd.ollama.image.model' for x in layers)==1
 verified=[]
 for layer in layers:
  dig=layer['digest'];size=layer['size'];assert re.fullmatch('sha256:[0-9a-f]{64}',dig) and 0<size<35*1024**3
  dest=blobs/dig.replace(':','-');part=root/(dig.replace(':','-')+'.partial')
  status('DOWNLOADING',manifest_sha256=md,current_blob=dig,current_blob_size=size,total_bytes=total,verified_blobs=verified)
  if not (dest.exists() and dest.stat().st_size==size and sha(dest)==dig.split(':')[1]):
   if dest.exists():raise RuntimeError('Existing content-addressed blob failed integrity validation')
   log=(root/'transfer.log').open('a')
   result=subprocess.run(['/usr/bin/ionice','-c','3','/usr/bin/curl','--fail','--location','--silent','--show-error','--continue-at','-','--limit-rate','8M','--retry','8','--retry-all-errors','--retry-delay','20','--connect-timeout','30','--speed-limit','1024','--speed-time','120','--output',str(part),'https://registry.ollama.ai/v2/library/qwen3.8/blobs/'+dig],stdout=log,stderr=log,timeout=12*3600)
   log.close();assert result.returncode==0,'Artifact transfer failed; partial file retained for resume'
   status('VERIFYING',manifest_sha256=md,current_blob=dig,total_bytes=total,verified_blobs=verified)
   assert part.stat().st_size==size and sha(part)==dig.split(':')[1],'Downloaded blob integrity check failed'
   os.replace(part,dest);dest.chmod(0o644)
  verified.append(dict(digest=dig,size=size,sha256_verified=True))
 config=json.loads((blobs/manifest['config']['digest'].replace(':','-')).read_text())
 quant=config.get('model_format') or config.get('file_type')
 mp=store/'manifests/registry.ollama.ai/library/qwen3.8/27b-q8_0';mp.parent.mkdir(parents=True,exist_ok=True)
 if mp.exists():assert mp.read_bytes()==raw,'Refuse overwriting a different installed tag'
 else:
  temp=mp.with_suffix('.download-tmp');temp.write_bytes(raw);os.replace(temp,mp);mp.chmod(0o644)
 status('COMPLETE',manifest_sha256=md,total_bytes=total,verified_blobs=verified,manifest_path=str(mp),note='Downloaded and hash-verified only; inspector test not run; current mission model and allowlist unchanged')
except Exception as e:
 status('FAILED',error_type=type(e).__name__,detail=str(e)[:200]);raise
