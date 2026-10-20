"""CAPA-064 (TAA-RCC FND-04): the package's tool records are generated from the run's tool results and model profile;
an operation the run used is not listed as disabled."""
import subprocess
import sys

from forge_factory.common import REPO_ROOT


def test_capa064_tool_records_are_the_runs():
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tests/reliability/reproducers/rpr068_package_stale_tool_records.py")],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0 and "SYMPTOM_ABSENT" in r.stdout, r.stdout + r.stderr
