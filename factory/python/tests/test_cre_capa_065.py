"""CAPA-065 (rc1 0008a): reads of the write-only RM0486 set/clear registers return 0 in the RCC model; writes still
set/clear their target register."""
import subprocess
import sys

from forge_factory.common import REPO_ROOT


def test_capa065_setclear_reads_are_zero():
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tests/reliability/reproducers/rpr069_setclear_read_returns_target.py")],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "SYMPTOM_ABSENT" in r.stdout, r.stdout + r.stderr
