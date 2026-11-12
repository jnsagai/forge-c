"""Executed argument-history controls; default v1 output and permissions stay unchanged."""
import hashlib
import json
import subprocess

import pytest
from forge_factory import workorder as W
from forge_factory.common import sha256_file
from forge_factory.mcp.servers import tests as T
from forge_factory.workflow import ll_call_arguments as H
from forge_factory.workflow import ll_fake
from forge_factory.workflow import scaffold as SC
from test_capa128_hal_on_st_ll import (
    _ctx,
    _iwdg_hal_example,
    _source_ll,
    env,  # noqa: F401 - shared fixture
)

HEADER = '''#ifndef ARGUMENT_CONTROL_H
#define ARGUMENT_CONTROL_H
#include <stdint.h>
typedef struct { uint32_t CR; } Device;
#define __STATIC_INLINE static inline
#define SET_BIT(R,M) ((R) |= (M))
#define READ_BIT(R,M) ((R) & (M))
__STATIC_INLINE void LL_Control_Feed(Device *instance, uint32_t value)
{ (void)instance; (void)value; }
__STATIC_INLINE void LL_Control_Enable(Device *instance)
{ SET_BIT(instance->CR, 1U); }
__STATIC_INLINE uint32_t LL_Control_IsEnabled(Device *instance, uint32_t tag)
{ (void)tag; return READ_BIT(instance->CR, 1U); }
__STATIC_INLINE void LL_Control_Three(Device *instance, uint32_t a, uint32_t b, uint32_t c)
{ (void)instance; (void)a; (void)b; (void)c; }
#endif
'''


@pytest.mark.parametrize("declaration", ["WordPtr value", "uint32_t value[2]", "uint64_t value"])
def test_unsupported_alias_array_and_wide_arguments_refuse_history(declaration):
    text = ("#include <stdint.h>\ntypedef uint32_t *WordPtr;\n"
            f"static inline void LL_Alias({declaration}) {{ (void)value; }}\n")
    with pytest.raises(ValueError, match="LL_FAKE_HISTORY_ARGUMENT_TYPE_UNSUPPORTED:LL_Alias"):
        ll_fake.generate(text, argument_history=True)


def execute(tmp_path, body):
    header = tmp_path / "control.h"
    header.write_text(ll_fake.generate(HEADER, argument_history=True))
    source = tmp_path / "control.c"
    source.write_text('#define LL_FAKE_IMPLEMENTATION\n#include "control.h"\n'
                      '#define CHECK(C) do { if (!(C)) { return __LINE__; } } while (0)\n'
                      'int main(void) { Device device = {0U}; uint32_t value = 0xA5A5A5A5U; '
                      'll_fake_reset();\n' + body + '\nreturn 0; }\n')
    binary = tmp_path / "control"
    compiled = subprocess.run(["clang", "-std=c11", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(binary)],
                              capture_output=True, text=True)
    assert compiled.returncode == 0, compiled.stderr[-2000:]
    result = subprocess.run([str(binary)], capture_output=True)
    assert result.returncode == 0, result.returncode


def test_default_fake_remains_byte_identical():
    from test_capa038_ll_fake import LL

    assert hashlib.sha256(ll_fake.generate(LL).encode()).hexdigest() == \
        "c383e2ab7680fdc25c6e23690ce2c6a76a8d036940e2092f9716cb5c343b1c6c"


def test_every_value_and_occurrence_is_observed_in_order(tmp_path):
    execute(tmp_path, '''for (uint32_t i = 0U; i < 64U; i++) { LL_Control_Feed(&device, 1000U + i); }
for (uint32_t i = 0U; i < 64U; i++) {
 CHECK(ll_fake_call_arg(LL_FAKE_LL_Control_Feed, i + 1U, 0U, &value) == 1U);
 CHECK(value == 1000U + i);
 CHECK(ll_fake_index_of(LL_FAKE_LL_Control_Feed, i + 1U) == (int32_t)i);
}
CHECK(ll_fake_last_arg(LL_FAKE_LL_Control_Feed, 0U) == 1063U);
''')


