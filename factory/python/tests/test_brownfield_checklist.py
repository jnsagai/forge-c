"""OD-2026-10-20-02: the v0.4-brownfield SWE.3 checklist - selected only for delivery work orders, SWE3-07..09 decided
on the delivered code (recorded findings in FROZEN / vendor style), CMSIS register definitions checked by
static-assertion probes against the RM0486 sections."""
import json

import pytest
from forge_factory.brownfield import checks as K
from forge_factory.brownfield.gates import code_checks
from forge_factory.inspection.engine import PHASES, Store, load_checklist
from forge_factory.workflow import prompts
from test_brownfield_pilot import _contract, ws  # noqa: F401 - pytest fixture
from test_brownfield_pilot import pytestmark as pilot_mark

DELIVERED = {"SWE3-07": "delivered_guideline", "SWE3-08": "delivered_register_definitions",
             "SWE3-09": "delivered_implementation"}


def test_brownfield_checklist_only_for_swe3_of_delivery_work_orders():
    g, b = load_checklist("SWE.3"), load_checklist("SWE.3", brownfield=True)
    assert g["version"] == "0.4" and b["version"] == "0.4-brownfield"
    assert [c["id"] for c in g["checks"]] == [c["id"] for c in b["checks"]]  # same items, same v0.3 base
    assert {c["id"]: c.get("deterministic_check") for c in b["checks"] if c["id"] in DELIVERED} == DELIVERED
    assert {c["id"]: c.get("deterministic_check") for c in g["checks"] if c["id"] in DELIVERED} == {
        "SWE3-07": "hal_guideline_conformance", "SWE3-08": "register_map_conformance",
        "SWE3-09": "implementation_completeness"}
    assert b["policy"] == g["policy"]
    for ph in PHASES:
        if ph != "SWE.3":
            assert load_checklist(ph, brownfield=True) == load_checklist(ph)


def test_store_selects_by_manifest(tmp_path):
    (tmp_path / ".forge-run").mkdir()
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL"}))
    assert Store(tmp_path).checklist("SWE.3")["version"] == "0.4"
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL", "delivery": {"code_mode": "FROZEN"}}))
    assert Store(tmp_path).checklist("SWE.3")["version"] == "0.4-brownfield"


def test_inspector_prompt_names_the_brownfield_items():
    old = prompts.BROWNFIELD["mode"]
    try:
        prompts.BROWNFIELD["mode"] = None
        green = prompts.inspector_prompt("SWE.3")
        prompts.BROWNFIELD["mode"] = "FROZEN"
        brown = prompts.inspector_prompt("SWE.3")
    finally:
        prompts.BROWNFIELD["mode"] = old
    assert "Generated HAL/LL C code conforms" in green and "Generated HAL/LL C code conforms" not in brown
    assert "The delivered code is checked against the guideline" in brown


def test_expected_masks_from_the_rm():
    rm = {"RCC_CFGR1": {"fields": {"SYSSW": (25, 24), "STOPWUCK": (0, 0)}}}
    assert K._expected_mask("RCC_CFGR1_SYSSW", "RCC_CFGR1", "SYSSW", rm) == ("mask", 0x3000000)
    assert K._expected_mask("RCC_CFGR1_SYSSW_Msk", "RCC_CFGR1", "SYSSW_Msk", rm) == ("mask", 0x3000000)
    assert K._expected_mask("RCC_CFGR1_SYSSW_Pos", "RCC_CFGR1", "SYSSW_Pos", rm) == ("pos", 24)
    assert K._expected_mask("RCC_CFGR1_SYSSW_1", "RCC_CFGR1", "SYSSW_1", rm) == ("mask", 0x2000000)
    assert K._expected_mask("RCC_CFGR1_NOPE", "RCC_CFGR1", "NOPE", rm) is None


@pilot_mark
def test_st_pilot_items_record_vendor_findings(ws):  # noqa: F811
    _contract(ws)
    rep = K.findings(ws)
    rd = rep["delivered_register_definitions"]
    assert rd["build"] == "PASS" and rd["probes"] >= 10 and rd["findings"] == []  # ST's header matches RM0486
    assert {"CSR", "CCR", "SR", "AHB1ENSR"} <= set(rd["registers"]) and "RCC_CSR_HSIONS" in rd["tokens"]
    gl = rep["delivered_guideline"]
    assert gl["findings"] and gl["violations_total"] > len(gl["findings"])  # only the scope is the subject
    im = rep["delivered_implementation"]["findings"]  # the r170 architecture allocates factory names, not ST's
    assert im and all(f.startswith("ALLOCATED_NOT_DELIVERED:LL_RCC_") for f in im)
    assert "ALLOCATED_NOT_DELIVERED:LL_RCC_HSI_Enable" not in im  # names ST does deliver are found
    assert K.item(ws, "delivered_guideline")["verdict"] == "FAIL"  # not yet recorded by the verify node
    cc = code_checks(ws)
    (ws / K.FINDINGS).write_text(json.dumps({"code_checks": cc}))
    for check in K.CHECKS:
        assert K.item(ws, check)["verdict"] == "PASS", check
    assert set(gl["findings"]) <= set(cc["findings"])


@pilot_mark
def test_st_pilot_vendor_register_mismatch_is_found(ws):  # noqa: F811
    _contract(ws)
    h = ws / "inputs/vendor/include/stm32n657xx.h"
    h.chmod(0o644)
    t = h.read_text()
    old = "#define RCC_CSR_HSIONS_Pos                      (3UL)"
    assert old in t
    h.write_text(t.replace(old, old.replace("(3UL)", "(4UL)")))
    rd = K.findings(ws)["delivered_register_definitions"]
    assert rd["build"] == "PASS" and rd["findings"] == ["REGISTER_DEFINITION_MISMATCH:mask RCC_CSR_HSIONS"]
    im = K.item(ws, "delivered_implementation")  # the vendor input changed after intake: always a FAIL
    assert im["verdict"] == "FAIL" and any("DELIVERY_MISMATCH" in f for f in im["major_findings"])


@pytest.mark.parametrize("build", ["FAIL", "NOT_RUN"])
def test_unbuilt_probes_fail_the_item(tmp_path, monkeypatch, build):
    monkeypatch.setattr(K, "RUN", {**K.RUN, "delivered_register_definitions":
                                   lambda _ws, _m: {"build": build, "probes": 3, "findings": []}})
    (tmp_path / ".forge-run").mkdir()
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps(
        {"delivery": {"build": {"style": "cmsis"}}, "code_mode": "FROZEN"}))
    r = K.item(tmp_path, "delivered_register_definitions")
    assert r["verdict"] == "FAIL" and r["major_findings"] == [f"REGISTER_PROBES_NOT_{'BUILT' if build == 'FAIL' else 'RUN'}"]
