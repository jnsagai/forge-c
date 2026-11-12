"""Feature 020 T016 (US2, FR-014..FR-016, FR-023, research R5): assembly of the functional SWE.1 work products.

`workproducts/SWE.1/software_requirements.md` keeps the `**SWR-NNN**` line followed by `Source:` (the link locators)
and `Verification:` (method, test level and pass criterion), then the template attributes as further lines;
`requirement_attributes.json` carries every attribute (author-written + the lane's fixed values) and validates
against contracts/functional-requirement.schema.json; `traceability/requirements_to_tests.csv` and
`.forge-run/lrtx/SWE.1/assembly.json` keep the shapes the existing readers use (swe1_quality, review, swtrace,
register_contract, EARS, ReqIF). The share of requirements awaiting traceability is reported (FR-016)."""
from __future__ import annotations

import csv
import io
import json
import re

import jsonschema
import pytest
from f020_swe1 import TASKS, answers, author, prepared
from forge_factory.common import REPO_ROOT

CONTRACT = json.loads((REPO_ROOT / "specs/020-usart-benchmark-pilot/contracts/functional-requirement.schema.json")
                      .read_text())
REQS = "workproducts/SWE.1/software_requirements.md"
ATTRS = "workproducts/SWE.1/requirement_attributes.json"
FIXED = {"status": "draft", "asil": "QM", "cal": "0", "allocated_interface": "not applicable until SWE.2",
         "allocated_operation": "not applicable until SWE.2"}
LINES = ["Source:", "Verification:", "Title:", "Type:", "Status:", "ASIL:", "CAL:", "Precondition:", "Origin group:",
         "Links:", "Use cases:", "Verification method:", "Test level:", "Allocated interface:", "Allocated operation:"]


@pytest.fixture()
def done(tmp_path, monkeypatch):
    ws = prepared(tmp_path, monkeypatch)
    rep, _ = author(ws, monkeypatch)
    assert rep["status"] == "PASS", rep
    return ws


def _blocks(md: str) -> dict[str, list[str]]:
    out, cur = {}, None
    for line in md.splitlines():
        m = re.match(r"^- \*\*(SWR-\d{3})\*\* (.+)$", line)
        if m:
            cur = m.group(1)
            out[cur] = [m.group(2)]
        elif cur and line.startswith("  - "):
            out[cur].append(line[4:])
        else:
            cur = None
    return out


def test_markdown_keeps_the_three_leading_lines_then_the_attributes(done):
    md = (done / REQS).read_text()
    blocks = _blocks(md)
    n = sum(len(a["requirements"]) for a in answers().values())
    assert list(blocks) == [f"SWR-{i:03d}" for i in range(1, n + 1)]
    for swr, b in blocks.items():
        assert [x.split(":", 1)[0] + ":" for x in b[1:]] == LINES, (swr, b)
    first = blocks["SWR-001"]
    assert first[0] == answers()["requirements:g_initialisation"]["requirements"][0]["statement"]
    assert first[1] == "Source: IN-02 RM9999-rev2-ch42-ser.md 42.1"
    assert first[2].startswith("Verification: test (component); passes when ")
    assert "Status: draft" in first and "ASIL: QM" in first and "CAL: 0" in first
    assert "Links: trace IN-02 42.1" in first and "Use cases: UC-01" in first
    awaiting = blocks["SWR-003"]
    assert awaiting[1] == "Source: awaiting traceability (no input states it yet)" and "Links: none" in awaiting
    derived = blocks["SWR-002"]
    assert derived[derived.index(next(x for x in derived if x.startswith("Links:")))].startswith(
        "Links: derive IN-02 42.1 (rationale: ")
    assert "Awaiting traceability: 1 of 20 requirements (5.0%)." in md
    assert "## Not delivered" in md and "separate configuration getters" in md
    assert "HAL_SER_EnableLoop" in md  # delivered, out of scope: listed, no requirement


def test_attributes_file_is_complete_and_contract_valid(done):
    doc = json.loads((done / ATTRS).read_text())
    assert doc["schema"] == "forge-c/swe1-requirement-attributes/1" and doc["template"] == "swe1-functional-v1"
    pkg = json.loads((done / "workproducts/SWE.1/governance/governance-package.json").read_text())
    assert doc["package_version"] == pkg["package_version"]
    v = jsonschema.Draft202012Validator(CONTRACT)
    for r in doc["requirements"]:
        own = {k: x for k, x in r.items() if k not in ("id", "task", *FIXED)}
        v.validate(own)
        assert {k: r[k] for k in FIXED} == FIXED
    assert [r["id"] for r in doc["requirements"]][:2] == ["SWR-001", "SWR-002"]
    assert {r["task"] for r in doc["requirements"]} == set(TASKS)


def test_trace_matrix_and_assembly_map_keep_their_shapes(done):
    from forge_factory.lrtx import swe1_quality as Q

    rows = list(csv.DictReader(io.StringIO((done / "traceability/requirements_to_tests.csv").read_text())))
    assert [r["requirement_id"] for r in rows] == [f"SWR-{i:03d}" for i in range(1, 21)]
    by = {r["requirement_id"]: r for r in rows}
    assert by["SWR-001"]["test_id"] == "SWR-001" and by["SWR-001"]["test_file"].startswith("software/tests/")
    assert by["SWR-019"]["test_id"] == "" and by["SWR-019"]["test_file"] == "inspection"  # a design constraint
    amap = json.loads((done / ".forge-run/lrtx/SWE.1/assembly.json").read_text())
    assert amap["schema"] == "forge-c/lrtx-swe1-assembly/1" and amap["level"] == "functional"
    assert amap["swr"]["SWR-001"] == {"task": "requirements:g_initialisation", "key": "init_applies_settings"}
    refs = Q.requirements(done)
    assert len(refs) == 20 and not any(r["generated"] for r in refs)
    assert refs[0]["obj"] == answers()["requirements:g_initialisation"]["requirements"][0]


def test_existing_parsers_read_the_new_file(done):
    from forge_factory.assurance import register_contract as RC
    from forge_factory.inspection import swtrace
    from forge_factory.inspection.ears import check_document
    from forge_factory.inspection.reqif_export import export
    from forge_factory.lrtx import review as R

    md = (done / REQS).read_text()
    names = set(json.loads((done / "configuration/system_names.json").read_text()))
    ears = check_document(md, names)
    assert ears["requirements"] == 20 and [f for f in ears["major_findings"] + ears["minor_findings"]
                                           if "SYSTEM_NAME_HINT" not in f] == []
    assert len(swtrace.requirement_ids(done)) == 20 and swtrace.swr_texts(done)["SWR-001"].startswith("When HAL_SER")
    assert len(RC.SWR_LINE.findall(md)) == 20
    assert R.fact_conflicts(done, "SWE.1", "SWE1-01", []) == []
    rq = export(done)
    assert rq["verdict"] == "PASS", rq["issues"]
    assert (done / "safety/software_safety_requirements.md").is_file()
