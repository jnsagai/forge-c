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
assert REPO_ROOT == B / 'repos/forge-c-014-maintenance-renewal-oracle'
assert os.environ.get('FORGE_CRE_ISOLATION') == 'bubblewrap'
assert not DEST.exists()
assert not subprocess.check_output(['git', '-C', str(B / 'repos/forge-c-014-offline-roundtrip'),
                                   'status', '--porcelain'], text=True).strip()
manifest, issues = RR.load_manifest()
assert not issues and len(manifest) == 173, issues
assert manifest['RPR-174']['sha256'] == '75d8f7629a3778660738b7b880cef572f34dacb0c34b0a2c8bbac823ee980564'
inputs = json.loads((OPS / '014-goal-audit-inputs-before-tests-20261105.json').read_text())['files']
s, p = CREStore(), load()
r = CapaRegistry(s, p)
assert r.get('CAPA-174') is None, 'EXISTING_CAPA_REQUIRES_RESUME_REVIEW'
r.open('CAPA-174', incident_ids=['M7-RENEWED-MISSION-REVIEW-REFUSED'], fingerprints=[],
       reason='Normal maintenance review refuses an otherwise valid renewed signed control because its effective mission deadline differs from immutable initial limits. Owner requests implementation continue, with clock synchronization ignored.')
r.triage('CAPA-174', 'Maintenance guard compares raw initial limits instead of validated effective snapshot. Compare exact effective limits while retaining immutable initial authority/lineage, current signatures/source/profile/intent and earlier per-job wall; never reset exposure.', 'RPR-174', 'RULE')
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
    with (OPS / 'capa174-crewtrees-inputs-before-tests.json').open('x') as stream:
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
