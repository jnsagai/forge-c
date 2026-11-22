"""T013/T014: neutral checklists are well-formed and cover every stage."""
from __future__ import annotations

import json
import re

import pytest

from conftest import REFS

CL = REFS / "checklists"
FILES = sorted(CL.glob("*.json"))
STAGES = json.loads((REFS / "stages.json").read_text())
STAGE_IDS = {s["id"] for s in STAGES["stages"]}
BANNED = re.compile(r"(?i)strada|omniverse|rm0486|fabro|/home/|\b100\.\d+\.\d+\.\d+")


@pytest.mark.parametrize("path", FILES, ids=[p.stem for p in FILES])
def test_checklist_structure(path):
    doc = json.loads(path.read_text())
    assert doc["id"] == path.stem and doc["phase"] in ("item", "set") and doc["_source"]
    assert set(doc["stages"]) <= STAGE_IDS
    ids = [i["id"] for i in doc["items"]]
    assert len(ids) == len(set(ids)) and ids
    for it in doc["items"]:
        assert re.fullmatch(r"[A-Z]{2,4}-[0-9]{2}", it["id"])
        assert it["default_severity"] in ("blocking", "major", "minor")
        assert isinstance(it["deterministic"], bool)
        assert len(it["pass_criterion"]) <= 400 and len(it["typical_defect"]) <= 200
        for ref in it.get("aspice_refs", []) + it.get("iso26262_refs", []):
            assert len(ref) <= 40
    assert not BANNED.search(path.read_text())


def test_every_stage_checklist_exists():
    for st in STAGES["stages"]:
        for cid in st["checklists"]:
            assert (CL / f"{cid}.json").is_file(), (st["id"], cid)


def test_requirement_checklists_complete():
    item = json.loads((CL / "requirements-item.json").read_text())
    sset = json.loads((CL / "requirements-set.json").read_text())
    assert [i["id"] for i in item["items"]] == [f"IQ-{n:02d}" for n in range(1, 13)]
    assert [i["id"] for i in sset["items"]] == [f"SQ-{n:02d}" for n in range(1, 11)]
