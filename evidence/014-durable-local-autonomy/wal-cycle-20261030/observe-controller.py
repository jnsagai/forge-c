"""Bounded procfs sample: no signals, model calls, source/control/state mutations."""
import collections,json,os,subprocess,time
from pathlib import Path
UNIT='forge-conductor-local-omniverse2.service'
pid=int(subprocess.check_output(['systemctl','--user','show',UNIT,'-p','MainPID','--value'],text=True).strip())
if not pid:print(json.dumps({'status':'NO_CURRENT_SERVICE_PID','unit':UNIT,'inference_requests':0}));raise SystemExit(3)
p=Path('/proc')/str(pid)
def stat():
 fields=(p/'stat').read_text().rsplit(') ',1)[1].split()
 return {'state':fields[0],'cpu_ticks':int(fields[11])+int(fields[12]),'start_ticks':int(fields[19])}
def io():return {k:int(v.strip()) for k,v in (line.split(':',1) for line in (p/'io').read_text().splitlines())}
first=stat();before=io();started=time.monotonic();counts=collections.Counter();states=collections.Counter();last=first;status='SAMPLED_SAME_LIVE_PROCESS'
for _ in range(200):
 try:
  last=stat()
  if last['start_ticks']!=first['start_ticks']:status='PROCESS_IDENTITY_CHANGED';break
  counts[(p/'wchan').read_text().strip()]+=1;states[last['state']]+=1
 except FileNotFoundError:status='PROCESS_EXITED_DURING_OBSERVATION';break
 time.sleep(.2)
wall=time.monotonic()-started
try:after=io()
except FileNotFoundError:after={}
cpu=(last['cpu_ticks']-first['cpu_ticks'])/os.sysconf('SC_CLK_TCK')
print(json.dumps({'scope':'READ_ONLY_SUPERVISOR_PROCFS_SAMPLE_NOT_ENGINEERING_OR_MODEL_SPEED_QUALIFICATION','status':status,'unit':UNIT,'pid':pid,'start_ticks':first['start_ticks'],'wall_seconds':wall,'cpu_seconds':cpu,'one_core_cpu_percent':100*cpu/wall,'wait_channel_samples':dict(counts),'state_samples':dict(states),'io_counter_deltas':{k:after[k]-v for k,v in before.items() if k in after},'inference_requests':0,'signals_sent':0,'configuration_changes':False}))
