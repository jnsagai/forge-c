"""Independent serial causal FIX qualification of a frozen development candidate.

No deployment, grant creation, mission amendment, provider or model effects.
Caller is the unchanged qualified G36 native baseline with its private inputs.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from forge_factory.common import REPO_ROOT
from forge_factory.reliability import promotion, reproduce as RR
from forge_factory.reliability.policy import load
from forge_factory.reliability.store import CREStore

B = Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c')
OPS = B / 'ops/scratch'
CALLER = '74e44a1f23b01f3200350436df1691249b441292'
BASE = '887820300340dcc31a03f3dc46c31107e9aef9f3'
STAGED = OPS / 'owner-nsentry-causal-oracle-v1/manifest.yaml'
STAGED_SHA = 'ad6ab1254210021dbd93f70d930a040b01e7b85ed076689971e0b49d11cce0a1'
REPRODUCER = 'AFO-PROVIDER-NSENTRY-20261105'


def git(tree, *args):
    return subprocess.check_output(['git', *args], cwd=tree, text=True).strip()


def save(path, data):
    with path.open('x') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--candidate-worktree', required=True, type=Path)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--receipt-prefix', required=True)
    a = ap.parse_args()
    assert a.receipt_prefix.replace('-', '').replace('_', '').isalnum()
    prefix = OPS / a.receipt_prefix
    assert REPO_ROOT == B / 'repos/forge-c-014-local-gen36'
    assert git(REPO_ROOT, 'rev-parse', 'HEAD') == CALLER
    assert not git(REPO_ROOT, 'status', '--porcelain')
    assert os.environ.get('FORGE_CRE_ISOLATION') == 'bubblewrap'
    assert os.environ.get('FORGE_CPU_JOBS') == '1'
    assert not os.environ.get('FORGE_OWNER_DEVELOPMENT_RECORD')
    assert not os.environ.get('FORGE_OWNER_DEVELOPMENT_SHA256')
    source = a.candidate_worktree.resolve()
    assert git(source, 'rev-parse', 'HEAD') == a.candidate
    assert not git(source, 'status', '--porcelain')
    assert git(source, 'merge-base', '--is-ancestor', BASE, a.candidate) == ''
    changed = git(source, 'diff', '--name-only', BASE, a.candidate).splitlines()
    assert changed and all(p.startswith(('factory/python/', 'docs/', 'specs/014-durable-local-autonomy/')) for p in changed)
    assert not any(p.startswith(('specs/014-durable-local-autonomy/contracts/',)) for p in changed)
    prepared = json.loads((OPS / 'owner-supervised-development-inputs-before-tests.json').read_text())
    assert prepared['base'] == CALLER
    files = prepared['all12_inputs_verified_before_any_tests']
    assert len(files) == len({row['path'] for row in files}) == 12
    for row in files:
        assert hashlib.sha256((REPO_ROOT / row['path']).read_bytes()).hexdigest() == row['sha256']
        assert hashlib.sha256((source / row['path']).read_bytes()).hexdigest() == row['sha256']
    assert hashlib.sha256(STAGED.read_bytes()).hexdigest() == STAGED_SHA
    staged, staged_issues = RR.load_manifest(STAGED)
    assert not staged_issues and list(staged) == [REPRODUCER]
    manifest, issues = RR.load_manifest()
    assert not issues and len(manifest) == 175
    assert manifest['RPR-176']['sha256'] == '0d4cbd30576e0a35204c3efee3517732ce84e2074f4dbae077b03a7679aa8ec6'
    decision_path = prefix.with_name(prefix.name + '-decision.json')
    assert not decision_path.exists()
    with RR.WorktreePool() as pool:
        receipts = []
        for revision in (BASE, a.candidate):
            tree = pool.get(revision)
            for row in files:
                src, dst = REPO_ROOT / row['path'], tree / row['path']
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                assert hashlib.sha256(dst.read_bytes()).hexdigest() == row['sha256']
            receipts.append(dict(revision=revision, worktree=str(tree), files=files, before_any_tests=True))
        save(prefix.with_name(prefix.name + '-worktrees-before-tests.json'), receipts)
        decision = promotion.evaluate(a.candidate, BASE, CREStore(), load(),
                                      reproducers=[REPRODUCER], kind='FIX', pool=pool, staged_manifest=STAGED)
        save(decision_path, decision)
    print(json.dumps(dict(candidate=a.candidate, decision_id=decision['decision_id'], decision=decision['decision'],
                          gates={g['name']: g['result'] for g in decision['hard_gates']})), flush=True)
    assert decision['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
    assert len(decision['hard_gates']) == 7 and all(g['result'] == 'PASS' for g in decision['hard_gates'])
    assert len(decision['reproducer_evidence_refs']) == 2
    assert len(next(g['evidence_refs'] for g in decision['hard_gates'] if g['name'] == 'prevention')) == 175


if __name__ == '__main__':
    main()
