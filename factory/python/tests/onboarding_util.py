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


# feature 016 OB-T066..OB-T068: factory-HAL (HAL_ON_LL) work orders
HAND = {"wwdg": ("0016m-wwdg-hal", "0016c-st-cube-wwdg"), "crc": ("0014m-crc-hal", "0014l-st-cube-crc-swe1-gen")}
OWN = {"spi": "0011m-spi-hal", "tim": "0013m-tim-hal"}


def factory_hal_example(tmp_path, pid, mutate=None, ll_mutate=None, replace_inputs=None):
    """A HAL_ON_LL work order: the owner inputs of a hand-made factory HAL order (its scope and peripheral dropped) or
    of 0011m/0013m, with its LL lineage next to it (a symlink, or a mutated copy)."""
    if pid in HAND:
        hand, ll = HAND[pid]
        spec = json.loads((REPO_ROOT / "examples" / hand / "workorder.json").read_text())
        spec.pop("scope")
        spec.pop("peripheral", None)
        spec["onboarding"] = {"style": "HAL_ON_LL", "ll_example": ll}
        src, name = REPO_ROOT / "examples" / hand, f"{hand}-ob"
    else:
        src, name = REPO_ROOT / "examples" / OWN[pid], OWN[pid]
        spec = json.loads((src / "workorder.json").read_text())
        ll = spec["onboarding"]["ll_example"]
    ex = tmp_path / "examples" / name
    ex.mkdir(parents=True)
    for item in spec["inputs"]:
        p = (src / item["path"]).resolve()
        if replace_inputs and p.name in replace_inputs:
            dst = ex / "inputs" / p.name
            dst.parent.mkdir(exist_ok=True)
            dst.write_text(replace_inputs[p.name](p.read_text()))
            item["path"] = f"inputs/{p.name}"
        else:
            item["path"] = str(p)
    if mutate:
        mutate(spec)
    (ex / "workorder.json").write_text(json.dumps(spec))
    lx = tmp_path / "examples" / ll
    if ll_mutate:
        lx.mkdir()
        lspec = json.loads((REPO_ROOT / "examples" / ll / "workorder.json").read_text())
        for item in lspec["inputs"]:
            item["path"] = str((REPO_ROOT / "examples" / ll / item["path"]).resolve())
        ll_mutate(lspec)
        (lx / "workorder.json").write_text(json.dumps(lspec))
    else:
        lx.symlink_to(REPO_ROOT / "examples" / ll)
    return ex
