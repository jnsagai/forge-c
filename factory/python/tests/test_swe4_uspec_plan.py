"""Owner decision 2026-11-03 (V-model): SWE.1 allocates only the SWR -> SWE.6 qualification tests; SWE.4 derives one
test task per USPEC item of the frozen SWE.3 units and assigns the UT ids itself. A frozen older SWE.1 baseline with
UT rows is never reinterpreted: its rows are SUPERSEDED and SWE.4 numbers after them."""
from __future__ import annotations

import csv
import io
import json
import re

import pytest
from forge_factory.inspection import uspec_plan
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe4
from test_lrtx_swe1 import _scripted, pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import ws1  # noqa: F401 - fixture
from test_lrtx_swe3 import TOOLS, ws2  # noqa: F401 - fixture
from test_lrtx_swe4 import TESTS, ws3  # noqa: F401 - fixture

pytestmark = [pytestmark, pytest.mark.skipif(not TOOLS, reason="build tools not installed")]


def _rows(ws_):
    return list(csv.DictReader(io.StringIO((ws_ / "traceability/requirements_to_tests.csv").read_text())))


def _renumber(answers: dict, shift: int) -> dict:
    """The scripted test answers for UT ids shifted by `shift` (same oracle-based code, new SWE.4 ids)."""
    out = {}
    for k, v in answers.items():
        n = int(k.split("-")[-1]) + shift
        new = f"UT-{n:03d}"
        old = k.split(":", 1)[1]
        code = v["code"].replace(old, new).replace(old.replace("-", "_"), new.replace("-", "_"))
        out[f"test:{new}"] = {**v, "code": code}
    return out


def test_swe1_allocates_only_qualification_tests_and_swe4_plans_one_test_per_uspec(ws3):  # noqa: F811
    rows = _rows(ws3)
    assert rows and all(r["test_id"] == r["requirement_id"] and r["test_file"].endswith("_requirements.robot")
                        for r in rows)  # no UT id, no unit-test level decided at SWE.1
    assert (ws3 / uspec_plan.PLAN).is_file() and (ws3 / uspec_plan.PLAN_MD).is_file()  # written by the harness scaffold
    plan = uspec_plan.build(ws3)
    md = (ws3 / "workproducts/SWE.3/unit_specifications.md").read_text()
    uspecs = re.findall(r"\*\*(USPEC-LL-\d{2}-\d{2})\*\*", md)
    assert [t["uspec"] for t in plan["tasks"]] == uspecs  # every USPEC has its task by construction
    assert [t["ut"] for t in plan["tasks"]] == [f"UT-{i:03d}" for i in range(1, len(uspecs) + 1)]
    assert plan["swe1_trace"] == "qualification_only" and plan["superseded_swe1_unit_rows"] == []
    assert not any(r in t["swrs"] for t in plan["tasks"] for r in t["constraints_verified_at_swe6"])


def test_legacy_swe1_unit_rows_are_superseded_and_never_reinterpreted(ws3, monkeypatch):  # noqa: F811
    p = ws3 / "traceability/requirements_to_tests.csv"
    rows = _rows(ws3)
    legacy = ["requirement_id,test_id,test_file"] + [
        f"{r['requirement_id']},UT-{i:03d},software/tests/unit/test_iwdg.c" if i <= 3 else
        f"{r['requirement_id']},{r['test_id']},{r['test_file']}" for i, r in enumerate(rows, 1)]
    p.write_text("\n".join(legacy) + "\n")  # a frozen pre-2026-11-03 SWE.1 trace with three UT rows
    plan = uspec_plan.build(ws3)
    assert plan["swe1_trace"] == "legacy_unit_allocation" and plan["first_ut"] == 4
    assert [r["test_id"] for r in plan["superseded_swe1_unit_rows"]] == ["UT-001", "UT-002", "UT-003"]
    calls = []
    monkeypatch.setattr(S, "call", _scripted(_renumber(TESTS, 3), calls))
    rep = swe4.visit_tests(ws3, "m")
    assert rep["status"] == "PASS", rep
    text = (ws3 / "software/tests/unit/test_iwdg.cpp").read_text()
    assert "@test UT-004" in text and "UT_001" not in text and "UT-001" not in text  # no SWE.1 UT id is reused
    from forge_factory.lrtx import tools as T

    tr = T.call(ws3, "forge-evidence-mcp", "validate_trace", {}, "swe4-author", "SWE.4")
    assert tr["status"] == "PASS", tr["issues"]
    assert tr["metrics"]["superseded_swe1_unit_rows"] == 3 and tr["metrics"]["planned_unit_tests"] == len(plan["tasks"])
    from forge_factory.release.finalize import trace_check

    ok, issues = trace_check(ws3)
    assert ok, issues
    md = (ws3 / uspec_plan.PLAN_MD).read_text()
    assert "superseded" in md and "UT-004" in md


def test_a_planned_test_that_is_missing_is_named(ws3, monkeypatch):  # noqa: F811
    answers = dict(TESTS)
    monkeypatch.setattr(S, "call", _scripted(answers, []))
    assert swe4.visit_tests(ws3, "m")["status"] == "PASS"
    plan = json.loads((ws3 / uspec_plan.PLAN).read_text())
    plan["tasks"].append({**plan["tasks"][0], "ut": "UT-099"})
    (ws3 / uspec_plan.PLAN).write_text(json.dumps(plan))
    from forge_factory.inspection.swtrace import tagged_tests

    tagged = tagged_tests(sorted(ws3.glob("software/tests/unit/test_*.c*")), ws3)
    assert uspec_plan.missing_tests(ws3, tagged) == [
        f"UT:PLANNED_TEST_MISSING:UT-099 (plan: verifies {plan['tasks'][0]['uspec']})"]


def test_without_frozen_unit_specification_the_plan_is_refused(ws3):  # noqa: F811
    (ws3 / "workproducts/SWE.3/unit_specifications.md").unlink()
    with pytest.raises(uspec_plan.PlanError, match="SWE4_NO_FROZEN_UNIT_SPECIFICATION"):
        uspec_plan.build(ws3)


def test_work_orders_without_the_flag_keep_the_swe1_unit_allocation(ws3):  # noqa: F811
    m = json.loads((ws3 / ".forge-run/manifest.json").read_text())
    m.pop("unit_verification")
    (ws3 / ".forge-run/manifest.json").write_text(json.dumps(m))
    from forge_factory.lrtx import swe1

    assert swe1.group_schema(None, ws=ws3) is swe1.GROUP_SCHEMA  # verified_by still required there
    assert not swe4.uspec_mode(ws3)


def test_native_prompts_take_the_ut_ids_from_the_swe4_plan():
    from forge_factory.workflow import prompts as P

    old = dict(P.UNIT_VERIFICATION), dict(P.LAYER), dict(P.ISOLATION)
    try:
        for layer, iso in (("LL", False), ("HAL", True), ("HAL", False)):
            P.LAYER["layer"], P.ISOLATION["on"] = layer, iso
            P.UNIT_VERIFICATION["gtest"] = False
            legacy = P.author_prompt("SWE.1") + P.unit_test_author_prompt()
            P.UNIT_VERIFICATION["gtest"] = True
            new = P.author_prompt("SWE.1") + P.author_prompt("SWE.4") + P.unit_test_author_prompt()
            assert "test_id UT-001.." in legacy and "test_id UT-001.." not in new
            assert "Never write UT ids" in new and P.PLAN_MD in new
            assert "(the UT ids per SWR)" not in new
    finally:
        P.UNIT_VERIFICATION.update(old[0]), P.LAYER.update(old[1]), P.ISOLATION.update(old[2])
