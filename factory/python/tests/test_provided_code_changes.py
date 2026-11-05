"""Owner decision 2026-11-03 (revised): provided code (a HAL order's provided LL, FROZEN delivered code) may be changed
in the consuming work order's own copy when a linked CODE defect sends it to SWE.3; every change is documented in a
deterministic diff report for human inspection and carried into the offline review package. An unlinked change is
refused; the source work order and its baseline stay unchanged."""
from __future__ import annotations

import json

import pytest
from forge_factory import layer as LY
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT, sha256_file
from forge_factory.inspection import defects, engine
from forge_factory.inspection import provided_changes as PC
from forge_factory.inspection.implementation import check_implementation
from forge_factory.inspection.regmap import FUNCTIONS_MARKER
from forge_factory.policy.authz import Authorizer, Binding
from forge_factory.workflow import prompts

HAL_EX = REPO_ROOT / "examples/0002b-arm_55_rcc_hal"
LL_TEXT = ("#ifndef STM32N6XX_LL_RCC_H\n#define STM32N6XX_LL_RCC_H\n#include <stdint.h>\n"
           "static inline uint32_t LL_RCC_HSI_IsReady(void)\n{\n    return 0U;\n}\n" + FUNCTIONS_MARKER +
           "\n#endif /* STM32N6XX_LL_RCC_H */\n")
REQ = "When the HSI ready query is called with RCC_SR.HSIRDY set, the RCC LL driver shall return 1U."


