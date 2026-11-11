"""Prove the whole-branch scan's only findings repeat a baseline synthetic fixture.

The scanner's FAIL and original JUnit report remain unchanged. Unknown paths,
credential kinds or values fail this triage; no scanner rule is relaxed.
"""
import subprocess
from pathlib import Path

from forge_factory.common import REPO_ROOT
from forge_factory.safec_bridge.provenance import CREDENTIAL_PATTERNS, scan_public_tree

BASE = "11482e3"
REPORT = "evidence/v0.4/runs/OB-FULL-SUITE/20261027T105033.xml"
FIXTURE = "factory/python/tests/test_m5_lessons.py"
baseline = subprocess.check_output(["git", "show", f"{BASE}:{FIXTURE}"], cwd=REPO_ROOT, text=True)
assert 'def test_t031_malicious_or_unsafe_lessons_quarantined' in baseline
findings = scan_public_tree(REPO_ROOT, BASE)["findings"]
assert len(findings) == 2, findings
assert {f["kind"] for f in findings} == {"CREDENTIAL:GITHUB_TOKEN", "CREDENTIAL:ASSIGNED_SECRET"}
report = (REPO_ROOT / REPORT).read_text().splitlines()
for finding in findings:
    assert finding["path"] == REPORT, finding
    line = report[finding["line"] - 1]
    assert 'name="test_t031_malicious_or_unsafe_lessons_quarantined[root_cause-' in line
    kind = finding["kind"].split(":")[1]
    matches = list(CREDENTIAL_PATTERNS[kind].finditer(line))
    assert matches and all(m.group("s") in baseline for m in matches)
print(f"PASS: both findings repeat the synthetic malicious-lesson fixture already present at {BASE}:{FIXTURE}")
print("The raw whole-branch provenance result remains FAIL; no real credential or unknown finding was found.")
