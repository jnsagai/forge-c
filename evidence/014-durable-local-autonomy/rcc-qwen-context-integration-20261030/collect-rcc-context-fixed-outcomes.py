"""Private local outcome copies. Read-only SSH observations; no job submission or model requests."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,time,zipfile,stat
from datetime import datetime,timezone
from forge_factory.release.finalize import verify_archive

ROOT=Path("/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/inspection/feature014/2026-10-30-qwen/full-pipeline-context-fixed")
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=10','-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no',
 '-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3','-o','ControlMaster=auto','-o','ControlPersist=300',
 '-o',"ControlPath=/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c/fc014-ssh.sock",'omniverse2@100.118.28.92']
REMOTE=r"""
import sys,json
from pathlib import Path
P=Path('/mnt/data/forge-c/production-local-014')
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.afo.queue import ReadSnapshot
rows=[]
with ReadSnapshot(P/'state/conductor/conductor.sqlite3',timeout_s=20) as s:
 with s.tx() as c:
  for raw, in c.execute('SELECT record FROM afo_product_jobs'):
   j=json.loads(raw)
   if j.get('mission_id')!='F014-NIGHT-20261027-RCC' or j.get('order_id') not in ('afo-6bde501adad6a2bf','afo-5bd7ba96b10624a5'):continue
   rawex=c.execute('SELECT record FROM afo_execution_liveness WHERE job_id=?',(j['job_id'],)).fetchone()
   e=json.loads(rawex[0]) if rawex else {}
   row={k:j.get(k) for k in ('job_id','order_id','attempt_id','mission_id','model','profile','factory_revision')}
   row.update({k:e.get(k) for k in ('execution_liveness','resource_lease','task_outcome','native_run_ids')})
   ws=Path(j['workspace'])
   if not ws.resolve().is_relative_to(P):raise ValueError('WORKSPACE_OUTSIDE_FACTORY')
   pp=ws/'.forge-run/package.json'
   if pp.is_file():
    package=json.loads(pp.read_text())
    row['package']={k:package.get(k) for k in ('package_status','archive','archive_sha256','gap_count','gaps','work_order_purpose')}
   rows.append(row)
print(json.dumps({'mission_id':'F014-NIGHT-20261027-RCC','rows':rows,'read_only':True}))
"""
def write(path,doc):
 tmp=path.with_suffix(path.suffix+'.tmp')
 tmp.write_text(json.dumps(doc,indent=2)+'\n');tmp.chmod(0o600);os.replace(tmp,path)
def copy_outcome(row):
 package=row.get('package') or {}
 if row.get('execution_liveness')!='QUIESCENT' or row.get('resource_lease')!='RELEASED':return None
 source=package.get('archive');expected=package.get('archive_sha256')
 if not source or not expected:return None
 if not re.fullmatch(r'/mnt/data/forge-c/production-local-014/archives/[A-Za-z0-9_./-]+',source) or '..' in Path(source).parts:
  raise ValueError('ARCHIVE_PATH_INVALID')
 if not re.fullmatch('[0-9a-f]{64}',expected) or not re.fullmatch('[A-Za-z0-9_-]+',row['job_id']):
  raise ValueError('ARCHIVE_IDENTITY_INVALID')
 out=ROOT/row['job_id'];out.mkdir(mode=0o700,exist_ok=True);out.chmod(0o700)
 target=out/Path(source).name
 if not target.exists():
  part=target.with_suffix('.zip.part')
  if part.is_symlink():raise ValueError('PART_SYMLINK_REFUSED')
  scp=['scp',*SSH[1:-1],SSH[-1]+':'+source,str(part)]
  subprocess.run(scp,check=True,capture_output=True,timeout=120)
  if hashlib.sha256(part.read_bytes()).hexdigest()!=expected:raise ValueError('ARCHIVE_SHA256_MISMATCH')
  os.chmod(part,0o600);os.replace(part,target)
 if target.is_symlink() or hashlib.sha256(target.read_bytes()).hexdigest()!=expected:
  raise ValueError('LOCAL_COPY_CHANGED')
 audit=verify_archive(target)
 if audit['integrity']!='PASS':raise ValueError('ARCHIVE_INVENTORY_FAILED')
 extracted=out/'review-package'
 if not extracted.exists():
  pending=out/'review-package.partial';pending.mkdir(mode=0o700,exist_ok=True)
  with zipfile.ZipFile(target) as z:
   for info in z.infolist():
    rel=Path(info.filename)
    if rel.is_absolute() or '..' in rel.parts or stat.S_ISLNK(info.external_attr>>16):raise ValueError('ARCHIVE_MEMBER_INVALID')
    if info.is_dir():continue
    dest=pending/rel;dest.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    if dest.is_symlink():raise ValueError('EXTRACTION_SYMLINK_REFUSED')
    with z.open(info) as src,dest.open('wb') as dst:
     while data:=src.read(1<<20):dst.write(data)
    dest.chmod(0o600)
  os.replace(pending,extracted)
 write(out/'outcome.json',row)
 write(out/'transfer-verification.json',{'expected_remote_package_sha256':expected,'integrity':audit,
  'copied_at':datetime.now(timezone.utc).isoformat(),'private_local_copy':True,'model_requests':0})
 (out/'START-HERE.md').write_text('# Qwen run outcome\n\nOrder '+row['order_id']+'; model '+str(row.get('model'))+
  '.\n\nProduct: '+str(package.get('package_status'))+'; '+str(package.get('gap_count'))+
  ' gaps. The full extracted archive is under review-package/.\n\nOpen [review summary](review-package/REVIEW_SUMMARY.md), [outcome metadata](outcome.json) and [transfer verification](transfer-verification.json).\n')
 return str(out)
def collect():
 result=subprocess.run([*SSH,'PYTHONDONTWRITEBYTECODE=1 /mnt/data/forge-c/production-local-014/venv/bin/python -'],input=REMOTE,text=True,capture_output=True,timeout=50)
 if result.returncode:raise RuntimeError('REMOTE_OBSERVATION_FAILED:'+result.stderr[-300:])
 snapshot=json.loads(result.stdout);copies=[]
 for row in snapshot['rows']:
  try:
   path=copy_outcome(row)
   if path:copies.append({'order_id':row['order_id'],'directory':path})
  except Exception as exc:
   copies.append({'order_id':row['order_id'],'transfer_error':type(exc).__name__+':'+str(exc)[:160]})
 write(ROOT/'index.json',{'captured_utc':datetime.now(timezone.utc).isoformat(),'remote':snapshot,
  'local_copies':copies,'remote_jobs_submitted':0,'model_requests':0})
 return copies
parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true')
args=parser.parse_args();ROOT.mkdir(mode=0o700,parents=True,exist_ok=True);ROOT.chmod(0o700)
end=1793347916
while time.time()<end:
 try:print(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'copies':collect()}),flush=True)
 except Exception as exc:print(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'error':type(exc).__name__+':'+str(exc)[:250]}),flush=True)
 if args.once:break
 time.sleep(min(60,max(0,end-time.time())))

