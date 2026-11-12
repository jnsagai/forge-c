"""Feature 020 T019 (US2, FR-022, research R6): the feature 018 two-phase inspection on functional requirements.

Phase-1 packets of a functional-level order use the functional wording, the functional sources and the unchanged
IQ-01..IQ-12 criteria (the criteria file is unchanged: sha256 pinned from forge-c-020-base); the rework packet answers
in the functional requirement schema, is validated by the functional validators, and its splice changes only the
flagged requirement (every other requirement, checkpoint and markdown block byte-identical). Phase-1 packets of a
register-level order are the T007 golden (re-run here). Model calls are scripted."""
from __future__ import annotations

import copy
import hashlib
import json
import re

import pytest
import test_f020_identity as identity
from f020_swe1 import MODEL, answers, author, prepared
from forge_factory.common import REPO_ROOT
from forge_factory.lrtx import structured as S

test_register_level_phase1_packets_are_unchanged = identity.test_register_level_packets_and_author_gate_are_unchanged

CHECKLIST_SHA = "a5e46ac280ecc278a6f873191dc07fd1f2d18f3efc2ede3933847a70021ae8e9"  # forge-c-020-base, 303b46ea
REQS = "workproducts/SWE.1/software_requirements.md"


@pytest.fixture()
def done(tmp_path, monkeypatch):
    ws = prepared(tmp_path, monkeypatch)
    rep, _ = author(ws, monkeypatch)
    assert rep["status"] == "PASS", rep
    return ws


def judge(flag: dict[str, str], seen: list):
    """Inspector stand-in: a CORRECTABLE IQ-03 finding for the flagged SWR ids (by key), none for the others."""
    def call(p, **_k):
        seen.append(p)
        swr = p["output_schema"]["properties"]["requirement_id"]["enum"][0]
        key = p["task"].split(":")[3]  # iq:<task>:<key>:<sha12>
        fs = [{"quality_id": "IQ-03", "severity": "CORRECTABLE", "evidence": "the completion condition is vague",
               "required_action": flag[key], "input_uncertainty": False}] if key in flag else []
        doc = {"requirement_id": swr, "findings": fs}
        return {"doc": doc, "errors": S.validate(doc, p["output_schema"]), "usage": None, "wall_ms": 1.0,
                "finish_reason": "stop"}
    return call


def _blocks(md: str) -> dict[str, str]:
    return {m.group(1): m.group(0) for m in re.finditer(r"^- \*\*(SWR-\d{3})\*\*.*?(?=^- \*\*SWR-|^## |\Z)", md,
                                                        re.M | re.S)}


def test_phase1_packets_use_the_functional_wording_and_the_unchanged_criteria(done, monkeypatch):
    from forge_factory.lrtx import swe1_quality as Q

    assert hashlib.sha256((REPO_ROOT / Q.CHECKLIST).read_bytes()).hexdigest() == CHECKLIST_SHA
    seen: list = []
    monkeypatch.setattr(S, "call", judge({}, seen))
    assert Q.iq_inspect(done, MODEL)["status"] == "PASS"
    assert len(seen) == 20
    crit = [f"{i['id']} {i['property']}: {i['criterion']}" for i in Q.quality_checklist()["individual"]]
    for p in seen:
        assert p["role"] == "swe1-inspector" and p["criteria"] == crit
        assert p["output_schema"] == Q.verdict_schema(p["output_schema"]["properties"]["requirement_id"]["enum"][0])
        assert "functional-level" in p["instructions"] and "REGISTER.FIELD" not in p["instructions"]
        assert "source_page" not in p["instructions"]
        assert ".fabro/skills/swe1-author/references/functional-level.md" not in [s["path"] for s in p["sources"]]
    by_task = {":".join(p["task"].split(":")[1:3]): p for p in seen}
    bt = by_task["requirements:g_blocking_transfer"]
    assert [s["path"] for s in bt["sources"]] == ["inputs/index.md", "inputs/sections/RM9999/42.3.1_Transmitter.md",
                                                  "inputs/sections/RM9999/42.3.2_Receiver.md"]
    dc = by_task["requirements:design_constraints"]
    assert "inputs/hal_guideline.md" in [s["path"] for s in dc["sources"]]
    assert Q.iq_check(done) == 1  # nothing flagged: phase 1 done


