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
BASE = '18814617abb98491abb5c03adb0802553634f14f'
CANDIDATE = subprocess.check_output(['git', '-C', str(B / 'repos/forge-c-014-review-learning'),
                                    'rev-parse', 'HEAD'], text=True).strip()
DEST = OPS / 'capa175-fix-decision-root.json'
assert len(CANDIDATE) == 40
assert REPO_ROOT == B / 'repos/forge-c-014-review-learning-oracle'
assert os.environ.get('FORGE_CRE_ISOLATION') == 'bubblewrap'
assert not DEST.exists()
assert not subprocess.check_output(['git', '-C', str(B / 'repos/forge-c-014-review-learning'),
                                   'status', '--porcelain'], text=True).strip()
manifest, issues = RR.load_manifest()
assert not issues and len(manifest) == 174, issues
assert manifest['RPR-175']['sha256'] == '4ea6b9e926f69d831ab69bd551b5067cd17df95b1b1b4b576c72af3e9184a6d1'
inputs = json.loads((OPS / '014-goal-audit-inputs-before-tests-20261105.json').read_text())['files']
s, p = CREStore(), load()
r = CapaRegistry(s, p)
assert r.get('CAPA-175') is None, 'EXISTING_CAPA_REQUIRES_RESUME_REVIEW'
r.open('CAPA-175', incident_ids=['OWNER-REVIEW-LEARNING-REGISTRATION-REFUSED'], fingerprints=[],
       reason='Review intake excludes nine baselines explicitly registered as learning after completed calibration. Owner requires human reviews to produce durable CAPA/prevention learning without contaminating unspent held-out sets.')
r.triage('CAPA-175', 'Default set membership ignores immutable post-calibration learning registrations. Replay source-bound transitions and require completed calibration, retaining unspent heldout cases and all original evidence. Connect verified reviews to existing guarded CAPA and qualified scoped memory.', 'RPR-175', 'RULE')
with RR.WorktreePool() as pool:
    prepared = []
    for rev in (BASE, CANDIDATE):
        wt = pool.get(rev)
        for entry in inputs:
            src, dst = B / 'repos/forge-c-014-review-learning' / entry['path'], wt / entry['path']
            assert hashlib.sha256(src.read_bytes()).hexdigest() == entry['sha256']
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            assert hashlib.sha256(dst.read_bytes()).hexdigest() == entry['sha256']
        prepared.append(dict(revision=rev, worktree=str(wt), all8_10_before_tests=True, files=inputs))
    with (OPS / 'capa175-crewtrees-inputs-before-tests.json').open('x') as stream:
        json.dump(prepared, stream, indent=2)
    baseline = RR.run(s, p, 'RPR-175', BASE, 'BASELINE', pool, manifest)
    print(json.dumps(dict(phase='BASELINE', record=baseline)), flush=True)
    candidate = RR.run(s, p, 'RPR-175', CANDIDATE, 'CANDIDATE', pool, manifest)
    print(json.dumps(dict(phase='CANDIDATE', record=candidate)), flush=True)
    assert baseline['verdict'] == 'SYMPTOM_PRESENT' and candidate['verdict'] == 'SYMPTOM_ABSENT'
    assert r.verify_cause('CAPA-175', baseline, candidate)['state'] == 'CAUSE_VERIFIED'
    r.register_fix('CAPA-175')
    decision = promotion.evaluate(CANDIDATE, BASE, s, p, reproducers=['RPR-175'], kind='FIX', pool=pool)
    with DEST.open('x') as stream:
        json.dump(decision, stream, indent=2)
    print(json.dumps(dict(candidate=CANDIDATE, baseline=BASE, decision_id=decision['decision_id'],
        decision=decision['decision'], gates={g['name']: g['result'] for g in decision['hard_gates']})), flush=True)
    assert decision['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
    assert all(g['result'] == 'PASS' for g in decision['hard_gates'])
    prevention = next(g['evidence_refs'] for g in decision['hard_gates'] if g['name'] == 'prevention')
    assert len(prevention) == 174
    rows = {v['run_id']: v for v in RR.reproducer_runs(s, 'RPR-175')}
    current = next(rows[ref.split(':', 1)[1]] for ref in prevention if ref.split(':', 1)[1] in rows)
    r.register_prevention('CAPA-175', current)
    r.link('CAPA-175', 'PROMOTION_DECISION', decision['decision_id'])
    print(json.dumps(dict(capa='CAPA-175', state=r.must('CAPA-175')['state'], activation=False)), flush=True)