@pytest.fixture()
def hal(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    src = tmp_path / "state/workorders/WO-LL-1/workspace"
    (src / "software/ll").mkdir(parents=True)
    (src / LY.LL_HEADER).write_text(LL_TEXT)
    (src / ".forge-run").mkdir(parents=True)
    (src / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL"}))
    monkeypatch.setattr(engine.Store, "gate", lambda self, ph: {"decision": "PASS"})
    ws, _m = WO.prepare(HAL_EX, "WO-HAL-PC", "WO-LL-1")
    (ws / "workproducts/SWE.1").mkdir(parents=True, exist_ok=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(f"# Software requirements\n\n- **SWR-001** {REQ}\n")
    yield ws, src
    prompts.LAYER["layer"] = "LL+HAL"


def _auth(ws):
    return Authorizer(Binding("b", str(ws), {"swe3_author": {"role": "swe3-author", "phase": "SWE.3"},
                                              "swe4_author": {"role": "swe4-author", "phase": "SWE.4"}}))


def _defect(ws):
    return defects.report(ws, detected_phase="SWE.4", reported_by="swe4-author", kind="CODE",
                          summary="UT-012 (USPEC-LL-01-02) fails: SWR-001 requires 1U when RCC_SR.HSIRDY is set; the "
                                  f"provided {LY.LL_HEADER} always returns 0U",
                          requirement_ids=["SWR-001"], test_files=[], evidence_refs=[f"{LY.LL_HEADER}:6"],
                          requirement_quote=REQ)


def test_the_provided_original_is_kept_hash_bound(hal):
    ws, src = hal
    assert PC.enabled(ws)
    orig = ws / PC.ORIGINALS / LY.LL_HEADER
    assert orig.read_text() == LL_TEXT and (orig.stat().st_mode & 0o222) == 0
    rep = PC.report(ws)
    assert [f["status"] for f in rep["files"]] == ["UNCHANGED"] and not rep["human_review_required"]
    assert PC.findings(ws) == []


def test_a_change_without_a_linked_defect_is_refused(hal):
    ws, _src = hal
    assert _auth(ws).decide("swe3_author", "write_file", {"path": LY.LL_HEADER, "content": ""}).code == \
        "PROVIDED_COMPONENT_READ_ONLY"
    p = ws / LY.LL_HEADER
    p.chmod(0o644)
    p.write_text(LL_TEXT.replace("return 0U;", "return 1U;"))  # an edit that bypassed the tools
    assert PC.findings(ws) == [f"PROVIDED_CODE_CHANGED_WITHOUT_DEFECT:{LY.LL_HEADER} (provided code changes only for "
                               "a CODE defect that names this file; restore it or link the change)"]
    assert f"IMPL:PROVIDED_COMPONENT_CHANGED:{LY.LL_HEADER}" in check_implementation(ws)["major_findings"]


def test_a_linked_change_is_accepted_and_reported_for_human_inspection(hal, tmp_path):
    ws, src = hal
    before_src, before_orig = sha256_file(src / LY.LL_HEADER), sha256_file(ws / PC.ORIGINALS / LY.LL_HEADER)
    d = _defect(ws)
    assert d["target_phase"] == "SWE.3"
    assert _auth(ws).decide("swe4_author", "write_file", {"path": LY.LL_HEADER, "content": ""}).allow is False
    dec = _auth(ws).decide("swe3_author", "write_file", {"path": LY.LL_HEADER, "content": ""})
    assert dec.allow, dec  # the SWE.3 author fixes the workspace copy (made writable), never the original
    (ws / LY.LL_HEADER).write_text(LL_TEXT.replace("return 0U;", "return ((ll_rcc_regs[1] & 2U) != 0U) ? 1U : 0U;"))
    assert PC.findings(ws) == []
    assert f"IMPL:PROVIDED_COMPONENT_CHANGED:{LY.LL_HEADER}" not in check_implementation(ws)["major_findings"]
    rep = json.loads((ws / PC.REPORT_JSON).read_text())
    f = rep["files"][0]
    assert f["status"] == "CHANGED_LINKED" and rep["changes"] == 1 and rep["human_review_required"]
    assert f["original_sha256"] == before_orig and f["final_sha256"] == sha256_file(ws / LY.LL_HEADER)
    r = f["hunks"][0]["reasons"][0]
    assert r["defect"] == d["id"] and r["tests"] == ["UT-012"] and r["requirements"] == ["SWR-001"]
    assert r["uspecs"] == ["USPEC-LL-01-02"] and "always returns 0U" in r["required_vs_original"]
    md = (ws / PC.REPORT_MD).read_text()
    assert md.startswith(f"# {PC.TITLE}") and "-    return 0U;" in md and "```diff" in md and d["id"] in md
    assert sha256_file(src / LY.LL_HEADER) == before_src  # the source work order is unchanged
    assert sha256_file(ws / PC.ORIGINALS / LY.LL_HEADER) == before_orig  # the hash-bound original is unchanged
    stage = tmp_path / "stage"
    (stage / "safety").mkdir(parents=True)
    (stage / "safety/known_limitations.md").write_text("# Known limitations\n")
    out = PC.stage_into(ws, stage)
    kl = (stage / "safety/known_limitations.md").read_text()
    assert out["human_review_required"] and f"## {PC.TITLE}" in kl and "PROVIDED CODE WAS MODIFIED" in kl
    assert "NOT used unchanged" in kl and (stage / "quality/provided-code-changes.md").read_text() == md


def test_inspectors_see_the_diff_report():
    prompts.UNIT_VERIFICATION["gtest"] = True
    try:
        for ph in ("SWE.3", "SWE.4", "SWE.5", "SWE.6"):
            assert "provided_code_changes.md" in prompts.inspector_prompt(ph, {"checks": [
                {"id": "X-01", "criterion": "c"}]})
        assert "provided_code_changes.md" not in prompts.inspector_prompt("SWE.2", {"checks": [
            {"id": "X-01", "criterion": "c"}]})
    finally:
        prompts.UNIT_VERIFICATION["gtest"] = False


def test_older_work_orders_keep_the_provided_ll_read_only(hal):
    ws, _src = hal
    m = json.loads((ws / ".forge-run/manifest.json").read_text())
    m.pop("unit_verification")
    (ws / ".forge-run/manifest.json").write_text(json.dumps(m))
    _defect(ws)
    assert not PC.enabled(ws) and PC.findings(ws) == []
    assert _auth(ws).decide("swe3_author", "write_file", {"path": LY.LL_HEADER, "content": ""}).code == \
        "PROVIDED_COMPONENT_READ_ONLY"


@pytest.mark.parametrize("flag,target", [(True, "SWE.3"), (False, None)])
def test_frozen_delivered_code_defect_goes_to_swe3_only_under_change_control(tmp_path, monkeypatch, flag, target):
    from forge_factory.brownfield import delivery as D
    from forge_factory.common import sha256_bytes

    ws = tmp_path / "ws"
    rel = "software/hal/crc_hal.c"
    data = b"int crc(void) { return 0; }\n"
    (ws / "software/hal").mkdir(parents=True)
    (ws / rel).write_bytes(data)
    (ws / ".forge-run").mkdir()
    (ws / "workproducts/SWE.1").mkdir(parents=True)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(f"# Software requirements\n\n- **SWR-001** {REQ}\n")
    m = {"work_order": "WO-BF", "layer": "HAL", "code_mode": "FROZEN", "delivery": {"scope": {"functions": ["crc"]}},
         "delivered": [{"path": rel, "role": "delivered_code", "sha256": sha256_bytes(data)}],
         **({"unit_verification": LY.UNIT_VERIFICATION} if flag else {})}
    (ws / ".forge-run/manifest.json").write_text(json.dumps(m))
    monkeypatch.setattr(D, "stored", lambda wo: {rel: data})
    d = defects.report(ws, detected_phase="SWE.4", reported_by="swe4-author", kind="CODE",
                       summary=f"UT-003 fails: SWR-001 requires 1U; the delivered {rel} returns 0",
                       requirement_ids=["SWR-001"], test_files=[], evidence_refs=[f"{rel}:1"], requirement_quote=REQ)
    assert d["target_phase"] == target
    if flag:  # the change is accepted only as a linked change, with the diff report
        (ws / rel).write_bytes(b"int crc(void) { return 1; }\n")
        rep = PC.write(ws)
        assert rep["files"][0]["kind"] == "frozen_delivery" and rep["files"][0]["status"] == "CHANGED_LINKED"
        assert rep["files"][0]["hunks"][0]["reasons"][0]["defect"] == d["id"]
