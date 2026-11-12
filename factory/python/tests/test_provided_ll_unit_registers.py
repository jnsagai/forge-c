"""Real C/GoogleTest executions: mock call contracts and provided LL RAM effects."""
import json

import pytest
from forge_factory import workorder as W
from forge_factory.common import sha256_file
from forge_factory.mcp.servers import tests as T
from forge_factory.workflow import provided_ll_unit as P
from forge_factory.workflow import scaffold as SC
from test_capa128_hal_on_st_ll import (
    HAL_C,
    HAL_H,
    UT,
    _ctx,
    _iwdg_hal_example,
    _source_ll,
    env,  # noqa: F401 - shared pytest fixture
)


@pytest.fixture
def workspace(env):  # noqa: F811 - imported shared fixture
    _source_ll(env / "state")
    ws, _ = W.prepare(_iwdg_hal_example(env), "WO-RAM-TEST", "WO-LL-ST")
    for name, text in [("stm32n6xx_hal_iwdg.h", HAL_H), ("stm32n6xx_hal_iwdg.c", HAL_C)]:
        path = ws / "software/hal" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    SC._scaffold(ws)
    test = ws / SC.unit_test(ws)
    test.write_text(test.read_text().replace(SC.TEST_CASES_MARKER, UT + "\n" + SC.TEST_CASES_MARKER))
    real = ws / "software/tests/unit/test_iwdg_registers.cpp"
    real.write_text(P.MARKER + '\n#include <gtest/gtest.h>\nextern "C" {\n'
                    '#include "stm32n6xx_hal_iwdg.h"\n}\n'
                    '/** @test UT-002 @verifies USPEC-HAL-01-02 */\n'
                    'TEST(RegisterEffects, UT_002) { IWDG->KR = 0U; '
                    'EXPECT_EQ(HAL_IWDG_Start(), 0U); EXPECT_EQ(IWDG->KR, 0xCCCCU); }\n')
    return ws


def run(ws, coverage=False):
    return T.run_unit(_ctx(ws, "forge-tests-mcp", "run_unit", "swe4-author", "SWE.4"), T.RunIn(coverage=coverage))


def test_both_backends_execute_same_c_hal_and_keep_provided_bytes(workspace):
    ws = workspace
    paths = [ws / "software/ll/stm32n6xx_ll_iwdg.h", ws / "software/tests/unit/ll_fake/stm32n6xx_ll_iwdg.h"]
    before = {p: sha256_file(p) for p in paths}
    out = run(ws, coverage=True)
    assert out["status"] == "PASS", out["issues"]
    assert out["summary"].startswith("unit: 2 passed, 0 failed (HOST)")
    assert {p: sha256_file(p) for p in paths} == before
    binding = json.loads(next((ws / "build/tests-unit/test_iwdg_registers").rglob("binding.json")).read_text())
    assert binding["linkage"] == "provided-ll-ram-v1" and binding["exported_symbols"] == []
    assert binding["target_or_hil_claim"] is False
    assert sorted(r["status"] for p in (ws / "build/tests-unit").glob("*.xml") for r in T.gtest_results(p)) == ["PASS", "PASS"]
    cov = T.llvm_coverage(_ctx(ws, "forge-tests-mcp", "llvm_coverage", "swe4-author", "SWE.4"), T.CovIn())
    assert cov["status"] == "PASS" and cov["metrics"]["line_pct"] == 100.0, cov


def test_cpp_does_not_compile_unused_arm_pointer_cast_bodies(workspace):
    ws = workspace
    p = ws / "software/ll/stm32n6xx_ll_iwdg.h"
    p.chmod(0o644)
    p.write_text(p.read_text() + '\n__STATIC_INLINE uint32_t LL_IWDG_Address(IWDG_TypeDef *IWDGx)\n'
                 '{ return (uint32_t)IWDGx; }\n')
    # This is fixture construction, with a new immutable input binding, before execution.
    manifest = ws / ".forge-run/manifest.json"
    man = json.loads(manifest.read_text())
    next(f for f in man["provided"] if f["path"].endswith(p.name))["sha256"] = sha256_file(p)
    manifest.write_text(json.dumps(man))
    from forge_factory.workflow import ll_fake

    ll_fake.write(ws)
    out = run(ws)
    assert out["status"] == "PASS", out["issues"]