def test_unobserved_arguments_never_supply_a_synthetic_zero(tmp_path):
    execute(tmp_path, '''LL_Control_Feed(&device, 7U); LL_Control_Enable(&device);
CHECK(ll_fake_call_arg(LL_FAKE_COUNT,1U,0U,&value) == 0U);
CHECK(ll_fake_call_arg((ll_fake_fn_t)-1,1U,0U,&value) == 0U);
CHECK(ll_fake_call_arg(LL_FAKE_LL_Control_Feed,0U,0U,&value) == 0U);
CHECK(ll_fake_call_arg(LL_FAKE_LL_Control_Feed,2U,0U,&value) == 0U);
CHECK(ll_fake_call_arg(LL_FAKE_LL_Control_Feed,1U,1U,&value) == 0U);
CHECK(ll_fake_call_arg(LL_FAKE_LL_Control_Enable,1U,0U,&value) == 0U);
CHECK(ll_fake_call_arg(LL_FAKE_LL_Control_Feed,1U,0U,(uint32_t *)0) == 0U);
CHECK(value == 0xA5A5A5A5U);
LL_Control_Three(&device, 11U, 12U, 13U);
CHECK(ll_fake_call_arg(LL_FAKE_LL_Control_Three,1U,2U,&value) == 0U);
CHECK(ll_fake_call_arg(LL_FAKE_LL_Control_Three,1U,1U,&value) == 1U && value == 12U);
''')


def test_state_query_records_actual_scalar_instead_of_a_fabricated_zero(tmp_path):
    execute(tmp_path, '''LL_Control_Enable(&device);
CHECK(LL_Control_IsEnabled(&device, 37U) == 1U);
CHECK(ll_fake_call_arg(LL_FAKE_LL_Control_IsEnabled,1U,0U,&value) == 1U && value == 37U);
''')


def test_overflow_and_reset_cannot_reuse_old_history(tmp_path):
    execute(tmp_path, f'''for (uint32_t i = 0U; i <= {ll_fake.LOG_CAPACITY}U; i++) {{ LL_Control_Feed(&device, i); }}
CHECK(ll_fake_call_arg(LL_FAKE_LL_Control_Feed,1U,0U,&value) == 0U);
ll_fake_reset();
CHECK(ll_fake_call_arg(LL_FAKE_LL_Control_Feed,1U,0U,&value) == 0U);
LL_Control_Feed(&device, 29U);
CHECK(ll_fake_call_arg(LL_FAKE_LL_Control_Feed,1U,0U,&value) == 1U && value == 29U);
CHECK(ll_fake_call_arg(LL_FAKE_LL_Control_Feed,2U,0U,&value) == 0U);
''')


