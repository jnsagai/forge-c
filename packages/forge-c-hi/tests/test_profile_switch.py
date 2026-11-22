"""T054: switching the standard profile or level changes configuration only, never the skills."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys

import pytest

from conftest import SCRIPTS, SKILLS
from forge_hi import seal
from hi_helpers import SWR_ITEMS, SYS_ITEMS, make_project, write
from test_seal import accept

HI = SCRIPTS / "hi.py"


def tree_hash(d):
    h = hashlib.sha256()
    for p in sorted(d.rglob("*")):
        if p.is_file() and "__pycache__" not in p.parts:
            h.update(p.relative_to(d).as_posix().encode() + b"\0" + p.read_bytes())
    return h.hexdigest()


def set_profile(root, profile, level):
    proj = json.loads((root / ".hi/project.json").read_text())
    proj.update(profile=profile, integrity_level=level)
    write(root / ".hi/project.json", proj)


@pytest.mark.parametrize("profile,level,name,stage_name", [
    ("generic", "HI-2", "HI-2", "Software requirements"),
    ("iso26262", "HI-2", "ASIL B", "Software safety requirements"),
    ("iec61508", "HI-2", "SIL 2", "Software safety requirements specification"),
    ("aspice40", "HI-1", "process HI-1", "SWE.1 Software Requirements Analysis"),
])
def test_same_workproducts_under_each_profile(tmp_project, profile, level, name, stage_name):
    before = tree_hash(SKILLS)
    make_project(tmp_project, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS)
    set_profile(tmp_project, profile, level)
    accept(tmp_project, "sys-req")
    accept(tmp_project, "sw-req")
    r = subprocess.run([sys.executable, str(HI), "gate", "sw-req"], cwd=tmp_project, capture_output=True, text=True)
    gates = json.loads(r.stdout)["gates"]
    from forge_hi.config import effective_rigor, load_project, stages
    rigor = effective_rigor(load_project(tmp_project))
    assert set(gates) == ({g for g in stages()["sw-req"]["gates"] if g in rigor["required_gates"]}
                          | ({"independence"} if "independence" in rigor["required_gates"] else set()))
    res = seal.seal(tmp_project)
    pkg = tmp_project / res["package"]
    m = json.loads((pkg / "manifest.json").read_text())
    assert m["profile"] == profile and m["integrity_level"] == level and m["level_name"] == name
    gates_md = (pkg / "gates.md").read_text()
    assert stage_name in gates_md and (name in gates_md)
    assert stage_name in (pkg / "findings.md").read_text()
    assert tree_hash(SKILLS) == before


def test_unmapped_level_is_refused(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS)
    set_profile(tmp_project, "iec61508", "HI-0")
    r = subprocess.run([sys.executable, str(HI), "gate", "sys-req"], cwd=tmp_project, capture_output=True, text=True)
    assert r.returncode == 2 and "not defined by profile 'iec61508'" in json.loads(r.stdout)["error"]


def test_level_changes_required_gates_not_skills(tmp_project):
    before = tree_hash(SKILLS)
    make_project(tmp_project, sys_items=SYS_ITEMS)
    seen = {}
    for level in ("HI-0", "HI-1", "HI-3"):
        set_profile(tmp_project, "iso26262", level)
        r = subprocess.run([sys.executable, str(HI), "gate", "sys-req"], cwd=tmp_project, capture_output=True, text=True)
        seen[level] = set(json.loads(r.stdout)["gates"])
    assert seen["HI-0"] < seen["HI-1"] <= seen["HI-3"] and "independence" in seen["HI-3"]
    assert tree_hash(SKILLS) == before
