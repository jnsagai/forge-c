"""Read-only local collector of terminal AFO outcomes; never submits or resumes work."""
from pathlib import Path
from datetime import datetime,UTC
import json,hashlib,subprocess,shlex,time,sys,os,stat,zipfile
B=Path("/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c");A=Path("/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/operations/feature014/incremental-m1-followup-20261029");W=Path("/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/operations/feature014/recovery-after-overnight-20261028")
DEST=B/'inspection/feature014/2026-10-30-qwen/overnight-afo-delivery'
DEST.mkdir(parents=True,exist_ok=True)
os.environ.update(FORGE_REPO_ROOT=str(W),FORGE_DATA_ROOT=str(B),PYTHONDONTWRITEBYTECODE='1')
sys.path.insert(0,str(W/'factory/python'))
from forge_factory.release.finalize import verify_archive
EXPORTER="from pathlib import Path\nimport json,sqlite3,os,sys,hashlib\nE=Path('/mnt/data/forge-c/delivery-first-afo-014-20261030-v1')\nos.environ.update(json.loads((E/'control/runtime-env-v5.json').read_text()));sys.path.insert(0,str(E/'source/factory/python'))\nfrom forge_factory.fabro.client import FabroClient,load_token,run_status\nfrom forge_factory.common import utc_now\ndb=sqlite3.connect('file:'+str(E/'state/conductor/conductor.sqlite3')+'?mode=ro',uri=True);db.row_factory=sqlite3.Row\nrows=[]\nwith FabroClient(base_url='http://127.0.0.1:32404',token=load_token(str(E/'fabro/storage')),timeout=10) as client:\n for order in db.execute('SELECT order_id,state,terminal_reason FROM afo_work_orders ORDER BY created_epoch'):\n  attempts=db.execute('SELECT * FROM afo_attempts WHERE order_id=? ORDER BY seq',(order['order_id'],)).fetchall()\n  for att in attempts:\n   record=json.loads(att['record']);rid=record.get('fabro_run_id')\n   if not rid:continue\n   raw=record.get('workspace_ref','');name=raw.removeprefix('workorder:')\n   ws=E/'state/workorders'/name/'workspace'\n   if not ws.resolve().is_relative_to(E/'state/workorders'):raise ValueError('WORKSPACE_OUTSIDE_RUNTIME')\n   status=run_status(client.get_run(rid))\n   row={'order_id':order['order_id'],'order_state':order['state'],'terminal_reason':order['terminal_reason'],\n    'attempt_id':att['attempt_id'],'native_id':rid,'native_status':status,'work_order':name,'workspace':str(ws)}\n   package=ws/'.forge-run/package.json'\n   if package.is_file() and status in ('SUCCEEDED','FAILED','CANCELLED','CANCELED','DEAD'):\n    doc=json.loads(package.read_text());archive=Path(doc['archive'])\n    assert archive.resolve().is_relative_to(E/'archives') and archive.is_file() and not archive.is_symlink()\n    sha=hashlib.sha256(archive.read_bytes()).hexdigest()\n    if doc.get('archive_sha256') and doc['archive_sha256']!=sha:raise ValueError('ARCHIVE_RECORD_HASH_CHANGED')\n    row.update(archive=str(archive),archive_sha256=sha,archive_bytes=archive.stat().st_size,\n     package_status=doc['package_status'],gap_count=doc.get('gap_count'),gaps=doc.get('gaps',[]))\n   rows.append(row)\nguard=E/'control/window-guard-process.json';g=json.loads(guard.read_text()) if guard.is_file() else {}\nprint(json.dumps({'at':utc_now(),'rows':rows,'deadline_utc':'2026-10-31T07:57:59Z','read_only':True,'model_calls':0,\n 'window_guard_pid':g.get('pid'),'window_guard_alive':bool(g and __import__('forge_factory.lrtx.stack',fromlist=['process_identity']).process_identity(g['pid'])==g.get('identity'))}))\n"
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no',
 '-o','ControlMaster=auto','-o','ControlPersist=300','-o','ControlPath='+str(B/'fc014-ssh.sock')]
