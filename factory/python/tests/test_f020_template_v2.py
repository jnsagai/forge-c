"""Feature 020 round 2 (owner 2026-11-12: "after UART finish, run the benchmark to compare, make the fixes if needed and
run again"; "in the new runs, preserve what is already good compared to the benchmark").

Template swe1-functional-v2 = v1 + the fixes of the first pilot round, selected per order (v1 unchanged):
- D31 design constraints: one per topic that shapes the module's API or behaviour, at most N per guideline part, no use
  cases (both models wrote ~40% design constraints one per guideline rule, benchmark 5 of 56);
- D32 allocation: an `operations` attribute (delivered public functions); assembly derives the allocated interface and
  operation from it (benchmark ~85% allocated at SWE.1, pilot 0%);
- D33 preconditions: every functional requirement states one (local 38%, cloud 89%).
Scripted answers only (never a real model)."""
from __future__ import annotations

import copy
import json
import re

import pytest
from f020_fixtures import ser_spec
from f020_swe1 import MODEL, TASKS, answers, prepared

V2 = "swe1-functional-v2"
PRE = "the SER handle is initialised and no transfer of the handle is ongoing"


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    spec = ser_spec()
    spec["swe1"] = {"level": "functional", "template": V2}
    return prepared(tmp_path, monkeypatch, spec=spec, wo="WO-F020-V2")


def answers_v2(ws) -> dict:
    """The v1 answers made v2-valid: preconditions on functional requirements, operations named in the statement."""
    from forge_factory.lrtx import swe1_functional as F

    plan = {t["id"]: t for t in F.plan(ws)}
    inscope = sorted({f for t in plan.values() for f in t.get("functions") or []}, key=len, reverse=True)
    out = copy.deepcopy(answers())
    for tid, a in out.items():
        for r in a["requirements"]:
            if r["type"] == "design_constraint":
                r["operations"] = []
                continue
            r["precondition"] = PRE
            pool = plan[tid].get("functions") or inscope
            named = [f for f in pool if re.search(rf"\b{re.escape(f)}\b", r["statement"])]
            r["operations"] = named[:2] or [pool[0]]
    return out


def _task(ws, tid):
    from forge_factory.lrtx import swe1_functional as F

    return {t["id"]: t for t in F.plan(ws)}[tid]


def test_v2_is_loaded_by_id_and_v1_is_unchanged(ws):
    from forge_factory.governance import level as L
    from forge_factory.lrtx import swe1_functional as F

    v1, v2 = L.load_template("swe1-functional-v1"), L.load_template(V2)
    assert v1["template_id"] == "swe1-functional-v1" and "operations" not in v1["attributes"]
    assert v2["template_id"] == V2 and "operations" in v2["attributes"]
    assert "allocated_interface" in v1["fixed"] and "allocated_interface" not in v2["fixed"]
    assert F.requirement_schema(v2)["properties"]["operations"]["type"] == "array"
    assert "operations" in F.requirement_schema(v2)["required"]
    with pytest.raises(L.LevelRefused):
        L.load_template("swe1-functional-v9")


def test_valid_v2_answers_pass_every_task(ws):
    from forge_factory.lrtx import swe1_functional as F

    a = answers_v2(ws)
    assert [t["id"] for t in F.plan(ws)] == TASKS
    for tid in TASKS:
        assert F.validate_task(ws, a[tid], _task(ws, tid)) == [], tid


CASES = [
    ("requirements:g_blocking_transfer", lambda r: r.update(precondition="none"), "PRECONDITION_MISSING"),
    ("requirements:g_blocking_transfer", lambda r: r.update(precondition="N/A"), "PRECONDITION_MISSING"),
    ("requirements:g_blocking_transfer", lambda r: r.update(operations=[]), "OPERATION_MISSING"),
    ("requirements:g_blocking_transfer", lambda r: r.update(operations=["HAL_SER_EnableLoop"]), "OPERATION_UNKNOWN"),
    ("requirements:g_blocking_transfer", lambda r: r.update(operations=["HAL_SER_Nope"]), "OPERATION_UNKNOWN"),
    ("requirements:design_constraints", lambda r: r.update(use_cases=["UC-01"]), "DESIGN_CONSTRAINT_USE_CASES"),
    ("requirements:design_constraints", lambda r: r.update(operations=["HAL_SER_Init"]),
     "DESIGN_CONSTRAINT_OPERATIONS"),
]


@pytest.mark.parametrize("tid, mutate, rule", CASES, ids=[c[2] + f"-{i}" for i, c in enumerate(CASES)])
def test_each_v2_rule_is_rejected_with_key_and_rule(ws, tid, mutate, rule):
    from forge_factory.lrtx import swe1_functional as F

    a = answers_v2(ws)[tid]
    mutate(a["requirements"][0])
    key = a["requirements"][0]["key"]
    errs = F.validate_task(ws, a, _task(ws, tid))
    assert any(e.startswith(f"[{key}] {rule}") for e in errs), errs


