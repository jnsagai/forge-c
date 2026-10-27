"""Re-derive the four approved subjects with current code in private state; never alter owner state."""
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from forge_factory.common import REPO_ROOT, state_dir
from forge_factory.onboarding import derive
from forge_factory.onboarding.approval import verify
from forge_factory.onboarding.facts import canonical_hash

root = state_dir()
record = json.loads((REPO_ROOT / 'evidence/v0.4/benchmark/st-drivers-hal-ob/record.json').read_text())
def snapshot(key):
    base = root / 'onboarding' / key / 'onboarding'
    return {name: hashlib.sha256((base / name).read_bytes()).hexdigest()
            for name in ('package.json', 'approval.json', 'approval.json.sig')}

before = {p['key']: snapshot(p['key']) for p in record['packages'].values()}
for p in record['packages'].values():
    assert verify(root / 'onboarding' / p['key'])['code'] == 'APPROVAL_OK'
prior = os.environ.get('FORGE_STATE_DIR')
try:
    with tempfile.TemporaryDirectory(prefix='f016-signed-rederive-') as scratch:
        os.environ['FORGE_STATE_DIR'] = scratch
        for peripheral, p in record['packages'].items():
            key = p['key']
            cache = root / 'onboarding' / key / 'onboarding/model_gate.json'
            if cache.is_file():
                target = Path(scratch) / 'onboarding' / key / 'onboarding/model_gate.json'
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(cache, target)
            package = derive(REPO_ROOT / 'examples' / key)
            assert package['sha256'] == canonical_hash(package) == p['sha256'], peripheral
            print(peripheral.upper(), 'PASS same signed subject', package['sha256'])
finally:
    if prior is None:
        os.environ.pop('FORGE_STATE_DIR', None)
    else:
        os.environ['FORGE_STATE_DIR'] = prior
for p in record['packages'].values():
    key = p['key']
    assert snapshot(key) == before[key], 'actual owner bytes changed'
    assert verify(root / 'onboarding' / key)['code'] == 'APPROVAL_OK'
print('PASS all four owner packages and signatures remain byte-identical and valid; no authoring model call requested')
