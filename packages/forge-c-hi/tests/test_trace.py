"""T024: bidirectional traceability, dangling, orphan, uncovered and suspect links, and the matrix."""
from __future__ import annotations

import copy
import json

from forge_hi import trace
from forge_hi.config import load_project
from hi_helpers import SWR_ITEMS, SYS_ITEMS, make_project, req, write, reqset


def codes(doc):
    return sorted({i["code"] for i in doc["issues"]})


def test_complete_chain_passes(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS)
    doc = trace.run(tmp_project, "sw-req")
    assert doc["verdict"] == "PASS", doc["issues"]
    links = json.loads((tmp_project / "hi/trace.json").read_text())["links"]
    assert {(l["from"], l["to"], l["type"]) for l in links} >= {
        ("STK-SUP-001", "SYS-SUP-001", "derives"),
        ("CON-SUP-001", "SYS-SUP-002", "derives"),
        ("SYS-SUP-002", "SWR-SUP-002", "derives"),
    }
    assert all(l["status"] == "valid" for l in links)
    assert (tmp_project / "hi/sw-req/gates/trace.json").is_file()


def test_orphan_software_requirement_fails(tmp_project):
    orphan = req("SWR-SUP-009", "The monitor shall log every task start within 1 ms.",
                 [{"kind": "document", "doc_id": "RM0486", "section": "1.2", "page": 3}])
    make_project(tmp_project, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS + [orphan])
    doc = trace.run(tmp_project, "sw-req")
    assert "TR-ORPHAN" in codes(doc)
    derived = dict(orphan, derived=True, rationale="Needed for timing analysis.", sources=[{"kind": "upstream", "id": "SYS-SUP-001"}])
    make_project(tmp_project, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS + [derived])
    assert "TR-ORPHAN" not in codes(trace.run(tmp_project, "sw-req"))


def test_uncovered_need_and_uncovered_system_requirement_fail(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS[:1])
    doc = trace.run(tmp_project, "sys-req")
    assert doc["verdict"] == "FAIL"
    assert any(i["code"] == "TR-UNCOVERED" and i["target_id"] == "STK-SUP-002" for i in doc["issues"])

    make_project(tmp_project, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS[:1])
    doc = trace.run(tmp_project, "sw-req")
    assert any(i["code"] == "TR-UNCOVERED" and i["target_id"] == "SYS-SUP-002" for i in doc["issues"])
    # a system requirement allocated to hardware only needs no software requirement
    hw = copy.deepcopy(SYS_ITEMS)
    hw[1]["attributes"] = {"allocation": ["hardware"]}
    make_project(tmp_project, sys_items=hw, swr_items=SWR_ITEMS[:1])
    assert trace.run(tmp_project, "sw-req")["verdict"] == "PASS"


def test_stage_scope_ignores_later_stages(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS[:1])
    assert trace.run(tmp_project, "sys-req")["verdict"] == "PASS"


def test_dangling_link_fails(tmp_project):
    bad = req("SWR-SUP-003", "The monitor shall flag a task within 2 cycles.", ["SYS-SUP-404"])
    make_project(tmp_project, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS + [bad])
    doc = trace.run(tmp_project, "sw-req")
    assert any(i["code"] == "TR-DANGLING" and i["target_id"] == "SWR-SUP-003" for i in doc["issues"])


def test_unknown_document_fails(tmp_project):
    cited = req("SWR-SUP-003", "The monitor shall flag a task within 2 cycles.",
                ["SYS-SUP-001", {"kind": "document", "doc_id": "RM9999", "section": "4.1", "page": 12}])
    make_project(tmp_project, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS + [cited])
    assert "TR-DOC-UNKNOWN" in codes(trace.run(tmp_project, "sw-req"))


def test_upstream_change_marks_links_suspect(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS)
    assert trace.run(tmp_project, "sw-req")["verdict"] == "PASS"
    assert trace.rebaseline(tmp_project, "sys-req") == 3
    assert trace.rebaseline(tmp_project, "sw-req") == 2
    assert trace.run(tmp_project, "sw-req")["verdict"] == "PASS"

    changed = copy.deepcopy(SYS_ITEMS)
    changed[0]["text"] = "The supervisor shall detect a missing alive indication within 30 ms."
    write(tmp_project / "hi/sys-req/requirements.json", reqset("sys-req", changed))
    doc = trace.run(tmp_project, "sw-req")
    assert doc["verdict"] == "FAIL"
    links = {(l["from"], l["to"]): l for l in json.loads((tmp_project / "hi/trace.json").read_text())["links"]}
    assert links[("STK-SUP-001", "SYS-SUP-001")]["status"] == "suspect"
    assert links[("SYS-SUP-001", "SWR-SUP-001")]["status"] == "suspect"
    assert "SYS-SUP-001 changed" in links[("SYS-SUP-001", "SWR-SUP-001")]["suspect_reason"]
    assert links[("SYS-SUP-002", "SWR-SUP-002")]["status"] == "valid"

    # re-accepting sys-req clears only the links into sys-req; the sw-req link waits for sw-req
    trace.rebaseline(tmp_project, "sys-req")
    doc = trace.run(tmp_project, "sw-req")
    assert [i["target_id"] for i in doc["issues"]] == ["SWR-SUP-001"]
    trace.rebaseline(tmp_project, "sw-req")
    assert trace.run(tmp_project, "sw-req")["verdict"] == "PASS"


