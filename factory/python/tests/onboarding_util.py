"""Shared helpers of the feature 016 onboarding tests: real ST inputs (skipped when absent) and mutable copies of an
example whose relative inputs keep resolving."""
import json
import os
import shutil
from pathlib import Path

import pytest

from forge_factory.common import REPO_ROOT


def need_inputs():
    if not shutil.which("arm-none-eabi-gcc") or not os.path.isdir(os.path.expandvars("$FORGE_DATA_ROOT/inputs/st")):
        pytest.skip("ST inputs or the Arm GNU toolchain not on this host")


def example_copy(tmp_path: Path, name: str, mutate=None, replace_inputs: dict | None = None) -> Path:
    """A copy of examples/<name> under tmp_path/examples/<name>; inputs are symlinked unless replaced."""
    src = REPO_ROOT / "examples" / name
    ex = tmp_path / "examples" / name
    ex.mkdir(parents=True)
    spec = json.loads((src / "workorder.json").read_text())
    for item in spec.get("inputs") or []:
        p = (src / item["path"]).resolve()
        dst = ex / "inputs" / p.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        if replace_inputs and p.name in replace_inputs:
            dst.write_text(replace_inputs[p.name](p.read_text()))
        else:
            dst.symlink_to(p)
        item["path"] = f"inputs/{p.name}"
    if mutate:
        mutate(spec)
    (ex / "workorder.json").write_text(json.dumps(spec))
    return ex
