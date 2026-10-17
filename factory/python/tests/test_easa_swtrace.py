"""Owner addendum 2026-10-17 (EASA-T073..T077): SWC structure, unit specs (ReqIF), Doxygen trace, six matrices."""
import hashlib
import json
import shutil

import pytest
from forge_factory.inspection import swtrace

REQS = """# Software requirements
- **SWR-001** When the HSI enable is requested, the RCC driver shall set RCC_CR.HSION.
  - Source: RM0486 p.480
- **SWR-002** When the HSI disable is requested, the RCC driver shall clear RCC_CR.HSION.
  - Source: RM0486 p.480
- **SWR-003** The RCC driver shall bound every oscillator ready wait to at most 1000 polling iterations.
  - Source: owner
"""
ARCH = """@startuml
component "RCC_HAL\\nhal_status_t API" <<SWC>> as SWC_HAL
component "RCC_LL\\n(PROVIDED)" <<SWC>> as SWC_LL
component "RCC registers" as RCC
note right of SWC_HAL
  Allocated: SWR-001, SWR-002, SWR-003
end note
SWC_HAL --> SWC_LL : IF-01 LL_RCC_* accessors
SWC_LL --> RCC : IF-02 ll_rcc_regs[] read-modify-write
@enduml
"""
UNITS = """# Unit specifications
## SWU-HAL-01: HSI enable
- SWC: SWC_HAL
- Functions: HAL_RCC_HSI_Enable
- Design: workproducts/SWE.3/detailed_design/SWU-HAL-01.puml
- **USPEC-HAL-01-01** Set HSION through LL_RCC_HSI_Enable. Traces: SWR-001
- **USPEC-HAL-01-02** Poll HSIRDY at most `timeout` (<= 1000) iterations. Traces: SWR-003
## SWU-HAL-02: HSI disable
- SWC: SWC_HAL
- Functions: HAL_RCC_HSI_Disable
- Design: workproducts/SWE.3/detailed_design/SWU-HAL-02.puml
- **USPEC-HAL-02-01** Clear HSION through LL_RCC_HSI_Disable. Traces: SWR-002
"""
DESIGN = "@startuml\ntitle {u} {fn}\nstart\n:{fn};\nstop\n@enduml\n"
CODE = """/**
 * @file stm32n6xx_hal_rcc.c
 * @brief RCC HAL.
 */
#include "stm32n6xx_hal_rcc.h"

/**
 * @brief Enable HSI and wait for ready.
 * @param timeout polling bound
 * @return status
 * @unit SWU-HAL-01
 * @spec USPEC-HAL-01-01 USPEC-HAL-01-02
 */
hal_status_t HAL_RCC_HSI_Enable(uint32_t timeout)
{
    (void)timeout;
    return HAL_OK;
}

/**
 * @brief Disable HSI.
 * @return status
 * @unit SWU-HAL-02
 * @spec USPEC-HAL-02-01
 */
hal_status_t HAL_RCC_HSI_Disable(void)
{
    return HAL_OK;
}
"""
UT = """/** @test UT-001 @verifies USPEC-HAL-01-01 */
static void ut1(void) { }
/** @test UT-002 @verifies USPEC-HAL-01-02 */
static void ut2(void) { }
/** @test UT-003 @verifies USPEC-HAL-02-01 */
static void ut3(void) { }
"""
IT = """/** @test IT-001 @verifies IF-01 SWC_HAL */
static void it1(void) { }
/** @test IT-002 @verifies IF-02 */
static void it2(void) { }
"""
ROBOT = """<?xml version="1.0"?><robot><suite name="s">
<test name="SWR-001"><tags><tag>SWR-001</tag></tags><status status="PASS"/></test>
<test name="SWR-002"><tags><tag>SWR-002</tag></tags><status status="PASS"/></test>
<test name="SWR-003"><tags><tag>SWR-003</tag></tags><status status="PASS"/></test>
</suite></robot>"""


def _raw(ws, body: bytes, ext: str) -> str:
    h = hashlib.sha256(body).hexdigest()
    (ws / "evidence/raw").mkdir(parents=True, exist_ok=True)
    (ws / "evidence/raw" / f"{h}{ext}").write_bytes(body)
    return f"artifact:sha256:{h}"


