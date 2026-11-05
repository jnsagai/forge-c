"""Normal independent CRE evaluation of the offline whole-release fix; no deployment."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

from forge_factory.common import REPO_ROOT
from forge_factory.reliability import promotion, reproduce as RR
from forge_factory.reliability.capa import CapaRegistry
from forge_factory.reliability.policy import load
from forge_factory.reliability.store import CREStore

B = Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c')
OPS = B / 'ops/scratch'
BASE = 'afa651a717f391f4c1e689516c626141d0f205b1'
CANDIDATE = subprocess.check_output(['git', '-C', str(B / 'repos/forge-c-014-goal-audit'),
                                    'rev-parse', 'HEAD'], text=True).strip()
DEST = OPS / 'capa173-fix-decision-root.json'
assert CANDIDATE.startswith('63a3a91d')
assert REPO_ROOT == B / 'repos/forge-c-014-offline-release-oracle-v2'
assert os.environ.get('FORGE_CRE_ISOLATION') == 'bubblewrap'
assert not DEST.exists()
assert not subprocess.check_output(['git', '-C', str(B / 'repos/forge-c-014-goal-audit'),
                                   'status', '--porcelain'], text=True).strip()
manifest, issues = RR.load_manifest()
assert not issues and len(manifest) == 172, issues
assert manifest['RPR-173']['sha256'] == 'ad007cdf5a59526146019c98e128c9b628e9b7264814032521ac7c8c69645d6a'
inputs = json.loads((OPS / '014-goal-audit-inputs-before-tests-20261105.json').read_text())['files']
s, p = CREStore(), load()
r = CapaRegistry(s, p)
assert r.must('CAPA-173')['state'] == 'REPRODUCER_PENDING'
r.annotate('CAPA-173', 'RPR173 v1 baseline and candidate both ERROR on missing UID2001 NSS entry before cryptographic fixture setup. Preserved runs and frozen v1. Version2 adds private NSS metadata only; no source/oracle-verdict weakening.',
    ['reproducer-run:rr-6274a0a846ad9ce772d7', 'reproducer-run:rr-c12db63f40628e659343'])
with RR.WorktreePool() as pool:
    prepared = []
    for rev in (BASE, CANDIDATE):
        wt = pool.get(rev)
        for entry in inputs:
            src, dst = B / 'repos/forge-c-014-goal-audit' / entry['path'], wt / entry['path']
            assert hashlib.sha256(src.read_bytes()).hexdigest() == entry['sha256']
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            assert hashlib.sha256(dst.read_bytes()).hexdigest() == entry['sha256']
        prepared.append(dict(revision=rev, worktree=str(wt), all8_10_before_tests=True, files=inputs))
    with (OPS / 'capa173-v2-crewtrees-inputs-before-tests.json').open('x') as stream:
        json.dump(prepared, stream, indent=2)
    baseline = RR.run(s, p, 'RPR-173', BASE, 'BASELINE', pool, manifest)
    print(json.dumps(dict(phase='BASELINE', record=baseline)), flush=True)
    candidate = RR.run(s, p, 'RPR-173', CANDIDATE, 'CANDIDATE', pool, manifest)
    print(json.dumps(dict(phase='CANDIDATE', record=candidate)), flush=True)
    assert baseline['verdict'] == 'SYMPTOM_PRESENT' and candidate['verdict'] == 'SYMPTOM_ABSENT'
    assert r.verify_cause('CAPA-173', baseline, candidate)['state'] == 'CAUSE_VERIFIED'
    r.register_fix('CAPA-173')
    decision = promotion.evaluate(CANDIDATE, BASE, s, p, reproducers=['RPR-173'], kind='FIX', pool=pool)
    with DEST.open('x') as stream:
        json.dump(decision, stream, indent=2)
    print(json.dumps(dict(candidate=CANDIDATE, baseline=BASE, decision_id=decision['decision_id'],
        decision=decision['decision'], gates={g['name']: g['result'] for g in decision['hard_gates']})), flush=True)
    assert decision['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
    assert all(g['result'] == 'PASS' for g in decision['hard_gates'])
    prevention = next(g['evidence_refs'] for g in decision['hard_gates'] if g['name'] == 'prevention')
    assert len(prevention) == 172
    rows = {v['run_id']: v for v in RR.reproducer_runs(s, 'RPR-173')}
    current = next(rows[ref.split(':', 1)[1]] for ref in prevention if ref.split(':', 1)[1] in rows)
    r.register_prevention('CAPA-173', current)
    r.link('CAPA-173', 'PROMOTION_DECISION', decision['decision_id'])
    print(json.dumps(dict(capa='CAPA-173', state=r.must('CAPA-173')['state'], activation=False)), flush=True)
