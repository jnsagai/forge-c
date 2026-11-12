"""Follow completed visible Qwen packet answers and reported token usage; zero inference, no reasoning capture."""
from pathlib import Path
import argparse, hashlib, json, time

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--once',action='store_true')
ap.add_argument('--workspace',type=Path,default=Path('/mnt/data/forge-c/production-local-014/state/workorders/WO-AFO-cf20126621ac2673-a1/workspace'))
args=ap.parse_args();seen={}
print('Qwen visible answers and provider-reported token usage. Responses appear when each request completes.',flush=True)
print('Hidden reasoning is excluded. Ctrl+C closes this viewer and leaves the factory running.',flush=True)
try:
 while True:
  for path in sorted((args.workspace/'.forge-run/lrtx').glob('*/packets/*.json')):
   try:
    raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if seen.get(str(path))==sha:continue
    data=json.loads(raw)
   except (OSError,ValueError):continue
   seen[str(path)]=sha
   if data.get('doc') is None and not data.get('attempts'):continue
   print('\n'+str(path.parent.parent.name)+' | '+str(data.get('task'))+' | '+str(data.get('status')),flush=True)
   for attempt in data.get('attempts',[]):
    usage=attempt.get('usage') or {}
    print('  provider-reported input_tokens='+str(usage.get('prompt_tokens','UNKNOWN'))+
     ' output_tokens='+str(usage.get('completion_tokens','UNKNOWN'))+
     ' total_tokens='+str(usage.get('total_tokens','UNKNOWN'))+
     ' wall_s='+str(round(attempt.get('wall_ms',0)/1000,1)),flush=True)
   if data.get('doc') is not None:print(json.dumps(data['doc'],ensure_ascii=False,indent=2),flush=True)
   if data.get('errors'):print('Validation findings: '+json.dumps(data['errors'],ensure_ascii=False),flush=True)
  if args.once:break
  time.sleep(2)
except KeyboardInterrupt:
 pass