@pytest.fixture
def ws(tmp_path):
    w = tmp_path / "WO-T" / "workspace"
    files = {".forge-run/manifest.json": json.dumps({"layer": "HAL"}),
             "workproducts/SWE.1/software_requirements.md": REQS,
             "workproducts/SWE.2/architecture_static.puml": ARCH,
             "workproducts/SWE.3/unit_specifications.md": UNITS,
             "workproducts/SWE.3/detailed_design/SWU-HAL-01.puml": DESIGN.format(u="SWU-HAL-01", fn="HAL_RCC_HSI_Enable"),
             "workproducts/SWE.3/detailed_design/SWU-HAL-02.puml": DESIGN.format(u="SWU-HAL-02", fn="HAL_RCC_HSI_Disable"),
             "software/hal/stm32n6xx_hal_rcc.c": CODE,
             "software/tests/unit/test_rcc.c": UT,
             "software/tests/integration/test_rcc_integration.c": IT}
    for rel, text in files.items():
        (w / rel).parent.mkdir(parents=True, exist_ok=True)
        (w / rel).write_text(text)
    recs = [{"op": "run_unit", "phase": "SWE.4", "result": {"status": "PASS", "artifact_refs": [
                _raw(w, b"UT-001 PASS\nUT-002 PASS\nUT-002b PASS\nUT-003 PASS\n", ".log")]}},
            {"op": "run_integration", "phase": "SWE.5", "result": {"status": "PASS", "artifact_refs": [
                _raw(w, b"IT-001 PASS\nIT-002a PASS\n", ".log")]}},
            {"op": "run_robot", "phase": "SWE.6", "result": {"status": "PASS", "artifact_refs": [
                _raw(w, ROBOT.encode(), ".xml")]}}]
    (w / "evidence/tool-results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    return w


def _edit(ws, rel, old, new):
    p = ws / rel
    t = p.read_text()
    assert old in t, old
    p.write_text(t.replace(old, new))


def test_at092_consistent_set_six_matrices_deterministic(ws):
    rep = swtrace.build_all(ws, render=False, doxygen=False)
    assert {k: v for k, v in rep["findings"].items() if v} == {}
    assert [m["matrix"] for m in rep["matrices"]] == [1, 2, 3, 4, 5, 6]
    assert all(m["uncovered"] == [] for m in rep["matrices"])
    first = {p.name: p.read_bytes() for p in ws.glob("workproducts/SWE.*/traceability/matrix_*")}
    assert len(first) == 12 and not list((ws / "traceability").glob("matrix_*"))      # SWE.1's folder untouched
    swtrace.build_all(ws, render=False, doxygen=False)
    assert {p.name: p.read_bytes() for p in ws.glob("workproducts/SWE.*/traceability/matrix_*")} == first
    m4 = (ws / "workproducts/SWE.4/traceability/matrix_4_unittest_to_unitspec.csv").read_text().splitlines()
    assert m4[0] == "test,file,uspec,result,status" and "UT-002,software/tests/unit/test_rcc.c,USPEC-HAL-01-02,PASS,VERIFIED" in m4


def test_at092_removed_link_is_uncovered_and_fails_its_phase(ws):
    _edit(ws, "software/tests/unit/test_rcc.c", "@test UT-003 @verifies USPEC-HAL-02-01", "@test UT-003 @verifies")
    rep = swtrace.build_all(ws, render=False, doxygen=False)
    assert rep["findings"]["SWE.4"] == ["UT:TEST_WITHOUT_TRACE:UT-003", "UT:SPEC_NOT_VERIFIED:USPEC-HAL-02-01"]
    assert next(m for m in rep["matrices"] if m["matrix"] == 4)["uncovered"] == ["USPEC-HAL-02-01"]


def test_at085_swc_count_and_layer_separation(ws):
    _edit(ws, "workproducts/SWE.2/architecture_static.puml", 'component "RCC_LL\\n(PROVIDED)" <<SWC>> as SWC_LL',
          'component "RCC_LL\\n(PROVIDED)" as SWC_LL')
    f = swtrace.check_architecture_model(ws)["major_findings"]
    assert "ARCH:SWC_COUNT:SWC_LL=0!=1" in f
    _edit(ws, "workproducts/SWE.2/architecture_static.puml", 'as SWC_HAL\n', 'as SWC_HAL\ncomponent "drv" <<SWC>> as SWC_DRIVER\n')
    assert any(x.startswith("ARCH:LAYER_NOT_SEPARATE") for x in swtrace.check_architecture_model(ws)["major_findings"])


def test_at086_unallocated_swr_and_unlabelled_interface(ws):
    _edit(ws, "workproducts/SWE.2/architecture_static.puml", "Allocated: SWR-001, SWR-002, SWR-003", "Allocated: SWR-001, SWR-002")
    _edit(ws, "workproducts/SWE.2/architecture_static.puml", ": IF-02 ll_rcc_regs[] read-modify-write", ": registers")
    f = swtrace.check_architecture_model(ws)["major_findings"]
    assert "ARCH:SWR_NOT_ALLOCATED:SWR-003" in f and "ARCH:INTERFACE_WITHOUT_ID:SWC_LL->RCC" in f


def test_ll_layer_expects_only_swc_ll(ws):
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "LL"}))
    f = swtrace.check_architecture_model(ws)["major_findings"]
    assert any(x.startswith("ARCH:LAYER_NOT_SEPARATE:unexpected SWC SWC_HAL") for x in f)


