"""Owner-approved CMSIS C/GoogleTest interoperability; real pinned vendor inputs and host toolchain."""
import json
import shutil

import pytest
from forge_factory import workorder as W
from forge_factory.brownfield import cmsis, resume
from forge_factory.layer import UNIT_VERIFICATION
from forge_factory.mcp import sdk
from forge_factory.mcp.servers import build as B
from forge_factory.mcp.servers import tests as T
from forge_factory.workflow import scaffold as SC
from test_brownfield_pilot import ws, pytestmark  # noqa: F401 - pinned input availability + real intake fixture
from test_brownfield_st_host import UT, UT_GTEST


def save(ws, manifest):
    (ws / ".forge-run/manifest.json").write_text(json.dumps(manifest))


def context(ws):
    return sdk.ToolContext("forge-tests-mcp", "run_unit", "swe4-author", "SWE.4", ws, "cmsis-abi-check")


def test_fresh_vendor_intake_builds_and_executes_google_tests_without_changing_delivered_headers(ws):
    manifest = json.loads((ws / ".forge-run/manifest.json").read_text())
    assert manifest[cmsis.GTEST_LINKAGE_FIELD] == cmsis.GTEST_LINKAGE
    assert manifest["unit_verification"] == UNIT_VERIFICATION
    before = {p: (ws / p).read_bytes() for p in (x["path"] for x in manifest["delivered"])}
    out = SC._scaffold(ws)
    assert out["framework"] == "googletest-1.11.0" and out["host_device"]
    p = ws / SC.unit_test(ws)
    assert p.suffix == ".cpp"
    p.write_text(p.read_text().replace(SC.TEST_CASES_MARKER, UT_GTEST + SC.TEST_CASES_MARKER))
    result = T.run_unit(context(ws), T.RunIn(coverage=True))
    assert result["status"] == "PASS", result["issues"]
    assert result["metrics"]["executables"] == 1
    coverage = T.llvm_coverage(context(ws), T.CovIn())
    assert coverage["status"] == "PASS", coverage["issues"]
    assert coverage["metrics"]["scope_function_pct"] > 0
    ref = coverage["artifact_refs"][0].split(":")[-1]
    exported = json.loads((ws / "evidence/raw" / (ref + ".json")).read_text())
    assert any(f["filename"].endswith("software/ll/stm32n6xx_ll_rcc.h")
               and f["summary"]["lines"]["covered"] > 0 for f in exported["data"][0]["files"])
    target = B.compile_(sdk.ToolContext("forge-build-mcp", "compile", "swe3-author", "SWE.3", ws, "abi-target"),
                        B.CompileIn(profile="target-cm55-gcc"))
    assert target["status"] == "PASS", target["issues"]
    assert all((ws / p).read_bytes() == raw for p, raw in before.items())


def test_cpp_cannot_link_a_vendor_function_outside_the_resolved_scope(ws):
    SC._scaffold(ws)
    p = ws / SC.unit_test(ws)
    p.write_text(p.read_text().replace(SC.TEST_CASES_MARKER,
        'TEST(ScopeBoundary, UT_001) { LL_RCC_HSE_EnableCSS(); EXPECT_TRUE(true); }\n' + SC.TEST_CASES_MARKER))
    result = T.run_unit(context(ws), T.RunIn(coverage=False))
    assert result["status"] == "FAIL"
    assert any("forge_cmsis_cabi_LL_RCC_HSE_EnableCSS" in issue for issue in result["issues"]), result["issues"]


def test_native_cmsis_instructions_use_the_bound_shim_without_the_generated_array_example(ws):
    from forge_factory.acp import statements
    from forge_factory.workflow.builder import build
    manifest = json.loads((ws / ".forge-run/manifest.json").read_text())
    def unit_prompt(man):
        graph, _ = build("WO-ABI-GUIDANCE", layer="LL", brownfield="FROZEN", delivery_style="cmsis",
                         uspec_gtest=True, assessment_manifest=man)
        return {n: attrs for _, _, _, n, attrs in statements(graph)}["swe4_test_author"]
    assert "CMSIS C-ABI HOST TESTS" in unit_prompt(manifest)
    legacy = dict(manifest)
    legacy.pop(cmsis.GTEST_LINKAGE_FIELD)
    assert "CMSIS C-ABI HOST TESTS" not in unit_prompt(legacy)


@pytest.mark.parametrize("example,body", [
    ("0014c-st-cube-crc", 'LL_CRC_Write_IDR(CRC, 0xA5U); EXPECT_EQ(LL_CRC_Read_IDR(CRC), 0xA5U);'),
    ("0016c-st-cube-wwdg", 'LL_WWDG_SetCounter(WWDG, 0x55U); EXPECT_EQ(LL_WWDG_GetCounter(WWDG), 0x55U);')])
