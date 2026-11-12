"""Independent normal CRE causal/FIX evaluation; no deployment or owner authority."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

from forge_factory.common import REPO_ROOT
from forge_factory.reliability import promotion, reproduce as RR
from forge_factory.reliability.capa import CapaRegistry
from forge_factory.reliability.policy import load
from forge_factory.reliability.store import CREStore

B = Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c')
OPS = B / 'ops/scratch'
C = '84a35ccb3533488be2ec81a40c6b375c72dccf4d'
BASE = '2035280de096a6f1107aa052db196c0a6c091ffc'
DESTINATION = OPS / 'capa172-fix-decision-root.json'
assert REPO_ROOT == B / 'repos/forge-c-014-capa172-oracle'
assert os.environ.get('FORGE_CRE_ISOLATION') == 'bubblewrap'
assert not DESTINATION.exists(), 'PRESERVE_EXISTING_DECISION'
assert hashlib.sha256((REPO_ROOT / 'tests/reliability/reproducers/manifest.yaml').read_bytes()).hexdigest() == 'a38af4f2cc017b35ac6303e20dbb763ad2e3a6f3a78eda027e3508f625e92da6'
assert subprocess.check_output(['git', '-C', str(B / 'repos/forge-c-014-integration17'), 'rev-parse', 'HEAD'], text=True).strip() == C
assert not subprocess.check_output(['git', '-C', str(B / 'repos/forge-c-014-integration17'), 'status', '--porcelain'], text=True).strip()
validation = json.loads((OPS / 'codex-integration17-independent-validation.json').read_text())
assert validation['candidate'] == C and validation['failures'] == validation['errors'] == 0
assert validation['skipped'] == ['test_act_dry_run_replay_over_todays_line_state']
s = CREStore()
p = load()
r = CapaRegistry(s, p)
manifest, issues = RR.load_manifest()
assert not issues and len(manifest) == 171, issues
assert r.get('CAPA-172') is None, 'EXISTING_CAPA_REQUIRES_EXPLICIT_RESUME_REVIEW'
r.open('CAPA-172', fingerprints=[], incident_ids=['CAPA-172'],
       reason='Owner approved two-week replacement window; qualified I16 public deadline extension cannot admit next finite LINE product/M9 intake without attempting immutable mission reset. No production retry, signature or exposure reset.')
r.triage('CAPA-172',
         'LINE next-order binding re-registers effective amended limits against the immutable original mission. M9 equates a separately signed effective deadline grant with the original CONTROL identity. Validate raw original authority and replayed exact effective mission, then link without re-registration.',
         'RPR-172', 'RULE')
with RR.WorktreePool() as pool:
    baseline = RR.run(s, p, 'RPR-172', BASE, 'BASELINE', pool, manifest)
    print(json.dumps({'phase': 'BASELINE', 'record': baseline}), flush=True)
    candidate = RR.run(s, p, 'RPR-172', C, 'CANDIDATE', pool, manifest)
    print(json.dumps({'phase': 'CANDIDATE', 'record': candidate}), flush=True)
    causal = r.verify_cause('CAPA-172', baseline, candidate)
    assert causal['state'] == 'CAUSE_VERIFIED', causal
    r.register_fix('CAPA-172')
    d = promotion.evaluate(C, BASE, s, p, reproducers=['RPR-172'], kind='FIX', pool=pool)
    with DESTINATION.open('x') as stream:
        json.dump(d, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'candidate': C, 'baseline': BASE, 'decision_id': d['decision_id'],
                      'decision': d['decision'], 'gates': {g['name']: g['result'] for g in d['hard_gates']}}), flush=True)
    assert d['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
    assert all(g['result'] == 'PASS' for g in d['hard_gates']), d
