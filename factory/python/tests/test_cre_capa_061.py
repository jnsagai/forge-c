"""CAPA-061 (b007 DEF-004/005): the Robot driver measurements build a header-only delivery through its scope wrappers
(vendor flags included); a build of nothing is a failure, never a 0-byte PASS of a flash, RAM or stack budget."""
import json
import subprocess
import sys

import pytest
from forge_factory.common import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "factory/sim/stm32n6"))


def test_capa061_header_only_delivery_is_measured():
    r = subprocess.run([sys.executable, str(REPO_ROOT / "tests/reliability/reproducers/rpr065_robot_measures_no_delivered_code.py")],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0 and "SYMPTOM_ABSENT" in r.stdout, r.stdout + r.stderr


def test_capa061_nothing_to_measure_fails(tmp_path):
    from ForgeTarget import ForgeTarget

    (tmp_path / ".forge-run").mkdir()
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL"}))
    with pytest.raises(AssertionError, match="no driver unit to measure"):
        ForgeTarget(str(tmp_path)).driver_flash_size_should_be_at_most(4096)