SCP=['scp','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no',
 '-o','ControlPath='+str(B/'fc014-ssh.sock')]
REMOTE='omniverse2@100.118.28.92'
CMD=shlex.join(['/mnt/data/forge-c/delivery-first-afo-014-20261030-v1/venv/bin/python','-c',EXPORTER])
END=datetime.fromisoformat('2026-10-31T08:12:59+00:00').timestamp()
(A/'overnight-afo-collector-process.json').write_text(json.dumps({'pid':os.getpid(),'destination':str(DEST),
 'observation_end_utc':'2026-10-31T08:12:59Z','inference_authority':False,'new_jobs_submitted':0})+'\n')
while time.time()<END:
 try:
  run=subprocess.run([*SSH,REMOTE,CMD],capture_output=True,text=True,timeout=45)
  if run.returncode:raise RuntimeError('REMOTE_OBSERVATION_FAILED:'+run.stderr[-300:])
  doc=json.loads(run.stdout);copies=[]
  for row in doc['rows']:
   if not row.get('archive'):continue
   name='native-'+row['native_id'];assert all(c.isalnum() or c in '-_' for c in name)
   root=DEST/name;root.mkdir(exist_ok=True)
   receipt=root/'transfer-verification.json'
   if receipt.exists():
    prior=json.loads(receipt.read_text())
    if prior['archive_sha256']!=row['archive_sha256']:raise RuntimeError('TERMINAL_ARCHIVE_CHANGED_PRESERVE_PRIOR:'+row['native_id'])
    continue
   archive=root/'review.zip';part=root/'review.zip.partial'
   subprocess.run([*SCP,REMOTE+':'+row['archive'],str(part)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=180)
   sha=hashlib.sha256(part.read_bytes()).hexdigest();assert sha==row['archive_sha256'],'TRANSFER_SHA_MISMATCH'
   part.replace(archive);verified=verify_archive(archive);assert verified['integrity']=='PASS',verified
   extract=root/'review-package';extract.mkdir(exist_ok=True)
   with zipfile.ZipFile(archive) as z:
    assert sum(i.file_size for i in z.infolist())<1024**3,'ARCHIVE_EXTRACTION_TOO_LARGE'
    for i in z.infolist():
     target=(extract/i.filename).resolve()
     assert target.is_relative_to(extract.resolve()) and not stat.S_ISLNK(i.external_attr>>16),'UNSAFE_ARCHIVE_MEMBER'
    z.extractall(extract)
   (root/'outcome.json').write_text(json.dumps(row,indent=2)+'\n')
   receipt.write_text(json.dumps({'captured_utc':datetime.now(UTC).isoformat(),'archive_sha256':sha,
    'integrity':verified['integrity'],'new_model_calls':0,'new_jobs_submitted':0},indent=2)+'\n')
   (root/'START-HERE.md').write_text('# Copied AFO terminal outcome\n\nNative '+row['native_id']+'; order '+row['order_id']+
    '. Package '+row['package_status']+', gaps '+str(row['gap_count'])+'. See review-package/REVIEW_SUMMARY.md and outcome.json. '
    'Archive SHA256 '+sha+'. Native completion is not functional or release acceptance.\n')
   copies.append(row['native_id'])
  index={'captured_utc':datetime.now(UTC).isoformat(),'remote':doc,'local_terminal_copies':[
   str(p.parent) for p in DEST.glob('native-*/transfer-verification.json')],'new_jobs_submitted':0,'model_requests':0}
  temporary=DEST/'index.json.partial';temporary.write_text(json.dumps(index,indent=2)+'\n');temporary.replace(DEST/'index.json')
  print(json.dumps({'at':datetime.now(UTC).isoformat(),'copied':copies,'native_statuses':[
   {'id':r['native_id'],'status':r['native_status']} for r in doc['rows']]}),flush=True)
 except Exception as exc:
  print(json.dumps({'at':datetime.now(UTC).isoformat(),'read_only_observation_error':str(exc)[-500:]}),flush=True)
 time.sleep(60)

