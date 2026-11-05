"""One normal independent CHANGE, immutable I21 caller and explicit12-input pool."""
import hashlib,json,os,shutil,subprocess
from pathlib import Path
from forge_factory.common import REPO_ROOT
from forge_factory.reliability import promotion,reproduce as RR,isolation
from forge_factory.reliability.policy import load
from forge_factory.reliability.store import CREStore

B=Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c');O=B/'ops/scratch'
BASE='d5024d62842b276c4a81fd51ed399704c7fc43cb';CAND='7f55de5c10a413bb251e91d8c6b9f4d61481df47'
assert REPO_ROOT==B/'repos/forge-c-014-integration21'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO_ROOT,text=True).strip()==BASE
assert os.environ.get('FORGE_CRE_ISOLATION')=='bubblewrap' and os.environ.get('FORGE_CPU_JOBS')=='1'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=B/'repos/forge-c-014-plant-floor-omniverse')
prepared=json.loads((O/'diagnosis-dependencies-inputs-before-tests.json').read_text());assert len(prepared['files'])==12
manifest,issues=RR.load_manifest();assert not issues and len(manifest)==175 and 'RPR-176' in manifest
# Existing executor's readable-input seam; evaluator/oracles/thresholds unchanged.
execute=isolation.execute
pinned=B/'inputs';assert pinned.is_dir()
def with_pinned(role,cmd,*,cwd,env,writable,readable=(),timeout=1800):
    return execute(role,cmd,cwd=cwd,env=env,writable=writable,readable=[*readable,pinned],timeout=timeout)
isolation.execute=with_pinned
with RR.WorktreePool() as pool:
    inventory=[]
    for revision in (BASE,CAND):
        tree=pool.get(revision);files=[]
        for row in prepared['files']:
            src=Path(prepared['worktree'])/row['path'];dst=tree/row['path']
            assert src.is_file() and not src.is_symlink() and hashlib.sha256(src.read_bytes()).hexdigest()==row['sha256']
            if dst.exists():assert dst.is_file() and not dst.is_symlink() and hashlib.sha256(dst.read_bytes()).hexdigest()==row['sha256']
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
            assert hashlib.sha256(dst.read_bytes()).hexdigest()==row['sha256']
            files.append({'path':row['path'],'sha256':row['sha256']})
        inventory.append({'revision':revision,'worktree':str(tree),'files':files,'before_any_tests':True})
    with (O/'plant-floor-monitor-cre-inputs-before-tests.json').open('x') as f:json.dump(inventory,f,indent=2)
    decision=promotion.evaluate(CAND,BASE,CREStore(),load(),kind='CHANGE',pool=pool)
    with (O/'plant-floor-monitor-change-decision.json').open('x') as f:json.dump(decision,f,indent=2)
    print(json.dumps({'candidate':CAND,'baseline':BASE,'decision_id':decision['decision_id'],'decision':decision['decision'],'gates':{g['name']:g['result'] for g in decision['hard_gates']}}),flush=True)
    assert decision['decision']=='ELIGIBLE_FOR_OFFLINE_REVIEW'
    assert all(g['result']=='PASS' or g['name']=='reproducer' and g['result']=='NOT_RUN' and g['reason_code']=='NOT_APPLICABLE_FOR_CHANGE' for g in decision['hard_gates'])
    assert len(next(g['evidence_refs'] for g in decision['hard_gates'] if g['name']=='prevention'))==175