@pytest.fixture
def workspace(env):  # noqa: F811 - shared fixture
    _source_ll(env / "state")
    ws, _ = W.prepare(_iwdg_hal_example(env), "WO-HISTORY-CONTROL", "WO-LL-ST")
    ll = ws / "software/ll/stm32n6xx_ll_iwdg.h"
    ll.chmod(0o644)
    ll.write_text(ll.read_text() + '\n__STATIC_INLINE void LL_IWDG_Feed(IWDG_TypeDef *IWDGx, uint32_t value)\n'
                  '{ WRITE_REG(IWDGx->KR, value); }\n')
    manifest = ws / ".forge-run/manifest.json"
    man = json.loads(manifest.read_text())
    man["provided"][0]["sha256"] = sha256_file(ll)
    manifest.write_text(json.dumps(man))
    ll_fake.write(ws)
    hal = ws / "software/hal"
    hal.mkdir(parents=True, exist_ok=True)
    (hal / "stm32n6xx_hal_iwdg.h").write_text('#include "stm32n6xx_ll_iwdg.h"\n'
        'void HAL_IWDG_Feed(const uint32_t *data, uint32_t count);\n')
    (hal / "stm32n6xx_hal_iwdg.c").write_text('#include "stm32n6xx_hal_iwdg.h"\n'
        'void HAL_IWDG_Feed(const uint32_t *data, uint32_t count) { '
        'for (uint32_t i=0U; i<count; i++) { LL_IWDG_Feed(IWDG, data[i]); } }\n')
    SC._scaffold(ws)
    test = ws / SC.unit_test(ws)
    body = '''/** @test UT-001 @verifies USPEC-HAL-01-01 */
TEST(CallArguments, UT_001) {
 ut_reset(); const uint32_t data[] = {19U, 3U, 71U, 5U}; HAL_IWDG_Feed(data, 4U);
 for(uint32_t i=0U;i<4U;i++) { uint32_t observed=0U;
  ASSERT_EQ(ll_fake_call_arg(LL_FAKE_LL_IWDG_Feed,i+1U,0U,&observed),1U);
  EXPECT_EQ(observed,data[i]); EXPECT_EQ(ll_fake_index_of(LL_FAKE_LL_IWDG_Feed,i+1U),(int32_t)i);
 }
}
'''
    test.write_text(H.MARKER + "\n" + test.read_text().replace(SC.TEST_CASES_MARKER, body + SC.TEST_CASES_MARKER))
    return ws


def run(ws):
    return T.run_unit(_ctx(ws,"forge-tests-mcp","run_unit","swe4-author","SWE.4"), T.RunIn(coverage=True))


def test_public_unit_operation_compiles_both_units_against_same_private_history(workspace):
    ws = workspace
    protected = ws / ll_fake.fake_header(ws)
    before = protected.read_bytes()
    result = run(ws)
    assert result["status"] == "PASS", result
    assert protected.read_bytes() == before and not ll_fake.modified(ws)
    binding = json.loads(next((ws / "build/tests-unit").glob("*.ll-call-arguments/binding.json")).read_text())
    assert binding["original_fake_sha256"] == sha256_file(protected)
    assert binding["target_or_register_effect_claim"] is False
    cov = T.llvm_coverage(_ctx(ws,"forge-tests-mcp","llvm_coverage","swe4-author","SWE.4"), T.CovIn())
    assert cov["status"] == "PASS", cov


@pytest.mark.parametrize("replacement", ["data[count-1U-i]", "data[count-1U]"])
def test_wrong_order_or_repeating_only_last_word_fails_genuine_history(workspace, replacement):
    source = workspace / "software/hal/stm32n6xx_hal_iwdg.c"
    source.write_text(source.read_text().replace("data[i]", replacement))
    result = run(workspace)
    assert result["status"] == "FAIL" and any("GTEST_FAIL:" in i for i in result["issues"])


def test_default_and_history_executables_share_real_driver_coverage_without_changing_v1(workspace):
    path = workspace / "software/tests/unit/test_default.cpp"
    path.write_text('#include <gtest/gtest.h>\nextern "C" {\n#include "stm32n6xx_hal_iwdg.h"\n}\n'
        '/** @test UT-002 @verifies USPEC-HAL-01-02 */\nTEST(DefaultBackend, UT_002) { '
        'll_fake_reset(); const uint32_t data[]={17U}; HAL_IWDG_Feed(data,1U); '
        'EXPECT_EQ(ll_fake_calls(LL_FAKE_LL_IWDG_Feed),1U); '
        'EXPECT_EQ(ll_fake_last_arg(LL_FAKE_LL_IWDG_Feed,0U),17U); }\n')
    out = run(workspace)
    assert out["status"] == "PASS", out
    backends = json.loads((workspace / "build/tests-unit/results.json").read_text())["backends"]
    assert backends[path.name] == "default" and backends["test_iwdg.cpp"] == "ll-call-arguments-v1"
    coverage = T.llvm_coverage(_ctx(workspace,"forge-tests-mcp","llvm_coverage","swe4-author","SWE.4"), T.CovIn())
    assert coverage["status"] == "PASS" and coverage["metrics"]["line_pct"] == 100.0, coverage
