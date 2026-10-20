"""CAPA-060 (b006): host coverage of a delivery is reported over the delivered scope functions (whole-file figures kept
as context); greenfield coverage is unchanged."""
import subprocess
import sys

from forge_factory.common import REPO_ROOT


def test_capa060_delivery_coverage_names_the_scope():
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tests/reliability/reproducers/rpr064_delivery_coverage_whole_files.py")],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0 and "SYMPTOM_ABSENT" in r.stdout, r.stdout + r.stderr