def test_at087_unit_design_missing_or_not_of_unit(ws):
    (ws / "workproducts/SWE.3/detailed_design/SWU-HAL-02.puml").unlink()
    _edit(ws, "workproducts/SWE.3/detailed_design/SWU-HAL-01.puml", "SWU-HAL-01", "SWU-HAL-99")
    f = swtrace.check_units(ws, render=False, export=False)["major_findings"]
    assert "UNIT:DESIGN_MISSING:SWU-HAL-02" in f and "UNIT:DESIGN_NOT_OF_UNIT:SWU-HAL-01" in f


@pytest.mark.skipif(swtrace._plantuml_jar() is None or shutil.which("java") is None, reason="plantuml not installed")
def test_at087_design_render_failure_detected_by_real_plantuml(ws):
    assert swtrace.check_units(ws, render=True, export=False)["major_findings"] == []
    _edit(ws, "workproducts/SWE.3/detailed_design/SWU-HAL-02.puml", ":HAL_RCC_HSI_Disable;", ":HAL_RCC_HSI_Disable;\nif (broken")
    f = swtrace.check_units(ws, render=True, export=False)["major_findings"]
    assert any(x.startswith("UNIT:DESIGN_RENDER_FAILED:SWU-HAL-02") for x in f)


def test_at088_spec_trace_rules_and_reqif_is_xsd_valid(ws):
    r = swtrace.check_units(ws, render=False, export=True)
    assert r["verdict"] == "PASS" and [x["verdict"] for x in r["reqif"]] == ["PASS", "PASS"]
    assert r["reqif"][0]["spec_objects"] == 4                       # 2 USPEC + 2 refined SWR objects
    _edit(ws, "workproducts/SWE.2/architecture_static.puml", "Allocated: SWR-001, SWR-002, SWR-003", "Allocated: SWR-001, SWR-003")
    _edit(ws, "workproducts/SWE.3/unit_specifications.md", "Poll HSIRDY at most `timeout` (<= 1000) iterations. Traces: SWR-003",
          "Poll HSIRDY. Traces: SWR-009")
    f = swtrace.check_units(ws, render=False, export=False)["major_findings"]
    assert "UNIT:SPEC_TRACES_UNALLOCATED_SWR:USPEC-HAL-02-01:SWR-002->SWC_HAL" in f
    assert "UNIT:UNKNOWN_SWR:USPEC-HAL-01-02:SWR-009" in f and "UNIT:SWR_NOT_REFINED:SWR-003" in f


def test_at089_code_doc_rules(ws):
    assert swtrace.check_code(ws, doxygen=False)["major_findings"] == []
    _edit(ws, "software/hal/stm32n6xx_hal_rcc.c", " * @unit SWU-HAL-02\n * @spec USPEC-HAL-02-01\n", "")
    _edit(ws, "software/hal/stm32n6xx_hal_rcc.c", "@spec USPEC-HAL-01-01 USPEC-HAL-01-02", "@spec USPEC-HAL-01-01 USPEC-HAL-07-01")
    f = swtrace.check_code(ws, doxygen=False)["major_findings"]
    assert any(x.startswith("CODE:UNDOCUMENTED_FUNCTION:HAL_RCC_HSI_Disable") for x in f)
    assert "CODE:UNKNOWN_SPEC_REF:HAL_RCC_HSI_Enable:USPEC-HAL-07-01" in f
    assert {"CODE:SPEC_NOT_IMPLEMENTED:USPEC-HAL-01-02", "CODE:SPEC_NOT_IMPLEMENTED:USPEC-HAL-02-01"} <= set(f)


@pytest.mark.skipif(shutil.which("doxygen") is None, reason="doxygen not installed")
def test_at089_real_doxygen_run_and_undocumented_warning(ws):
    r = swtrace.check_code(ws, doxygen=True)
    assert r["doxygen"]["status"] == "PASS" and r["verdict"] == "PASS", r["major_findings"]
    assert (ws / "build/doxygen/xml/index.xml").is_file()
    xref = list((ws / "build/doxygen/html").glob("unit.html"))
    assert xref and "SWU-HAL-01" in xref[0].read_text()               # the @unit xrefitem page lists the units
    _edit(ws, "software/hal/stm32n6xx_hal_rcc.c", "/**\n * @brief Disable HSI.", "/*\n * @brief Disable HSI.")
    r2 = swtrace.check_code(ws, doxygen=True)
    assert any(x.startswith("CODE:DOXYGEN_WARNING") for x in r2["major_findings"])


