"""Independent normal CHANGE gate for the exact integrated M9 source; no deployment."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

from forge_factory.common import REPO_ROOT
from forge_factory.reliability import promotion
from forge_factory.reliability.policy import load
from forge_factory.reliability.store import CREStore

B = Path('/media/jefferson/11c42dee-73a3-4c2b-ab42-a0440011d9e0/forge-c')
OPS = B / 'ops/scratch'
CANDIDATE = 'a856b521fccab43309ee4bfe1cded42c2eb37938'
BASELINE = 'c121ea79813bcd06f51b2468a067e7584ef15cdf'
SOURCE = B / 'repos/forge-c-014-integration16'
DESTINATION = OPS / 'codex-integration16-change-decision.json'

assert REPO_ROOT == B / 'repos/forge-c-014-line-soak-oracle'
assert os.environ.get('FORGE_CRE_ISOLATION') == 'bubblewrap'
assert not DESTINATION.exists(), 'PRESERVE_EXISTING_DECISION_NO_BLIND_REPEAT'
assert subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip() == CANDIDATE
assert not subprocess.check_output(['git', '-C', str(SOURCE), 'status', '--porcelain'], text=True).strip()
manifest = REPO_ROOT / 'tests/reliability/reproducers/manifest.yaml'
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == 'e12fd44033ec0d945ea900bfa6d5e57a8edc5c3c5837263d49534da71bee820d'
decision = promotion.evaluate(CANDIDATE, BASELINE, CREStore(), load(), kind='CHANGE')
with DESTINATION.open('x') as stream:
    json.dump(decision, stream, indent=2)
    stream.write('\n')
print(json.dumps({'candidate': CANDIDATE, 'baseline': BASELINE, 'decision_id': decision['decision_id'],
                  'decision': decision['decision'], 'gates': {g['name']: g['result'] for g in decision['hard_gates']}}), flush=True)
assert decision['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
assert all(g['result'] == 'PASS' or g['name'] == 'reproducer' and g['result'] == 'NOT_RUN'
           and g['reason_code'] == 'NOT_APPLICABLE_FOR_CHANGE' for g in decision['hard_gates'])