def test_rework_splices_only_the_flagged_requirement(done, monkeypatch):
    from forge_factory.lrtx import swe1_quality as Q
    from forge_factory.lrtx import visit as V

    seen: list = []
    monkeypatch.setattr(S, "call", judge({"transmit_blocking": "state when the transmission is complete"}, seen))
    assert Q.iq_inspect(done, MODEL)["status"] == "PASS"
    assert Q.iq_check(done) == 0
    md0 = _blocks((done / REQS).read_text())
    attrs0 = {r["id"]: r for r in json.loads((done / "workproducts/SWE.1/requirement_attributes.json").read_text())
              ["requirements"]}
    ck = {t: V._ckpt(done, "SWE.1", t).read_bytes() for t in answers()}
    new = copy.deepcopy(answers()["requirements:g_blocking_transfer"]["requirements"][0])
    new["statement"] = ("When HAL_SER_Transmit is called with a valid handle, data and size, the SER HAL driver shall "
                        "send the data and return HAL_OK after the transmitter accepted the last data item.")
    packets: list = []

    def rework(p, **_k):
        packets.append(p)
        doc = {"requirement": new}
        return {"doc": copy.deepcopy(doc), "errors": S.validate(doc, p["output_schema"]), "usage": None,
                "wall_ms": 1.0, "finish_reason": "stop"}
    monkeypatch.setattr(S, "call", rework)
    rep = Q.iq_rework(done, MODEL)
    assert rep["status"] == "PASS" and "PHASE1_REWORKED:1" in rep["issues"], rep
    from forge_factory.governance import level as L
    from forge_factory.lrtx import swe1_functional as F

    assert packets[0]["output_schema"]["properties"]["requirement"] == F.requirement_schema(
        L.load_template("swe1-functional-v1"))
    assert "functional-level" in packets[0]["instructions"] and "REGISTER.FIELD" not in packets[0]["instructions"]
    md1 = _blocks((done / REQS).read_text())
    assert set(md1) == set(md0)
    assert [s for s in md0 if md0[s] != md1[s]] == ["SWR-004"] and new["statement"] in md1["SWR-004"]
    attrs1 = {r["id"]: r for r in json.loads((done / "workproducts/SWE.1/requirement_attributes.json").read_text())
              ["requirements"]}
    assert [s for s in attrs0 if attrs0[s] != attrs1[s]] == ["SWR-004"]
    assert [t for t in ck if V._ckpt(done, "SWE.1", t).read_bytes() != ck[t]] == ["requirements:g_blocking_transfer"]
    rows = [json.loads(x) for x in (done / ".forge-run/lrtx/SWE.1/phase1/reworks.jsonl").read_text().splitlines()]
    assert [r["status"] for r in rows] == ["CHANGED"]


def test_an_invalid_rework_is_refused_by_the_functional_validators(done, monkeypatch):
    from forge_factory.lrtx import swe1_quality as Q

    seen: list = []
    monkeypatch.setattr(S, "call", judge({"transmit_blocking": "name the data register"}, seen))
    assert Q.iq_inspect(done, MODEL)["status"] == "PASS"
    md0 = (done / REQS).read_text()
    bad = copy.deepcopy(answers()["requirements:g_blocking_transfer"]["requirements"][0])
    bad["statement"] = "When HAL_SER_Transmit is called, the SER HAL driver shall write each data item to SER_TDR."
    packets: list = []

    def rework(p, **_k):
        packets.append(p)
        doc = {"requirement": bad}
        return {"doc": copy.deepcopy(doc), "errors": S.validate(doc, p["output_schema"]), "usage": None,
                "wall_ms": 1.0, "finish_reason": "stop"}
    monkeypatch.setattr(S, "call", rework)
    Q.iq_rework(done, MODEL)
    assert (done / REQS).read_text() == md0
    rows = [json.loads(x) for x in (done / ".forge-run/lrtx/SWE.1/phase1/reworks.jsonl").read_text().splitlines()]
    assert rows[-1]["status"] == "INVALID"
    assert any("[transmit_blocking] LEVEL_REGISTER_TERM" in e for e in rows[-1]["errors"]), rows[-1]
    assert len(packets) > 1 and any("LEVEL_REGISTER_TERM" in f for f in packets[1]["findings"])
