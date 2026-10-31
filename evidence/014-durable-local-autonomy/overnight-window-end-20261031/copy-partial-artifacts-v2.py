"""Read/copy existing trial artifacts only; no inference or release authority."""
from pathlib import Path
from datetime import datetime,UTC
import argparse,json,sqlite3,hashlib,zipfile,os,tempfile,stat
E=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1')
ap=argparse.ArgumentParser();ap.add_argument('--order-id',required=True);ap.add_argument('--capture',action='store_true');a=ap.parse_args()
cohort=E/'control/repeatability-20261031-v4b/repeatability-prepared-20261031-v4b/cohort.json'
raw=cohort.read_bytes();assert hashlib.sha256(raw).hexdigest()=='a14bfe74a0365a47360a630e09cdaec0338b10385ecb8be7a1b4d3389d18e759'
assert a.order_id in {x['order_id'] for x in json.loads(raw)['items']}
with sqlite3.connect('file:'+str(E/'state/conductor/conductor.sqlite3')+'?mode=ro',uri=True) as db:
 db.row_factory=sqlite3.Row
 order=dict(db.execute('SELECT order_id,state,terminal_reason FROM afo_work_orders WHERE order_id=?',(a.order_id,)).fetchone())
 attempts=list(db.execute('SELECT attempt_id,record FROM afo_attempts WHERE order_id=? ORDER BY seq',(a.order_id,)))
if not attempts:print(json.dumps({'status':'NO_ATTEMPT_NO_WORKSPACE','order':order,'model_calls':0}));raise SystemExit()
att=attempts[-1];rec=json.loads(att['record']);name=rec['workspace_ref'].removeprefix('workorder:')
ws=E/'state/workorders'/name/'workspace'
assert ws.resolve().is_relative_to(E/'state/workorders') and not ws.is_symlink()
tops=['software','workproducts','evidence','.forge-run/delivery-first','.forge-run/test-snapshots','.forge-run/gates']
files=set()
for top in tops:
 base=ws/top
 if base.is_dir():files.update(p for p in base.rglob('*') if p.is_file() and not p.is_symlink())
for rel in ('.forge-run/manifest.json','.forge-run/model-profile.json','.forge-run/fabro_run_id','.forge-run/package.json','.forge-run/delivery-first/initial.json'):
 p=ws/rel
 if p.is_file() and not p.is_symlink():files.add(p)
if not a.capture:print(json.dumps({'status':'PREPARED_NOT_CAPTURED','order':order,'native_id':rec.get('fabro_run_id'),'file_count':len(files),'model_calls':0}));raise SystemExit()
base=E/'control/qualification-observations/partial-artifacts';base.mkdir(exist_ok=True)
dest=Path(tempfile.mkdtemp(prefix=a.order_id+'-',dir=base));os.chmod(dest,0o700)
archive=dest/'PARTIAL-artifacts.zip';start=datetime.now(UTC).isoformat();entries=[]
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=3) as z:
 for p in sorted(files):
  rel=p.relative_to(ws)
  assert p.resolve().is_relative_to(ws.resolve()) and all(not part.is_symlink() for part in [p,*list(p.parents)[:len(rel.parts)-1]])
  fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
  with os.fdopen(fd,'rb') as stream:
   before=os.fstat(stream.fileno());assert stat.S_ISREG(before.st_mode)
   h=hashlib.sha256();n=0
   with z.open('artifacts/'+rel.as_posix(),'w') as out:
    while chunk:=stream.read(1024*1024):h.update(chunk);n+=len(chunk);out.write(chunk)
   after=os.fstat(stream.fileno())
  entries.append({'path':rel.as_posix(),'sha256':h.hexdigest(),'bytes_captured':n,'stable_during_read':(before.st_ino,before.st_dev,before.st_size,before.st_mtime_ns)==(after.st_ino,after.st_dev,after.st_size,after.st_mtime_ns)})
 manifest={'schema':'forge-c/private-partial-artifact-copy/1','status':'PARTIAL_UNATOMIC_ARTIFACT_COPY_NOT_RELEASE_OR_QUALIFICATION','captured_start':start,'captured_end':datetime.now(UTC).isoformat(),'order_at_start':order,'attempt_id':att['attempt_id'],'native_id':rec.get('fabro_run_id'),'files':entries,'model_calls':0,'candidate_execution':False,'source_workspace_written':False,'limits':'Captured byte hashes only; active writes can race. No finality, consistency, authorship, release or missing checks inferred.'}
 z.writestr('PARTIAL-MANIFEST.json',json.dumps(manifest,indent=2))
os.chmod(archive,0o600)
h=hashlib.sha256()
with archive.open('rb') as stream:
 while chunk:=stream.read(1024*1024):h.update(chunk)
receipt={**{k:v for k,v in manifest.items() if k!='files'},'archive':str(archive),'archive_sha256':h.hexdigest(),'file_count':len(entries),'unstable_during_read':[x['path'] for x in entries if not x['stable_during_read']]}
(dest/'transfer-source.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
