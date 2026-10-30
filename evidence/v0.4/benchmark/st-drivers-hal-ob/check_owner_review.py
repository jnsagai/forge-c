"""Validate exact owner decisions and bound artifacts; never relabel raw audit or gate results."""
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DECISIONS = ROOT / 'evidence/easa/owner-decisions'

def read(path):
    return json.loads(path.read_text())

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

record = read(HERE / 'record.json')
owner = read(DECISIONS / 'OD-2026-10-27-01-blocked-onboarding-handovers.json')
exception = read(DECISIONS / 'OD-2026-10-27-02-sc001-history-exception.json')
assert owner['statement'] == 'Accept all four BLOCKED handovers; keep findings open'
assert owner['decision'] == 'ACCEPT_BLOCKED_HANDOVERS_WITH_OPEN_FINDINGS'
assert owner['record_sha256'] == digest(HERE / 'record.json')
assert owner['review_brief_sha256'] == digest(HERE / 'OWNER-REVIEW.md')
assert {p['peripheral'] for p in owner['packages']} == {'gpio', 'spi', 'usart', 'tim'}
for p in owner['packages']:
    o = [o for o in record['orders'] if o['peripheral'] == p['peripheral']][-1]
    a = o['attempts'][-1]
    package = a['package_record']
    assert p['request_id'] == o['request_id'] and p['attempt_id'] == a['attempt_id']
    assert p['package_status'] == package['package_status'] == o['state'] == 'BLOCKED'
    assert p['gap_count'] == package['gap_count'] > 0
    assert p['archive_sha256'] == package['archive_sha256'] == digest(Path(p['archive']))
assert exception['statement'] == 'Accept this scoped exception; retain the raw FAIL'
assert exception['decision'] == 'ACCEPT_SCOPED_HISTORICAL_EXCEPTION'
raw = ROOT / 'evidence/v0.4/runs/OB-SC001-HISTORY/latest.json'
active = ROOT / 'evidence/v0.4/runs/OB-SC001-PREPARATION/latest.json'
assert read(raw)['status'] == exception['raw_history_status'] == 'FAIL'
assert read(active)['status'] == 'PASS'
assert exception['raw_history_evidence_sha256'] == digest(raw)
assert exception['active_input_evidence_sha256'] == digest(active)
diff = subprocess.check_output(['git', 'diff', exception['baseline_revision'], 'HEAD', '--',
                                'config/factory/peripherals'], cwd=ROOT)
assert hashlib.sha256(diff).hexdigest() == exception['peripheral_profile_diff_sha256']
spec = importlib.util.spec_from_file_location('ob_check', HERE / 'ob_check.py')
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
checker.check(record)
print('PASS owner accepted the four exact BLOCKED handovers with findings open and the exact historical exception')
print('Raw SC-001 remains FAIL. This proves owner adjudication and artifact binding, not driver/safety/merge approval.')
