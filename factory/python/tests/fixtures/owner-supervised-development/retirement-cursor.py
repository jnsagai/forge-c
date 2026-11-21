"""Only typed factual-capture telemetry may drift; never write controls or infer authority."""
import datetime,hashlib,json,re,sqlite3
from pathlib import Path
KEY='line_learning_capture_cursor';ACTOR='line-learning-capture'
HOLD='owner-development-source-fix-hold'
UTC=re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)\Z')
def need(ok,code):
 if not ok:raise RuntimeError(code)
def utc(value):
 need(type(value)is str and len(value)<=40 and UTC.fullmatch(value),'CURSOR_UTC_INVALID')
 try:d=datetime.datetime.fromisoformat(value.replace('Z','+00:00'))
 except ValueError as e:raise RuntimeError('CURSOR_UTC_INVALID') from e
 need(d.utcoffset()==datetime.timedelta(0),'CURSOR_UTC_INVALID')
def observe_connection(c):
 allowed=c.execute('SELECT key,actor,value FROM afo_control ORDER BY key LIMIT 4').fetchall()
 need(len(allowed)<=3 and all(tuple(x[:2]) in ((KEY,ACTOR),('controller_escalation_event_cursor','controller-escalation'),('paused',HOLD)) for x in allowed),'UNKNOWN_CONTROL_ROWS')
 need(all(x[0]!='paused' or x[2]=='0' for x in allowed),'ADMISSION_HOLD_STILL_SET')
 rows=c.execute('SELECT key,value,updated_utc,actor FROM afo_control WHERE key=?',(KEY,)).fetchall()
 out=[]
 for row in rows:
  key,value,updated,actor=row
  need(type(key)is str and key==KEY and type(actor)is str and actor==ACTOR,'UNKNOWN_CONTROL_OR_ACTOR')
  need(type(value)is str and 1<=len(value)<=512,'CURSOR_VALUE_INVALID');utc(updated)
  attempts=c.execute("SELECT a.attempt_id,a.order_id,a.state,a.created_utc,o.tenant_scope FROM afo_attempts a JOIN afo_work_orders o ON o.order_id=a.order_id WHERE a.created_utc||a.attempt_id=? LIMIT 2",(value,)).fetchall()
  need(len(attempts)==1,'CURSOR_TERMINAL_ATTEMPT_REQUIRED');aid,oid,state,created,scope=attempts[0]
  need(all(type(x)is str and 1<=len(x)<=256 for x in (aid,oid,state,scope)) and state in ('SUCCEEDED','FAILED','CANCELLED','UNKNOWN') and scope=='line-local','CURSOR_TERMINAL_LOCAL_ATTEMPT_REQUIRED');utc(created)
  need(value==created+aid,'CURSOR_VALUE_REBOUND')
  out.append(dict(key=key,value=value,updated_utc=updated,actor=actor,attempt_id=aid,order_id=oid,attempt_state=state,tenant_scope=scope))
 return dict(schema='forge-c/typed-line-learning-cursor-observation/1',rows=out,row_count=len(out),observation_sha256=hashlib.sha256(json.dumps(out,sort_keys=True,separators=(',',':')).encode()).hexdigest(),authority=False,writes=0)
def observe(path):
 p=Path(path);need(not p.is_symlink(),'CURSOR_DATABASE_REBOUND');before=p.stat()
 with sqlite3.connect(p.absolute().as_uri()+'?mode=ro',uri=True,timeout=2) as c:
  c.execute('PRAGMA query_only=ON');c.execute('BEGIN');result=observe_connection(c)
 after=p.stat();need((before.st_dev,before.st_ino)==(after.st_dev,after.st_ino),'CURSOR_DATABASE_REBOUND');return result
