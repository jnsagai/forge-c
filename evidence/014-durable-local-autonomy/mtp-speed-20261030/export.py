"""Read-only MTP artifacts and designated semantic proposals; never export prompts/reasoning."""
from pathlib import Path
import hashlib,io,json,os,sys,tarfile
P=Path('/mnt/data/forge-c/production-local-014');O=P/'deployment/q38-mtp-speed-20261030-v1'
for line in (P/'state/afo/conductor.env').read_text().splitlines():
 if line and not line.startswith('#') and '=' in line:k,v=line.split('=',1);os.environ[k]=v
sys.path.insert(0,str(P/'repo/factory/python'))
from forge_factory.afo.queue import ReadSnapshot
files={}
def add(path,name=None):
 if not path.exists():return
 assert path.is_file() and not path.is_symlink()
 raw=path.read_bytes();assert len(raw)<8*1024*1024
 files[name or path.relative_to(O).as_posix()]=raw
for name in ('scope.json','owner-approval.json','preparation.json','mtp-plan.json','execution-tools.json','continuation-complete.json'):add(O/name)
with ReadSnapshot(P/'state/conductor/conductor.sqlite3') as S:
 for variant in ('draft3','draft2','draft4','draft6'):
  E=O/variant
  for name in ('campaign.json','inputs.json','policy.yaml','authorization.json','authorization-message.bin.sig','protocol-report.json','completion.json','progress.json','effective-native-settings.json','activation.json','activation-exit.json','driver-exit.json','history-before-activation.json'):add(E/name)
  for group in ('metrics','results','cases'):
   for p in sorted((E/group).rglob('*')):
    if p.is_file() and p.suffix in ('.json','.md','.c'):add(p)
  for p in (E/'reference').glob('*'):
   if p.is_file() and p.suffix in ('.json','.c'):add(p)
  for p in (E/'metrics').glob('*.json'):
   row=json.loads(p.read_text());ref=row.get('independent_audit') or {}
   if ref.get('path'):
    audit=Path(ref['path']);assert audit.resolve().is_relative_to(P/'state/lrtx/qualification-audits');assert hashlib.sha256(audit.read_bytes()).hexdigest()==ref['sha256'];add(audit,'independent-audits/'+variant+'/'+audit.name)
  manifest=json.loads((E/'campaign.json').read_text());designated=[]
  with S.tx() as c:
   for trial,binding in manifest['jobs'].items():
    rows=c.execute('SELECT proposal_sha256,record FROM afo_semantic_proposals WHERE job_id=?',(binding['job_id'],)).fetchall()
    for row in rows:
     record=json.loads(row['record'])
     assert set(record)<= {'proposal','reason','diagnostic'}
     designated.append({'trial_id':trial,'job_id':binding['job_id'],'proposal_sha256':row['proposal_sha256'],'stored_designated_record':record})
  files[variant+'/designated-semantic-proposals.json']=(json.dumps(designated,indent=2)+'\n').encode()
assert sum(map(len,files.values()))<64*1024*1024
manifest={'schema':'forge-c/private-mtp-transfer/1','scope':'FROZEN_INPUTS_DESIGNATED_RESULTS_NUMERIC_TIMING_NO_HIDDEN_REASONING','complete':{v:(O/v/'completion.json').exists() for v in ('draft3','draft2','draft4','draft6')},'files':{n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in files.items()}}
files['transfer-manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode()
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as t:
 for n,b in files.items():
  h=tarfile.TarInfo(n);h.size=len(b);h.mode=0o600;t.addfile(h,io.BytesIO(b))

