"""Builders for small consumer projects used by the gate, CLI, MCP and conductor tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path

NEEDS = """# Needs

- **STK-SUP-001** The supervisor must notice when a task stops.
- **STK-SUP-002** The supervisor must notice late tasks.
"""

CONSTRAINTS = "| CON-SUP-001 | Target: a Cortex-M55 microcontroller. |\n"

PROV = {
    "role": "author",
    "skill": "hi-sys-req-author",
    "skill_version": "0.1.0",
    "harness": "fake",
    "model": None,
    "model_family": "fake-a",
    "input_hashes": {},
    "created_utc": "2026-11-22T12:00:00Z",
    "run_id": "r-test",
}


def req(rid: str, text: str, sources: list[str] | list[dict], **kw) -> dict:
    level = {"SYS": "system", "SWR": "software", "DRV": "driver_interface", "STK": "stakeholder"}[rid.split("-")[0]]
    srcs = [s if isinstance(s, dict) else {"kind": "upstream", "id": s} for s in sources]
    item = {
        "id": rid,
        "level": level,
        "text": text,
        "sources": srcs,
        "derived": False,
        "verification_method": "test",
        "status": "proposed",
    }
    item.update(kw)
    return item


SYS_ITEMS = [
    req("SYS-SUP-001", "The supervisor shall detect a missing alive indication of a supervised task within 20 ms.",
        ["STK-SUP-001"]),
    req("SYS-SUP-002", "The supervisor shall detect a supervised task that completes later than its configured deadline.",
        ["STK-SUP-002", "CON-SUP-001"]),
]

SWR_ITEMS = [
    req("SWR-SUP-001", "The alive monitor shall flag a task as failed when its alive counter is unchanged for 2 cycles.",
        ["SYS-SUP-001"]),
    req("SWR-SUP-002", "The deadline monitor shall flag a task as failed when its end checkpoint is later than 5 ms.",
        ["SYS-SUP-002"]),
]


def reqset(stage: str, items: list[dict]) -> dict:
    return {
        "schema": "forge-c-hi/requirement-set@1",
        "stage": stage,
        "baseline_id": f"{stage}-BL-1",
        "status": "draft",
        "provenance": copy.deepcopy(PROV),
        "items": copy.deepcopy(items),
        "open_points": [],
    }


def project_doc(level: str = "HI-2", profile: str = "generic", stages=("sys-req", "sw-req"), **kw) -> dict:
    doc = {
        "schema": "forge-c-hi/project@1",
        "project_id": "demo-proj",
        "profile": profile,
        "integrity_level": level,
        "input_class": "natural_language",
        "entry_stage": stages[0],
        "stages": list(stages),
        "inputs": [
            {"path": "needs/stakeholder-needs.md", "kind": "needs"},
            {"path": "needs/constraints.md", "kind": "constraints"},
        ],
        "roles": {
            "author": {"harness": "manual", "command": [], "model_family": "fake-a"},
            "inspector": {"harness": "manual", "command": [], "model_family": "fake-b", "read_only": True},
        },
    }
    doc.update(kw)
    return doc


def write(path: Path, doc) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n" if not isinstance(doc, str) else doc, encoding="utf-8")
    return path


def make_project(root: Path, *, sys_items=None, swr_items=None, **project_kw) -> Path:
    write(root / "needs" / "stakeholder-needs.md", NEEDS)
    write(root / "needs" / "constraints.md", CONSTRAINTS)
    write(root / ".hi" / "project.json", project_doc(**project_kw))
    if sys_items is not None:
        write(root / "hi" / "sys-req" / "requirements.json", reqset("sys-req", sys_items))
    if swr_items is not None:
        write(root / "hi" / "sw-req" / "requirements.json", reqset("sw-req", swr_items))
    return root