def test_at090_unit_test_trace_needs_executed_pass(ws):
    _edit(ws, "software/tests/unit/test_rcc.c", "@verifies USPEC-HAL-01-01", "@verifies USPEC-HAL-09-09")
    f = swtrace.build_all(ws, render=False, doxygen=False, upto="SWE.4")["findings"]["SWE.4"]
    assert f == ["UT:UNKNOWN_SPEC_REF:UT-001:USPEC-HAL-09-09", "UT:SPEC_NOT_VERIFIED:USPEC-HAL-01-01"]
    raw = next(p for p in (ws / "evidence/raw").glob("*.log") if b"UT-001" in p.read_bytes())
    raw.write_bytes(raw.read_bytes().replace(b"UT-003 PASS", b"UT-003 FAIL"))
    f2 = swtrace.build_all(ws, render=False, doxygen=False, upto="SWE.4")["findings"]["SWE.4"]
    assert "UT:SPEC_NOT_VERIFIED:USPEC-HAL-02-01" in f2           # tampered raw output: digest mismatch, not evidence
    assert "UT:SPEC_NOT_VERIFIED:USPEC-HAL-01-02" in f2


def test_at091_interface_and_validation_trace(ws):
    _edit(ws, "software/tests/integration/test_rcc_integration.c", "@verifies IF-02", "@verifies IF-07")
    rep = swtrace.build_all(ws, render=False, doxygen=False)
    assert "IT:INTERFACE_NOT_VERIFIED:IF-02" in rep["findings"]["SWE.5"]
    assert "IT:UNKNOWN_ARCH_REF:IT-002:IF-07" in rep["findings"]["SWE.5"]
    bad = ROBOT.replace("<tag>SWR-003</tag></tags><status status=\"PASS\"/>", "<tag>SWR-033</tag></tags><status status=\"PASS\"/>")
    with (ws / "evidence/tool-results.jsonl").open("a") as f:      # a newer, properly recorded run_robot result
        f.write(json.dumps({"op": "run_robot", "phase": "SWE.6", "result": {
            "status": "PASS", "artifact_refs": [_raw(ws, bad.encode(), ".xml")]}}) + "\n")
    f6 = swtrace.build_all(ws, render=False, doxygen=False)["findings"]["SWE.6"]
    assert f6 == ["VT:UNKNOWN_SWR:SWR-003:SWR-033", "VT:SWR_NOT_VERIFIED:SWR-003"]
    xml = next(p for p in (ws / "evidence/raw").glob("*.xml") if b"SWR-033" in p.read_bytes())
    xml.write_bytes(xml.read_bytes().replace(b"SWR-033", b"SWR-003"))   # tamper the recorded output
    f7 = swtrace.build_all(ws, render=False, doxygen=False)["findings"]["SWE.6"]
    assert f7[:3] == ["VT:SWR_NOT_VERIFIED:SWR-001", "VT:SWR_NOT_VERIFIED:SWR-002", "VT:SWR_NOT_VERIFIED:SWR-003"]


def test_check_phase_entry_point(ws):
    assert swtrace.check_phase(ws, "SWE.2")["verdict"] == "PASS"
    (ws / "workproducts/SWE.3/unit_specifications.md").unlink()
    r = swtrace.check_phase(ws, "SWE.3")
    assert r["verdict"] == "FAIL" and "UNIT:SPECIFICATION_MISSING" in r["major_findings"]


# ---- T078 / AT-093: workflow integration, opt-in by trace profile --------------------------------------------------
def test_at093_presence_gate_and_checklist_apply_only_with_trace_profile(ws):
    from forge_factory.inspection.engine import Store, load_checklist
    from forge_factory.layer import TRACE_PROFILE, swtrace_enabled

    st = Store(ws)
    assert not swtrace_enabled(ws)
    legacy = st.missing_outputs("SWE.3")
    assert not any("unit_specifications" in m for m in legacy)
    assert not any(c["id"] == "SWE3-10" for c in st.applicable(load_checklist("SWE.3"))["checks"])
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL", "trace_profile": TRACE_PROFILE}))
    assert swtrace_enabled(ws)
    new = {"MISSING_REQUIRED_OUTPUT:workproducts/SWE.3/unit_specifications.md",
           "MISSING_REQUIRED_OUTPUT:workproducts/SWE.3/detailed_design/SWU-*.puml"}
    assert not new & set(st.missing_outputs("SWE.3"))
    (ws / "workproducts/SWE.3/unit_specifications.md").unlink()
    shutil.rmtree(ws / "workproducts/SWE.3/detailed_design")
    miss = st.missing_outputs("SWE.3")
    assert "MISSING_REQUIRED_OUTPUT:workproducts/SWE.3/unit_specifications.md" in miss
    assert "MISSING_REQUIRED_OUTPUT:workproducts/SWE.3/detailed_design/SWU-*.puml" in miss
    ids = {c["id"] for p in ("SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6") for c in st.applicable(load_checklist(p))["checks"]}
    assert {"SWE2-09", "SWE3-10", "SWE4-07", "SWE5-07", "SWE6-07"} <= ids


