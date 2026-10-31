"""Isolated local SQLite durability experiment; no native/model/runtime changes."""
from pathlib import Path
import hashlib,json,sqlite3,time,os
from forge_factory.afo.queue import Store
A=Path(__file__).parent;root=A/'wal-connection-local-probe';root.mkdir(mode=0o700)
def io():return {k:int(v.strip()) for k,v in (line.split(':',1) for line in Path('/proc/self/io').read_text().splitlines())}
rows=[]
for keep in (False,True):
 p=root/('keeper.sqlite3' if keep else 'baseline.sqlite3');assert not p.exists();s=Store(p)
 with s.tx() as c:c.execute('CREATE TABLE probe (n INTEGER PRIMARY KEY, receipt TEXT NOT NULL)')
 conn=s.connect() if keep else None
 start=time.monotonic();before=io()
 for n in range(32):
  with s.tx() as c:c.execute('INSERT INTO probe VALUES (?,?)',(n,hashlib.sha256(str(n).encode()).hexdigest()))
 after=io();elapsed=time.monotonic()-start
 wal=Path(str(p)+'-wal');walbytes=wal.stat().st_size if wal.exists() else 0
 if conn:conn.close()
 c=sqlite3.connect(p);ok=c.execute('PRAGMA integrity_check').fetchone()[0];data=c.execute('SELECT n,receipt FROM probe ORDER BY n').fetchall();c.close()
 assert ok=='ok' and len(data)==32 and all(v==hashlib.sha256(str(n).encode()).hexdigest() for n,v in data)
 rows.append({'keep_idle_connection':keep,'transactions':32,'seconds':elapsed,'io_deltas':{k:after[k]-v for k,v in before.items()},'wal_bytes_before_keeper_close':walbytes,'integrity':ok,'reopened_rows':len(data),'synchronous':'FULL_IN_EXISTING_STORE_CONNECT'})
print(json.dumps({'scope':'LOCAL_ISOLATED_STORAGE_EXPERIMENT_NOT_NATIVE_OR_MODEL_QUALIFICATION','rows':rows,'model_requests':0,'live_database_mutated':False,'speedup':rows[0]['seconds']/rows[1]['seconds']},indent=2))
