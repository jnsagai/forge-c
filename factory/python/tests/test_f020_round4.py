"""Feature 020 round 4 (owner-approved recommendation 2026-11-14, after the UART L50B benchmark comparison): template
v3 = v2 plus the granularity rule (one requirement per service behaviour, its variants merged; one design constraint
per guideline part) and D41 (HAL-only behaviour traces to the HAL driver guideline, not awaiting traceability). v2
orders keep the v2 rules; the UART module runs again on v3 after TIM's SWE.1, carrying what L50B validated."""
from __future__ import annotations

import copy
import json

import pytest
from f020_fixtures import ser_spec
from f020_swe1 import prepared
from forge_factory.common import REPO_ROOT
from test_f020_template_v2 import answers_v2

V3 = "swe1-functional-v3"
GROUP = "requirements:g_blocking_transfer"


@pytest.fixture()
def ws3(tmp_path, monkeypatch):
    spec = ser_spec()
    spec["swe1"] = {"level": "functional", "template": V3}
    return prepared(tmp_path, monkeypatch, spec=spec, wo="WO-F020-V3")


@pytest.fixture()
def ws2(tmp_path, monkeypatch):
    spec = ser_spec()
    spec["swe1"] = {"level": "functional", "template": "swe1-functional-v2"}
    return prepared(tmp_path / "v2", monkeypatch, spec=spec, wo="WO-F020-V2B")


def _task(ws, tid):
    from forge_factory.lrtx import swe1_functional as F

    return {t["id"]: t for t in F.plan(ws)}[tid]


def test_v3_is_v2_plus_the_round4_rules():
    from forge_factory.governance import level as L

    v2, v3 = L.load_template("swe1-functional-v2"), L.load_template(V3)
    assert v3["attributes"] == v2["attributes"] and v3["enums"] == v2["enums"]
    assert v3["rules"]["design_constraints_per_part"] == 1 and v2["rules"]["design_constraints_per_part"] == 3
    assert v3["rules"]["functional_requirements_per_operation"] == 2
    assert v3["rules"]["hal_behaviour_traces_to_guideline"] is True
    assert "functional_requirements_per_operation" not in v2["rules"]


def _hal_awaiting(a):
    r = copy.deepcopy(a["requirements"][0])
    r.update(key="hal_state_report", origin_group="awaiting_traceability", links=[], use_cases=[])
    return r


def test_hal_only_behaviour_awaiting_traceability_is_sent_to_the_guideline(ws3, ws2):
    from forge_factory.lrtx import swe1_functional as F

    for ws, expect in ((ws3, True), (ws2, False)):
        a = copy.deepcopy(answers_v2(ws)[GROUP])
        t = _task(ws, GROUP)
        if "awaiting_traceability" not in (t.get("origins") or ["awaiting_traceability"]):
            pytest.skip("the fixture group may not write awaiting_traceability")
        hal = [f for f in t.get("functions") or [] if f.startswith("HAL_")]
        r = _hal_awaiting(a)
        r["operations"] = hal[:1]
        a["requirements"].append(r)
        errs = F.validate_task(ws, a, t)
        hit = [e for e in errs if e.startswith("[hal_state_report] HAL_GUIDELINE_TRACE")]
        assert bool(hit) is expect, errs
        if expect:
            assert F.context(ws)["guideline"] in hit[0]


def test_a_service_behaviour_split_into_variants_is_merged(ws3, ws2):
    from forge_factory.lrtx import swe1_functional as F

    for ws, expect in ((ws3, True), (ws2, False)):
        a = copy.deepcopy(answers_v2(ws)[GROUP])
        t = _task(ws, GROUP)
        op = (t.get("functions") or [])[0]
        base = next(r for r in a["requirements"] if r["type"] == "functional")
        for n in range(3):
            r = copy.deepcopy(base)
            r.update(key=f"variant_{n}", operations=[op],
                     statement=base["statement"].rstrip(".") + f" for variant {n}.")
            a["requirements"].append(r)
        errs = F.validate_task(ws, a, t)
        hit = [e for e in errs if e.startswith(f"[{GROUP}] GRANULARITY")]
        assert bool(hit) is expect, errs
        if expect:
            assert op in hit[0] and "variant_2" in hit[0]


def test_v3_packets_carry_the_round4_guidance_and_v2_packets_do_not(ws3, ws2):
    from forge_factory.lrtx import swe1_functional as F

    for ws, expect in ((ws3, True), (ws2, False)):
        p = F.task_packet(ws, _task(ws, GROUP), "m")
        assert (F.GRANULARITY_RULE in p["instructions"]) is expect
        assert (F.GUIDELINE_TRACE_RULE in p["instructions"]) is expect


def test_the_uart_round4_order_runs_after_tim_on_v3_and_carries_l50b():
    from forge_factory.afo import owner_supervised_development as D

    w = json.loads((REPO_ROOT / "examples/0012v-st-cube-uart-module-r4/workorder.json").read_text())
    base = json.loads((REPO_ROOT / "examples/0012u-st-cube-uart-module/workorder.json").read_text())
    assert w["swe1"]["template"] == V3 and w["swe1"]["carry_from"][0] == "WO-F014-SWE1-UARTM-20261113-L50B"
    assert {k: v for k, v in w.items() if k != "swe1"} == {k: v for k, v in base.items() if k != "swe1"}
    assert D.PILOTS["uart-module-r4"] == ["SWE.1"] and D.PILOT_AFTER["uart-module-r4"] == "tim-module"
    camp = D.derived_campaign() if callable(getattr(D, "derived_campaign", None)) else None
    if camp:
        e = next(x for x in camp["lineages"] if x["id"] == "uart-module-r4")
        assert e["after"] == {"lineage": "tim-module", "phase": "SWE.1", "verdict": "PASS"}