def test_a_design_part_with_more_constraints_than_the_cap_is_rejected(ws):
    from forge_factory.lrtx import swe1_functional as F

    tid = "requirements:design_constraints"
    a = answers_v2(ws)[tid]
    base = a["requirements"][0]
    for n in range(2):  # 2 + 2 = 4 > cap 3
        extra = copy.deepcopy(base)
        extra["key"], extra["statement"] = f"extra_{n}", f"The SER HAL driver shall keep rule {n} of the guideline."
        a["requirements"].append(extra)
    errs = F.validate_task(ws, a, _task(ws, tid))
    assert any(e.startswith(f"[{tid}] DESIGN_CONSTRAINT_LIMIT") for e in errs), errs


def test_v1_orders_keep_the_v1_rules(tmp_path, monkeypatch):
    """Preserve what is good: a v1 order still accepts 'none' preconditions and no operations attribute."""
    from forge_factory.lrtx import swe1_functional as F

    w = prepared(tmp_path, monkeypatch)
    for tid in TASKS:
        assert F.validate_task(w, answers()[tid], _task(w, tid)) == [], tid
    d = F.task_packet(w, _task(w, "requirements:design_constraints"), MODEL)
    assert "one requirement per applicable rule" in d["instructions"]


def test_v2_packets_ask_for_topics_preconditions_and_operations(ws):
    from forge_factory.lrtx import swe1_functional as F

    d = F.task_packet(ws, _task(ws, "requirements:design_constraints"), MODEL)
    assert "one requirement per applicable rule" not in d["instructions"]
    assert "at most 3" in d["instructions"] and "per topic" in d["instructions"]
    assert "SWE.3" in d["instructions"]  # general coding rules are checked by the SWE.3 guideline checklist
    g = F.task_packet(ws, _task(ws, "requirements:g_blocking_transfer"), MODEL)
    assert "operations" in g["instructions"] and "'none' only for a design constraint" in g["instructions"]
    assert g["output_schema"]["properties"]["requirements"]["items"]["properties"]["operations"]["type"] == "array"


def _assembled(ws, monkeypatch):
    from f020_swe1 import author

    rep, _calls = author(ws, monkeypatch, answers_v2(ws))
    assert rep["status"] == "PASS", rep
    return json.loads((ws / "workproducts/SWE.1/requirement_attributes.json").read_text())


def test_assembly_derives_the_allocation_from_operations(ws, monkeypatch):
    from forge_factory.governance import inventory as GI

    doc = _assembled(ws, monkeypatch)
    assert doc["template"] == V2
    comp = {a["function"]: a["component"] for a in GI.load(ws)["api"]}
    for r in doc["requirements"]:
        if r["type"] == "design_constraint":
            assert r["allocated_interface"] == r["allocated_operation"] == "not allocated (design constraint)"
        else:
            assert r["allocated_operation"] == ", ".join(r["operations"])
            assert r["allocated_interface"] == ", ".join(sorted({comp[o] for o in r["operations"]}))
    md = (ws / "workproducts/SWE.1/software_requirements.md").read_text()
    r0 = doc["requirements"][0]
    assert f"  - Allocated operation: {r0['allocated_operation']}" in md
    assert f"  - Operations: {', '.join(r0['operations'])}" in md


def test_the_gate_accepts_v2_and_catches_a_tampered_allocation_or_cap(ws, monkeypatch):
    from forge_factory.assurance import swe1_functional_checks as SA

    doc = _assembled(ws, monkeypatch)
    assert SA.findings(ws) == []
    p = ws / "workproducts/SWE.1/requirement_attributes.json"
    bad = copy.deepcopy(doc)
    bad["requirements"][0]["allocated_operation"] = "HAL_SER_Other"
    p.write_text(json.dumps(bad))
    assert any("ALLOCATION_MISMATCH" in f for f in SA.findings(ws))
    bad = copy.deepcopy(doc)
    dcs = [r for r in bad["requirements"] if r["task"] == "requirements:design_constraints"]
    md = (ws / "workproducts/SWE.1/software_requirements.md").read_text()
    for n in range(2):
        extra = {**copy.deepcopy(dcs[0]), "id": f"SWR-{len(bad['requirements']) + 1:03d}", "key": f"extra_{n}",
                 "statement": f"The SER HAL driver shall keep rule {n} of the guideline."}
        bad["requirements"].append(extra)
        md += f"\n- **{extra['id']}** {extra['statement']}\n"
    p.write_text(json.dumps(bad))
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(md)
    assert any("DESIGN_CONSTRAINT_LIMIT" in f for f in SA.findings(ws))
