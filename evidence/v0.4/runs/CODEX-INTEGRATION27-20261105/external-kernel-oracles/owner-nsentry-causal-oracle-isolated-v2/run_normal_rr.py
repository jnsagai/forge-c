"""Unchanged qualified G36 RR, isolated baseline/candidate, hash all12 before tests."""
import json,shutil,hashlib,os
from pathlib import Path
from forge_factory.reliability import reproduce as R
from forge_factory.reliability.policy import load
from forge_factory.reliability.store import CREStore
B=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c');O=B/'ops/scratch';OUT=O/'owner-nsentry-causal-oracle-isolated-v2'
assert R.REPO_ROOT==B/'repos/forge-c-014-local-gen36'
assert os.environ['FORGE_CRE_ISOLATION']=='bubblewrap' and os.environ['FORGE_CPU_JOBS']=='1'
base='887820300340dcc31a03f3dc46c31107e9aef9f3';cand='a42f715489625f44f51213c72a422d3ae2944a40'
files=json.loads((O/'owner-supervised-development-inputs-before-tests.json').read_text())['all12_inputs_verified_before_any_tests'];assert len(files)==12
reps,issues=R.load_manifest(OUT/'manifest.yaml');assert not issues
with R.WorktreePool() as pool:
 receipts=[]
 for rev in (base,cand):
  t=pool.get(rev)
  for row in files:
   dst=t/row['path'];dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(R.REPO_ROOT/row['path'],dst);assert hashlib.sha256(dst.read_bytes()).hexdigest()==row['sha256']
  receipts.append(dict(revision=rev,worktree=str(t),all12=files,before_any_tests=True))
 with (OUT/'inputs-before-tests.json').open('x') as f:json.dump(receipts,f,indent=2);f.write('\n')
 store=CREStore();policy=load();records={}
 for key,rev,role in [('baseline',base,'BASELINE'),('candidate',cand,'CANDIDATE')]:
  records[key]=R.run(store,policy,'AFO-PROVIDER-NSENTRY-20261105',rev,role,pool,reps);print(key,records[key],flush=True)
 records['causal']=R.causal_verdict(records['baseline'],records['candidate'])
 with (OUT/'normal-rr-result.json').open('x') as f:json.dump(records,f,indent=2);f.write('\n')
 print(records['causal'],flush=True)