def test_real_assertion_failure_cannot_be_hidden_by_passing_mock(workspace):
    p = workspace / "software/tests/unit/test_iwdg_registers.cpp"
    p.write_text(p.read_text().replace("0xCCCCU", "0xCCCDU"))
    out = run(workspace)
    assert out["status"] == "FAIL"
    assert any("UT-002" in i and i.startswith("GTEST_FAIL:") for i in out["issues"])


def test_direct_ll_call_has_no_export_and_cannot_replace_hal_observation(workspace):
    p = workspace / "software/tests/unit/test_iwdg_registers.cpp"
    p.write_text(p.read_text().replace("HAL_IWDG_Start()", "(LL_IWDG_Enable(IWDG), 0U)"))
    out = run(workspace)
    assert out["status"] == "FAIL"
    assert any("BUILD_FAIL:test_iwdg_registers.cpp" in i for i in out["issues"])


@pytest.mark.parametrize("fault", ["provided", "vendor", "symlink", "unsupported", "marker"])
def test_unbound_or_changed_inputs_refuse_before_test_execution(workspace, fault):
    ws = workspace
    if fault in ("provided", "vendor"):
        p = ws / ("software/ll/stm32n6xx_ll_iwdg.h" if fault == "provided" else "inputs/vendor/include/stm32n6xx.h")
        p.chmod(0o644)
        p.write_text(p.read_text() + "\n/* changed */\n")
    elif fault == "symlink":
        p = ws / "software/ll/stm32n6xx_ll_iwdg.h"
        raw = p.read_bytes()
        p.chmod(0o644)
        p.unlink()
        other = ws.parent / "other.h"
        other.write_bytes(raw)
        p.symlink_to(other)
    elif fault == "unsupported":
        p = ws / ".forge-run/manifest.json"
        man = json.loads(p.read_text())
        man["layer"] = "LL"
        p.write_text(json.dumps(man))
    else:
        p = ws / "software/tests/unit/test_iwdg_registers.cpp"
        p.write_text(p.read_text().replace(P.MARKER, P.MARKER + "-unknown"))
    # host_flags also independently refuses changed vendor inputs before building.
    if fault == "vendor":
        with pytest.raises(ValueError, match="PROVIDED_BUILD_INPUT_CHANGED"):
            run(ws)
    else:
        out = run(ws)
        assert out["status"] == "FAIL", out
        assert not (ws / "build/tests-unit").exists()


def test_removing_marker_retains_default_mock_semantics_and_fails_register_claim(workspace):
    p = workspace / "software/tests/unit/test_iwdg_registers.cpp"
    p.write_text(p.read_text().removeprefix(P.MARKER + "\n"))
    out = run(workspace)
    assert out["status"] == "FAIL"
    assert any("UT-002" in i for i in out["issues"])


def test_native_guidance_limits_exception_to_bound_hal_and_preserves_other_graphs():
    from forge_factory.workflow import prompts as Q
    old = Q.ASSESSMENT["manifest"]
    try:
        Q.ASSESSMENT["manifest"] = {"layer": "HAL", "hal_unit_isolation": "ll-fake-v1",
            "unit_verification": "uspec-gtest-v1", "provided_build": {"style": "cmsis"}, "provided": [{"path": "x"}]}
        note = Q.provided_ll_unit_note()
        assert P.MARKER in note and "Target-simulation timing" in note and "No LL calls" in note
        Q.ASSESSMENT["manifest"] = None
        assert Q.provided_ll_unit_note() == ""
    finally:
        Q.ASSESSMENT["manifest"] = old