def test_real_pointer_parameter_and_return_value_cross_the_c_abi(tmp_path, monkeypatch, example, body):
    from forge_factory.common import REPO_ROOT
    from forge_factory.brownfield import delivery as D, DELIVERY_DIR
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    work, manifest = W.prepare(REPO_ROOT / "examples" / example, "WO-POINTER-ABI")
    # Controlled post-intake fixture, exactly as the existing vendor-input tests.
    # No source phase is manufactured or claimed passed.
    for path, data in D.stored(manifest["work_order"]).items():
        p = work / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    (work / DELIVERY_DIR).mkdir(parents=True, exist_ok=True)
    shutil.copyfile(D.store_dir(manifest["work_order"]) / "scope.json", work / DELIVERY_DIR / "scope.json")
    SC._scaffold(work)
    p = work / SC.unit_test(work)
    p.write_text(p.read_text().replace(SC.TEST_CASES_MARKER,
        'TEST(CmsisPointers, UT_001) { ut_reset_regs(); ' + body + ' }\n' + SC.TEST_CASES_MARKER))
    out = T.run_unit(context(work), T.RunIn(coverage=False))
    assert out["status"] == "PASS", out["issues"]


def test_c_driver_and_cpp_google_test_share_the_generated_host_instance(ws):
    SC._scaffold(ws)
    bridge = ws / "software/src/host_abi_probe.c"
    bridge.parent.mkdir(parents=True, exist_ok=True)
    bridge.write_text('/* Test-only bridge: exercise the real C compilation and linkage. */\n'
                      '#include "forge_host_device.h"\n#include "stm32n6xx_ll_rcc.h"\n'
                      'void host_abi_enable_hsi(void) { LL_RCC_HSI_Enable(); }\n')
    # Deliberately include the generated shim outside an enclosing extern C:
    # the shim itself must publish the C ABI, independently of scaffold wrapping.
    test = ws / SC.unit_test(ws)
    test.write_text('#include <gtest/gtest.h>\n'
                    '#define FORGE_HOST_DEVICE_IMPLEMENTATION\n#include "forge_host_device.h"\n'
                    'extern "C" void host_abi_enable_hsi(void);\n'
                    'TEST(CmsisABI, UT_001) { forge_host_rcc.CSR = 0U; host_abi_enable_hsi(); '
                    'EXPECT_EQ(forge_host_rcc.CSR, RCC_CSR_HSIONS); }\n')
    result = T.run_unit(context(ws), T.RunIn(coverage=False))
    assert result["status"] == "PASS", result["issues"]
    assert list((ws / "build/tests-unit").glob("*.c*.o"))


def test_legacy_cmsis_order_keeps_its_recorded_c_harness_and_still_executes(ws):
    manifest = json.loads((ws / ".forge-run/manifest.json").read_text())
    manifest.pop(cmsis.GTEST_LINKAGE_FIELD)
    save(ws, manifest)
    SC._scaffold(ws)
    p = ws / SC.unit_test(ws)
    assert p.suffix == ".c"
    p.write_text(p.read_text().replace(SC.TEST_CASES_MARKER, UT + SC.TEST_CASES_MARKER)
                 .replace(SC.TEST_CALLS_MARKER, "ut_hsi();\n    " + SC.TEST_CALLS_MARKER))
    result = T.run_unit(context(ws), T.RunIn(coverage=False))
    assert result["status"] == "PASS", result["issues"]


def test_linkage_is_in_the_new_resume_contract_but_absent_from_the_legacy_contract(ws):
    manifest = json.loads((ws / ".forge-run/manifest.json").read_text())
    modern = resume.contract(manifest)
    assert modern[cmsis.GTEST_LINKAGE_FIELD] == cmsis.GTEST_LINKAGE
    manifest.pop(cmsis.GTEST_LINKAGE_FIELD)
    legacy = resume.contract(manifest)
    assert cmsis.GTEST_LINKAGE_FIELD not in legacy
    assert {k: v for k, v in modern.items() if k != cmsis.GTEST_LINKAGE_FIELD} == legacy
    manifest[cmsis.GTEST_LINKAGE_FIELD] = "unknown-abi"
    save(ws, manifest)
    with pytest.raises(ValueError, match="CMSIS_HOST_TEST_LINKAGE_INVALID"):
        SC.unit_test(ws)


@pytest.mark.parametrize("bound,expected", [(False, False), (True, True)])
def test_resume_intake_inherits_source_linkage_before_preparing_any_work(tmp_path, monkeypatch, bound, expected):
    """Probe public intake only; never submit inference or manufacture passed source phases."""
    from test_brownfield_pilot import EX
    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "events"))
    old = {"delivery": {"build": {"style": "cmsis"}},
           "resume_identity": {"limits": resume.DEFAULT_LIMITS}}
    if bound:
        old[cmsis.GTEST_LINKAGE_FIELD] = cmsis.GTEST_LINKAGE
    source = tmp_path / "source"
    (source / ".forge-run").mkdir(parents=True)
    save(source, old)
    monkeypatch.setattr(resume, "check_source", lambda *a: (source, old))
    monkeypatch.setattr(resume, "source_workspace", lambda *a: source)
    monkeypatch.setattr(W, "suspension", lambda *a: None)
    class IntakeReached(Exception):
        pass
    def prepare(*args, **kwargs):
        assert kwargs["cmsis_gtest"] is expected
        raise IntakeReached
    monkeypatch.setattr(W, "prepare", prepare)
    with pytest.raises(IntakeReached):
        W.run(EX, "WO-ABI-RESUME", resume="WO-ABI-SOURCE")
