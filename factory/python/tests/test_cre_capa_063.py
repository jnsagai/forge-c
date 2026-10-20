"""CAPA-063 (h004): the stack bound of a HAL with an external time base (profile hal.time_base) is measured with a
reference leaf time base and the assumption is logged; a driver without a time base is measured as before."""
import subprocess
import sys

from forge_factory.common import REPO_ROOT


def test_capa063_time_base_charged_as_reference_leaf():
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tests/reliability/reproducers/rpr067_stack_external_time_base.py")],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0 and "SYMPTOM_ABSENT" in r.stdout, r.stdout + r.stderr
