"""Check a complete pytest JUnit report against the three handoff baseline failures.

The raw suite is still FAIL when these tests fail; this check only establishes
that the failure set has not grown. It never rewrites the report or test results.
"""
import hashlib
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

EXPECTED = {
    "test_cre_d7_e2e.test_latest_local_qwen_work_order_has_real_terminal_evidence",
    "test_kpi_003.test_kpi_t012_observer_mcp_read_only_and_least_privilege",
    "test_kpi_003.test_kpi_t020_pilot_reconciles_with_raw_evidence",
}

report = Path(sys.argv[1])
root = ET.parse(report).getroot()
cases = list(root.iter("testcase"))
failures = {
    f"{case.get('classname').split('.')[-1]}.{case.get('name')}"
    for case in cases
    if case.find("failure") is not None or case.find("error") is not None
}
skipped = sum(case.find("skipped") is not None for case in cases)
print(f"JUnit sha256: {hashlib.sha256(report.read_bytes()).hexdigest()}")
print(f"Total: {len(cases)}, passed: {len(cases) - skipped - len(failures)}, "
      f"skipped: {skipped}, failed/error: {len(failures)}")
for name in sorted(failures):
    print(f"FAILED {name}")
assert len(cases) >= 1400, "incomplete suite"
assert failures == EXPECTED, f"unexpected failures: {failures - EXPECTED}; absent baseline failures: {EXPECTED - failures}"
print("PASS: exactly the three previously recorded baseline failures; no additional failures")
