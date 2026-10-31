from pathlib import Path
import json,subprocess
P=Path('/mnt/data/forge-c/production-local-014');out=P/'progress-afo-focused-20261029-v6';branch='overnight/2026-10-29-local-qwen-afo'
head=subprocess.check_output(['git','-C',str(out),'rev-parse','HEAD'],text=True).strip()
r=subprocess.run(['git','-C',str(out),'ls-remote','--heads','origin',branch],capture_output=True,text=True,timeout=30)
remote=r.stdout.split()[0] if r.returncode==0 and r.stdout.strip() else None
status=subprocess.check_output(['systemctl','--user','show','forge-qwen-mission-recorder.service','-p','ActiveState','-p','ExecMainStatus'],text=True).strip().splitlines()
print(json.dumps({'status':status,'local_head':head,'remote_head':remote,'latest_commit_published':head==remote,'progress_branch':branch,'progress':json.loads((out/'progress.json').read_text()),'raw_config_exported':False},indent=2))