def test_at093_deterministic_items_computed_by_engine(ws):
    from forge_factory.inspection.engine import Store, load_checklist
    from forge_factory.layer import TRACE_PROFILE

    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL", "trace_profile": TRACE_PROFILE}))
    st = Store(ws)
    det = st.deterministic_items("SWE.4", st.applicable(load_checklist("SWE.4")))
    assert det["SWE4-07"]["verdict"] == "PASS" and "workproducts/SWE.4/traceability/matrix_4_unittest_to_unitspec.csv" in det["SWE4-07"]["evidence_refs"]
    _edit(ws, "software/tests/unit/test_rcc.c", "@verifies USPEC-HAL-02-01", "@verifies")
    det = st.deterministic_items("SWE.4", st.applicable(load_checklist("SWE.4")))
    assert det["SWE4-07"]["verdict"] == "FAIL" and "UT:SPEC_NOT_VERIFIED:USPEC-HAL-02-01" in det["SWE4-07"]["findings"]


def test_at093_prompts_and_turn_budget_follow_the_profile(ws):
    from forge_factory.layer import TRACE_PROFILE
    from forge_factory.policy import governor
    from forge_factory.workflow import prompts as P

    before = governor.turn_limit("swe3-author", str(ws))
    (ws / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL", "trace_profile": TRACE_PROFILE}))
    assert governor.turn_limit("swe3-author", str(ws)) == before + governor.TRACE_EXTRA_TURNS
    assert governor.turn_limit("swe3-inspector", str(ws)) == governor.turn_limit("swe3-inspector", None)
    layer, on = P.LAYER["layer"], P.TRACE["on"]
    try:
        P.LAYER["layer"] = "HAL"
        P.TRACE["on"] = False
        assert "OWNER TRACE" not in P.author_prompt("SWE.3")
        P.TRACE["on"] = True
        a = P.author_prompt("SWE.3")
        assert "OWNER TRACE" in a and "USPEC-HAL-nn-mm" in a and a.index("OWNER TRACE") < a.index("freezes the SWE.3")
        assert "@verifies USPEC" in P.unit_test_author_prompt() and "@file" in P.target_test_author_prompt()
    finally:
        P.LAYER["layer"], P.TRACE["on"] = layer, on


def test_capa026_multiline_allocation_note_r108(ws):
    """CAPA-026 (r108): the agent wrapped the allocation list over four note lines; only the first was read."""
    _edit(ws, "workproducts/SWE.2/architecture_static.puml", "  Allocated: SWR-001, SWR-002, SWR-003\n",
          "Allocated: SWR-001,\nSWR-002,\nSWR-003\nHeader-only: stm32n6xx_hal_rcc.c\n")
    m = swtrace.parse_architecture((ws / "workproducts/SWE.2/architecture_static.puml").read_text())
    assert m["allocation"]["SWC_HAL"] == ["SWR-001", "SWR-002", "SWR-003"]
    assert swtrace.check_architecture_model(ws)["major_findings"] == []


def test_capa027_matrices_never_change_the_swe1_baseline(ws):
    """CAPA-027 (r109): writing matrix 1 into traceability/ made SWE.1 stale -> UPSTREAM_NOT_FROZEN for SWE.2."""
    from forge_factory.inspection.engine import Store

    st = Store(ws)
    (ws / "traceability").mkdir(exist_ok=True)
    (ws / "traceability/requirements_to_tests.csv").write_text("requirement_id,test_id,test_file\n")
    before = st.current_hash("SWE.1")
    for ph in ("SWE.2", "SWE.3", "SWE.4", "SWE.5", "SWE.6"):
        swtrace.check_phase(ws, ph)
        assert st.current_hash("SWE.1") == before, ph
    assert (ws / "workproducts/SWE.2/traceability/matrix_1_swr_to_architecture.csv").is_file()
