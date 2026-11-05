"""Normal independent CRE qualification of dependency-aware diagnosis; no deployment."""
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
BASE = '3e8936a27f847b32bb76eef4a24bc83cc2daad20'
CANDIDATE = subprocess.check_output(['git', '-C', str(B / 'repos/forge-c-014-diagnosis-dependencies'),
                                    'rev-parse', 'HEAD'], text=True).strip()
DEST = OPS / 'capa176-fix-decision-root.json'
assert len(CANDIDATE) == 40
assert REPO_ROOT == B / 'repos/forge-c-014-diagnosis-dependencies-oracle'
assert os.environ.get('FORGE_CRE_ISOLATION') == 'bubblewrap'
assert not DEST.exists()
assert not subprocess.check_output(['git', '-C', str(B / 'repos/forge-c-014-diagnosis-dependencies'),
                                   'status', '--porcelain'], text=True).strip()
manifest, issues = RR.load_manifest()
assert not issues and len(manifest) == 175, issues
assert manifest['RPR-176']['sha256'] == 'c51abf274b7e2d8b3217dbd418c46a4aa2901fe558a1c2d0cc8a17ce8ad1a760'
inputs = json.loads((OPS / 'diagnosis-dependencies-inputs-before-tests.json').read_text())['files']
s, p = CREStore(), load()
r = CapaRegistry(s, p)
assert r.get('CAPA-176') is None, 'EXISTING_CAPA_REQUIRES_RESUME_REVIEW'
r.open('CAPA-176', incident_ids=['AUDIT-DEPENDENT-OBJECTIVE-BEFORE-PREREQUISITE'], fingerprints=[],
       reason='Diagnosis serializes AAA-DEPENDENT before unresolved ZZZ-PREREQUISITE despite a complete sealed dependency graph. Actual prepare and pending broker boundaries also permit the inconsistent scope.')
r.triage('CAPA-176', 'Preparation and request serialization choose lexical IDs instead of validated ready objectives; pending broker admission trusts that scope. Validate the entire graph and choose one dependency-free unresolved objective at every boundary without changing global evidence, mission identity or allowances.', 'RPR-176', 'RULE')
with RR.WorktreePool() as pool:
    prepared = []
    for rev in (BASE, CANDIDATE):
        wt = pool.get(rev)
        for entry in inputs:
            src, dst = B / 'repos/forge-c-014-diagnosis-dependencies' / entry['path'], wt / entry['path']
            assert hashlib.sha256(src.read_bytes()).hexdigest() == entry['sha256']
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            assert hashlib.sha256(dst.read_bytes()).hexdigest() == entry['sha256']
        prepared.append(dict(revision=rev, worktree=str(wt), all8_10_before_tests=True, files=inputs))
    with (OPS / 'capa176-crewtrees-inputs-before-tests.json').open('x') as stream:
        json.dump(prepared, stream, indent=2)
    baseline = RR.run(s, p, 'RPR-176', BASE, 'BASELINE', pool, manifest)
    print(json.dumps(dict(phase='BASELINE', record=baseline)), flush=True)
    candidate = RR.run(s, p, 'RPR-176', CANDIDATE, 'CANDIDATE', pool, manifest)
    print(json.dumps(dict(phase='CANDIDATE', record=candidate)), flush=True)
    assert baseline['verdict'] == 'SYMPTOM_PRESENT' and candidate['verdict'] == 'SYMPTOM_ABSENT'
    assert r.verify_cause('CAPA-176', baseline, candidate)['state'] == 'CAUSE_VERIFIED'
    r.register_fix('CAPA-176')
    decision = promotion.evaluate(CANDIDATE, BASE, s, p, reproducers=['RPR-176'], kind='FIX', pool=pool)
    with DEST.open('x') as stream:
        json.dump(decision, stream, indent=2)
    print(json.dumps(dict(candidate=CANDIDATE, baseline=BASE, decision_id=decision['decision_id'],
        decision=decision['decision'], gates={g['name']: g['result'] for g in decision['hard_gates']})), flush=True)
    assert decision['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
    assert all(g['result'] == 'PASS' for g in decision['hard_gates'])
    prevention = next(g['evidence_refs'] for g in decision['hard_gates'] if g['name'] == 'prevention')
    assert len(prevention) == 175
    rows = {v['run_id']: v for v in RR.reproducer_runs(s, 'RPR-176')}
    current = next(rows[ref.split(':', 1)[1]] for ref in prevention if ref.split(':', 1)[1] in rows)
    r.register_prevention('CAPA-176', current)
    r.link('CAPA-176', 'PROMOTION_DECISION', decision['decision_id'])
    print(json.dumps(dict(capa='CAPA-176', state=r.must('CAPA-176')['state'], activation=False)), flush=True)
