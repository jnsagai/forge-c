"""CAPA-066 (h004/h005/rc1): the unit-test trace rule says @verifies takes USPEC ids only, and the gate finding for a
non-USPEC id names the rule."""
import subprocess
import sys

from forge_factory.common import REPO_ROOT


def test_capa066_rule_is_explicit():
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tests/reliability/reproducers/rpr070_verifies_rule_not_explicit.py")],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "SYMPTOM_ABSENT" in r.stdout, r.stdout + r.stderr
