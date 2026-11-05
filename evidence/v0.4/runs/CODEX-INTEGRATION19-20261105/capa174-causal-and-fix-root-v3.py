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
BASE = '03f968603369f7934fde478ae8fd107c40ecec8b'
CANDIDATE = subprocess.check_output(['git', '-C', str(B / 'repos/forge-c-014-offline-roundtrip'),
                                    'rev-parse', 'HEAD'], text=True).strip()
DEST = OPS / 'capa174-fix-decision-root.json'
assert CANDIDATE.startswith('d244e2df')
assert REPO_ROOT == B / 'repos/forge-c-014-maintenance-renewal-oracle-v3'
assert os.environ.get('FORGE_CRE_ISOLATION') == 'bubblewrap'
assert not DEST.exists()
assert not subprocess.check_output(['git', '-C', str(B / 'repos/forge-c-014-offline-roundtrip'),
                                   'status', '--porcelain'], text=True).strip()
manifest, issues = RR.load_manifest()
assert not issues and len(manifest) == 173, issues
assert manifest['RPR-174']['sha256'] == '9c863ccdc9549fabd9761471b457a1698c2808cc0b22dbc85f396dda35ec654d'
inputs = json.loads((OPS / '014-goal-audit-inputs-before-tests-20261105.json').read_text())['files']
s, p = CREStore(), load()
r = CapaRegistry(s, p)
assert r.must('CAPA-174')['state'] == 'REPRODUCER_PENDING'
r.annotate('CAPA-174', 'First pair ERROR before maintenance predicate because scoped detached Git metadata unavailable. Preserve both runner errors and oracle versions; version3 declares source identity as isolated fixture leaf while CRE import preflight pins actual code and real signature/effective mission checks remain.',
 ['reproducer-run:rr-a480d4b26c2c7fad407c','reproducer-run:rr-e97d1a258d7b13dea15a'])
with RR.WorktreePool() as pool:
    prepared = []
    for rev in (BASE, CANDIDATE):
        wt = pool.get(rev)
        for entry in inputs:
            src, dst = B / 'repos/forge-c-014-offline-roundtrip' / entry['path'], wt / entry['path']
            assert hashlib.sha256(src.read_bytes()).hexdigest() == entry['sha256']
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            assert hashlib.sha256(dst.read_bytes()).hexdigest() == entry['sha256']
        prepared.append(dict(revision=rev, worktree=str(wt), all8_10_before_tests=True, files=inputs))
    with (OPS / 'capa174-v3-crewtrees-inputs-before-tests.json').open('x') as stream:
        json.dump(prepared, stream, indent=2)
    baseline = RR.run(s, p, 'RPR-174', BASE, 'BASELINE', pool, manifest)
    print(json.dumps(dict(phase='BASELINE', record=baseline)), flush=True)
    candidate = RR.run(s, p, 'RPR-174', CANDIDATE, 'CANDIDATE', pool, manifest)
    print(json.dumps(dict(phase='CANDIDATE', record=candidate)), flush=True)
    assert baseline['verdict'] == 'SYMPTOM_PRESENT' and candidate['verdict'] == 'SYMPTOM_ABSENT'
    assert r.verify_cause('CAPA-174', baseline, candidate)['state'] == 'CAUSE_VERIFIED'
    r.register_fix('CAPA-174')
    decision = promotion.evaluate(CANDIDATE, BASE, s, p, reproducers=['RPR-174'], kind='FIX', pool=pool)
    with DEST.open('x') as stream:
        json.dump(decision, stream, indent=2)
    print(json.dumps(dict(candidate=CANDIDATE, baseline=BASE, decision_id=decision['decision_id'],
        decision=decision['decision'], gates={g['name']: g['result'] for g in decision['hard_gates']})), flush=True)
    assert decision['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
    assert all(g['result'] == 'PASS' for g in decision['hard_gates'])
    prevention = next(g['evidence_refs'] for g in decision['hard_gates'] if g['name'] == 'prevention')
    assert len(prevention) == 173
    rows = {v['run_id']: v for v in RR.reproducer_runs(s, 'RPR-174')}
    current = next(rows[ref.split(':', 1)[1]] for ref in prevention if ref.split(':', 1)[1] in rows)
    r.register_prevention('CAPA-174', current)
    r.link('CAPA-174', 'PROMOTION_DECISION', decision['decision_id'])
    print(json.dumps(dict(capa='CAPA-174', state=r.must('CAPA-174')['state'], activation=False)), flush=True)
