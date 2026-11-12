"""Feature 020 T017 (US2, FR-023, research R5): the ReqIF of a functional-level order carries the template attributes
and `traces-to` / `derived-from` relations to the input register's SPEC-OBJECTs; the ReqIF of a register-level order
is byte-identical to the base (golden sha256 of the same markdown and trace matrix computed on forge-c-020-base,
303b46ea, with its build_xml and its export())."""
from __future__ import annotations

import hashlib
import json
import re

import pytest
from f020_swe1 import author, prepared

REGISTER_MD = """# Software requirements

## SER_CR register requirements (RM9999 section 42.7.1)

- **SWR-001** When LL_SER_Enable is called, the SER LL driver shall set SER_CR.UE.
  - Source: RM9999 p.413
  - Verification: host unit test passes when SER_CR.UE is 1.
- **SWR-002** The SER LL driver shall occupy at most 4096 bytes of flash.
  - Source: work-order budget (owner development target)
  - Verification: SWE.6 Robot suite passes when the driver flash usage is at most 4096 bytes.
"""
REGISTER_CSV = ("requirement_id,test_id,test_file\nSWR-001,UT-001,software/tests/unit/test_ser.c\n"
                "SWR-002,SWR-002,software/tests/software/test_ser_requirements.robot\n")
GOLDEN_BUILD_XML = "8c19b1d4735a57ada950e83ca071bb433c1df7810e893f06ef5790ecc10fc38b"
ATTRIBUTES = ("Title", "Type", "Status", "ASIL", "CAL", "Precondition", "OriginGroup", "VerificationMethod",
              "TestLevel", "AllocatedInterface", "AllocatedOperation")


def test_register_level_reqif_is_byte_identical_to_the_base(tmp_path):
    from forge_factory.inspection.reqif_export import OUT, build_xml, export

    xml = build_xml(REGISTER_MD, REGISTER_CSV, "SWE.1 Software Requirements")
    assert hashlib.sha256(xml.encode()).hexdigest() == GOLDEN_BUILD_XML
    ws = tmp_path / "ws"
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "traceability").mkdir()
    (ws / ".forge-run").mkdir()
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL", "register_contract": "rc-v1"}))
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(REGISTER_MD)
    (ws / "traceability/requirements_to_tests.csv").write_text(REGISTER_CSV)
    assert export(ws)["verdict"] == "PASS"
    assert hashlib.sha256((ws / OUT).read_bytes()).hexdigest() == GOLDEN_BUILD_XML


@pytest.fixture()
def done(tmp_path, monkeypatch):
    ws = prepared(tmp_path, monkeypatch)
    rep, _ = author(ws, monkeypatch)
    assert rep["status"] == "PASS", rep
    return ws


def test_functional_reqif_has_attributes_inputs_and_link_relations(done):
    from forge_factory.inspection.reqif_export import OUT, export

    rq = export(done)
    assert rq["verdict"] == "PASS", rq["issues"]
    xml = (done / OUT).read_text()
    for name in ATTRIBUTES:
        assert f'LONG-NAME="{name}"' in xml, name
    attrs = json.loads((done / "workproducts/SWE.1/requirement_attributes.json").read_text())["requirements"]
    inv = json.loads((done / "inputs/governance-inventory.json").read_text())
    assert 'LONG-NAME="Input Document"' in xml
    for i in inv["inputs"]:
        assert f'LONG-NAME="{i["input_id"]}"' in xml
    assert 'LONG-NAME="traces-to"' in xml and 'LONG-NAME="derived-from"' in xml
    links = [(r["id"], ln["kind"]) for r in attrs for ln in r["links"]]
    rels = re.findall(r"<SPEC-RELATION [^>]*>.*?</SPEC-RELATION>", xml)
    trace_type = re.search(r'<SPEC-RELATION-TYPE IDENTIFIER="([^"]+)" [^>]*LONG-NAME="traces-to"', xml).group(1)
    derive_type = re.search(r'<SPEC-RELATION-TYPE IDENTIFIER="([^"]+)" [^>]*LONG-NAME="derived-from"', xml).group(1)
    assert sum(trace_type in r for r in rels) == sum(k == "trace" for _s, k in links)
    assert sum(derive_type in r for r in rels) == sum(k == "derive" for _s, k in links)
    assert 'THE-VALUE="awaiting_traceability"' in xml and 'THE-VALUE="not applicable until SWE.2"' in xml
    assert rq["spec_objects"] == len(attrs) + len(inv["inputs"]) + len({r["test_id"] for r in _csv(done)
                                                                        if r["test_id"]})


def _csv(ws):
    import csv
    import io

    return list(csv.DictReader(io.StringIO((ws / "traceability/requirements_to_tests.csv").read_text())))
