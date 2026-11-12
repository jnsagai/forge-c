from pathlib import Path
import json,sqlite3,time,os
P=Path('/mnt/data/forge-c/production-local-014')
s=json.loads((P/'deployment/rcc-context-completion-20261030-v1/scope.json').read_text())
assert time.time()<s['enrolment_latest_epoch']
while time.time()<s['enrolment_latest_epoch']:
 c=sqlite3.connect('file:'+str(P/'state/conductor/conductor.sqlite3')+'?mode=ro',uri=True)
 row=c.execute("SELECT expires_epoch FROM afo_leases WHERE scope='scheduler'").fetchone();c.close()
 if not row or time.time()>row[0]+0.25:break
 time.sleep(min(10,max(0.5,row[0]+0.5-time.time())))
assert time.time()<s['enrolment_latest_epoch']
py=str(P/'venv/bin/python')
os.execv(py,[py,str(P/'deployment/run-rcc-context-completion.py')])
