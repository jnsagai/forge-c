"""Independent normal CHANGE gate for the exact GEN35 controller campaign; no deployment."""
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
CANDIDATE = '62fce0a4b2dbcae8dbcd7e5f5952d5ee8acb7fa9'
BASELINE = '84a35ccb3533488be2ec81a40c6b375c72dccf4d'
SOURCE = B / 'repos/forge-c-014-local-gen35-controller'
DESTINATION = OPS / 'local-gen35-controller-change-decision.json'

assert REPO_ROOT == B / 'repos/forge-c-014-capa172-oracle'
assert os.environ.get('FORGE_CRE_ISOLATION') == 'bubblewrap'
assert not DESTINATION.exists(), 'PRESERVE_EXISTING_DECISION_NO_BLIND_REPEAT'
assert subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip() == CANDIDATE
assert not subprocess.check_output(['git', '-C', str(SOURCE), 'status', '--porcelain'], text=True).strip()
manifest = REPO_ROOT / 'tests/reliability/reproducers/manifest.yaml'
assert hashlib.sha256(manifest.read_bytes()).hexdigest() == 'a38af4f2cc017b35ac6303e20dbb763ad2e3a6f3a78eda027e3508f625e92da6'
qualified = json.loads((OPS / 'capa172-fix-decision-root.json').read_text())
assert qualified['candidate_revision'] == BASELINE and qualified['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
assert all(g['result'] == 'PASS' for g in qualified['hard_gates'])
native = json.loads((OPS / 'local-gen35-change-decision.json').read_text())
assert native['candidate_revision'] == '38acc88c549e3713665542474385999822cdd3d4' and native['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
assert all(g['result'] == 'PASS' or g['name'] == 'reproducer' and g['reason_code'] == 'NOT_APPLICABLE_FOR_CHANGE' for g in native['hard_gates'])
decision = promotion.evaluate(CANDIDATE, BASELINE, CREStore(), load(), kind='CHANGE')
with DESTINATION.open('x') as stream:
    json.dump(decision, stream, indent=2)
    stream.write('\n')
print(json.dumps({'candidate': CANDIDATE, 'baseline': BASELINE, 'decision_id': decision['decision_id'],
                  'decision': decision['decision'], 'gates': {g['name']: g['result'] for g in decision['hard_gates']}}), flush=True)
assert decision['decision'] == 'ELIGIBLE_FOR_OFFLINE_REVIEW'
assert all(g['result'] == 'PASS' or g['name'] == 'reproducer' and g['result'] == 'NOT_RUN'
           and g['reason_code'] == 'NOT_APPLICABLE_FOR_CHANGE' for g in decision['hard_gates'])
