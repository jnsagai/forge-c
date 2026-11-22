"""T058: later V-model workproducts (architecture, design, test specification, verification results) and their trace."""
from __future__ import annotations

import copy
import json

import pytest

from forge_hi import gates, trace
from forge_hi.config import schema
from forge_hi.jsonschema_lite import validate
from hi_helpers import PROV, SWR_ITEMS, SYS_ITEMS, make_project, write

ALL = ("sys-req", "sys-arch", "sw-req", "sw-arch", "sw-design", "unit-verif", "sw-integ", "sw-qual", "sys-integ",
       "sys-qual")


def up(*ids):
    return [{"kind": "upstream", "id": i} for i in ids]


def env(name, stage, items):
    return {"schema": f"forge-c-hi/{name}@1", "stage": stage, "baseline_id": "BL-1", "status": "draft",
            "provenance": copy.deepcopy(PROV), "items": items, "open_points": []}


SYE = [{"id": "SYE-SUP-001", "kind": "software", "name": "Supervisor software",
        "description": "Runs the supervision functions on the microcontroller.", "sources": up("SYS-SUP-001", "SYS-SUP-002"),
        "status": "proposed"}]
SWC = [{"id": "SWC-SUP-001", "kind": "component", "name": "Alive monitor",
        "description": "Counts alive indications per task and flags missing ones.", "sources": up("SWR-SUP-001"),
        "status": "proposed"},
       {"id": "SWC-SUP-002", "kind": "interface", "name": "Check-in API",
        "description": "Functions the tasks call to report alive and deadline checkpoints.", "sources": up("SWR-SUP-002"),
        "status": "proposed"}]
SWU = [{"id": "SWU-SUP-001", "name": "alive_monitor", "description": "Implements the alive counters and the check.",
        "sources": up("SWC-SUP-001"), "files": ["src/alive_monitor.c", "include/alive_monitor.h"], "status": "proposed"}]


def cases(prefix, *targets):
    return [{"id": f"{prefix}-SUP-{n:03d}", "title": f"Verify {t}", "objective": f"Show that {t} behaves as specified.",
             "method": "test", "steps": ["Run the scenario."], "expected": ["The observed result matches."],
             "sources": up(t), "status": "proposed"} for n, t in enumerate(targets, 1)]


def full_v(root):
    make_project(root, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS, stages=ALL)
    write(root / "hi/sys-arch/architecture.json", env("architecture", "sys-arch", SYE))
    write(root / "hi/sw-arch/architecture.json", env("architecture", "sw-arch", SWC))
    write(root / "hi/sw-design/design.json", env("design", "sw-design", SWU))
    write(root / "hi/unit-verif/test-spec.json", env("test-spec", "unit-verif", cases("UTC", "SWU-SUP-001")))
    write(root / "hi/sw-integ/test-spec.json", env("test-spec", "sw-integ", cases("ITC", "SWC-SUP-001", "SWC-SUP-002")))
    write(root / "hi/sw-qual/test-spec.json", env("test-spec", "sw-qual", cases("QTC", "SWR-SUP-001", "SWR-SUP-002")))
    write(root / "hi/sys-integ/test-spec.json", env("test-spec", "sys-integ", cases("SIT", "SYE-SUP-001")))
    write(root / "hi/sys-qual/test-spec.json", env("test-spec", "sys-qual", cases("SQT", "SYS-SUP-001", "SYS-SUP-002")))
    return root


@pytest.mark.parametrize("name,doc", [
    ("architecture", env("architecture", "sw-arch", SWC)),
    ("design", env("design", "sw-design", SWU)),
    ("test-spec", env("test-spec", "sw-qual", cases("QTC", "SWR-SUP-001"))),
    ("verification-result", {"schema": "forge-c-hi/verification-result@1", "stage": "unit-verif",
                             "tool": {"name": "forge-c-hi unit-test", "version": "0.1.0"}, "created_utc": "x",
                             "results": [{"test_id": "UTC-SUP-001", "verdict": "PASS"}]}),
])
def test_valid_and_invalid_fixture(name, doc):
    assert validate(doc, schema(name)) == []
    bad = copy.deepcopy(doc)
    if name == "verification-result":
        bad["results"][0]["verdict"] = "GREEN"
    elif name == "design":
        bad["items"][0]["files"] = ["/etc/passwd"]
    elif name == "test-spec":
        bad["items"][0]["expected"] = []
    else:
        bad["items"][0]["id"] = "ARCH-1"
    assert validate(bad, schema(name))


def test_full_v_traces(tmp_project):
    full_v(tmp_project)
    doc = trace.run(tmp_project, "sys-qual")
    assert doc["verdict"] == "PASS", doc["issues"]
    links = {(l["from"], l["to"]): l["type"] for l in json.loads((tmp_project / "hi/trace.json").read_text())["links"]}
    assert links[("SYS-SUP-001", "SYE-SUP-001")] == "allocates"
    assert links[("SWR-SUP-001", "SWC-SUP-001")] == "realises"
    assert links[("SWC-SUP-001", "SWU-SUP-001")] == "implements"
    assert links[("SWU-SUP-001", "UTC-SUP-001")] == "verifies"
    assert links[("SYS-SUP-002", "SQT-SUP-002")] == "verifies"
    for s in ALL:
        assert gates.validate_stage(tmp_project, s)["verdict"] == "PASS", s


@pytest.mark.parametrize("stage,file,keep", [
    ("sw-qual", "hi/sw-qual/test-spec.json", 1),       # SWR-SUP-002 has no qualification test
    ("sys-qual", "hi/sys-qual/test-spec.json", 1),
    ("sw-integ", "hi/sw-integ/test-spec.json", 1),
])
def test_unverified_counterpart_fails(tmp_project, stage, file, keep):
    full_v(tmp_project)
    doc = json.loads((tmp_project / file).read_text())
    doc["items"] = doc["items"][:keep]
    write(tmp_project / file, doc)
    res = trace.run(tmp_project, "sys-qual")
    assert any(i["code"] == "TR-UNCOVERED" and "verified by" in i["message"] for i in res["issues"]), res["issues"]


def test_interface_elements_need_no_unit_but_components_do(tmp_project):
    full_v(tmp_project)
    assert not [i for i in trace.run(tmp_project, "sys-qual")["issues"] if i["target_id"] == "SWC-SUP-002"]
    write(tmp_project / "hi/sw-design/design.json",
          env("design", "sw-design", [dict(SWU[0], sources=up("SWC-SUP-002"))]))
    res = trace.run(tmp_project, "sys-qual")
    assert any(i["target_id"] == "SWC-SUP-001" and i["code"] == "TR-UNCOVERED" for i in res["issues"])


def test_orphan_test_case_fails(tmp_project):
    full_v(tmp_project)
    doc = json.loads((tmp_project / "hi/sw-qual/test-spec.json").read_text())
    doc["items"].append(dict(doc["items"][0], id="QTC-SUP-009",
                             sources=[{"kind": "document", "doc_id": "X", "section": "1", "page": 1}]))
    write(tmp_project / "hi/sw-qual/test-spec.json", doc)
    assert any(i["code"] == "TR-ORPHAN" for i in trace.run(tmp_project, "sys-qual")["issues"])