def test_need_text_change_marks_link_suspect(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS)
    trace.rebaseline(tmp_project, "sys-req")
    p = tmp_project / "needs/stakeholder-needs.md"
    p.write_text(p.read_text().replace("stops.", "stops for 2 cycles."))
    doc = trace.run(tmp_project, "sys-req")
    assert [i["target_id"] for i in doc["issues"] if i["code"] == "TR-SUSPECT"] == ["SYS-SUP-001"]


def test_matrix_is_rendered(tmp_project):
    make_project(tmp_project, sys_items=SYS_ITEMS[:1])
    trace.run(tmp_project, "sys-req")
    md = (tmp_project / "hi/trace-matrix.md").read_text()
    assert "| STK-SUP-001 | SYS-SUP-001 | derives | valid |" in md
    assert "| STK-SUP-002 | **NOT COVERED** | | |" in md
    assert "## Issues" in md


def test_no_workproduct_is_not_run(tmp_project):
    make_project(tmp_project)
    assert trace.run(tmp_project)["verdict"] == "NOT_RUN"


def test_gate_result_validates_against_contract(tmp_project):
    from forge_hi.config import schema
    from forge_hi.jsonschema_lite import validate
    make_project(tmp_project, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS)
    trace.run(tmp_project, "sw-req")
    for f in ("hi/sw-req/gates/trace.json",):
        assert validate(json.loads((tmp_project / f).read_text()), schema("gate-result")) == []
    assert validate(json.loads((tmp_project / "hi/trace.json").read_text()), schema("trace")) == []


def drv_project(root):
    drv = req("DRV-IWDG-001", "The driver shall start the watchdog counter when started with a valid configuration.",
              [{"kind": "document", "doc_id": "RM0486", "section": "59.3", "page": 2981}])
    make_project(root, swr_items=[drv], stages=("sw-req",), input_class="reference_document")
    return root


def test_linked_driver_requirements_resolve_as_interfaces(tmp_path):
    drv_project(tmp_path / "iwdg-driver")
    app = tmp_path / "app"
    uses = req("SWR-SUP-003", "The supervisor shall start the independent watchdog during start-up.",
               ["SYS-SUP-001", "DRV-IWDG-001"])
    make_project(app, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS + [uses],
                 links=[{"project_path": "../iwdg-driver", "level": "driver_interface"}])
    doc = trace.run(app, "sw-req")
    assert doc["verdict"] == "PASS", doc["issues"]
    links = {(l["from"], l["to"]): l["type"] for l in json.loads((app / "hi/trace.json").read_text())["links"]}
    assert links[("DRV-IWDG-001", "SWR-SUP-003")] == "interfaces"
    assert "DRV-IWDG-001" in (app / "hi/trace-matrix.md").read_text()


def test_linked_project_missing_or_item_unknown_fails(tmp_path):
    app = tmp_path / "app"
    uses = req("SWR-SUP-003", "The supervisor shall start the independent watchdog during start-up.",
               ["SYS-SUP-001", "DRV-IWDG-009"])
    make_project(app, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS + [uses],
                 links=[{"project_path": "../iwdg-driver", "level": "driver_interface"}])
    assert {"TR-LINK-MISSING", "TR-DANGLING"} <= set(codes(trace.run(app, "sw-req")))
    drv_project(tmp_path / "iwdg-driver")
    assert codes(trace.run(app, "sw-req")) == ["TR-DANGLING"]


def test_linked_driver_change_makes_link_suspect(tmp_path):
    drv_root = drv_project(tmp_path / "iwdg-driver")
    app = tmp_path / "app"
    uses = req("SWR-SUP-003", "The supervisor shall start the independent watchdog during start-up.",
               ["SYS-SUP-001", "DRV-IWDG-001"])
    make_project(app, sys_items=SYS_ITEMS, swr_items=SWR_ITEMS + [uses],
                 links=[{"project_path": "../iwdg-driver", "level": "driver_interface"}])
    trace.rebaseline(app, "sw-req")
    doc = json.loads((drv_root / "hi/sw-req/requirements.json").read_text())
    doc["items"][0]["text"] = "The driver shall start the watchdog counter within 1 ms of the start call."
    write(drv_root / "hi/sw-req/requirements.json", doc)
    res = trace.run(app, "sw-req")
    assert [i["target_id"] for i in res["issues"] if i["code"] == "TR-SUSPECT"] == ["SWR-SUP-003"]
