"""Feature 010 P4: structured SWE.5 (LL) with a scripted model on top of the structured SWE.1-SWE.4: target programs on
the real Renode model, the host integration program, the deterministic report and the unchanged SWE.5 gate."""
from __future__ import annotations

import pytest
from forge_factory.lrtx import structured as S
from forge_factory.lrtx import swe4, swe5
from test_lrtx_swe1 import _scripted, pytestmark, ws  # noqa: F401 - fixture and owner-input precondition
from test_lrtx_swe2 import ws1  # noqa: F401 - fixture
from test_lrtx_swe3 import TOOLS, _gate, ws2  # noqa: F401 - fixture
from test_lrtx_swe4 import TESTS, ws3  # noqa: F401 - fixture

pytestmark = [pytestmark, pytest.mark.skipif(not TOOLS, reason="build tools not installed")]

TARGET = """/** @file test_iwdg_target.c @verifies IF-01 IF-02 */
#include "stm32n6xx_ll_iwdg.h"
#include "forge_target_test.h"

FORGE_MAILBOX_DEFINE;

int main(void)
{
    FORGE_TEST_BEGIN();
    LL_IWDG_EnableWriteAccess();
    LL_IWDG_SetPrescaler(4U);
    TCHECK(1, (ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U] & LL_IWDG_PR_PR_MSK) == 4U);
    LL_IWDG_Enable();
    TCHECK(2, LL_IWDG_IsActive() == 1U);
    FORGE_TEST_END();
    return 0;
}
"""
TIMEOUT = """/** @file test_iwdg_target_timeout.c @verifies IF-01 IF-02 */
#include "stm32n6xx_ll_iwdg.h"
#include "forge_target_test.h"

FORGE_MAILBOX_DEFINE;

int main(void)
{
    uint32_t i = 0U;
    uint32_t busy = 1U;
    FORGE_TEST_BEGIN();
    LL_IWDG_EnableWriteAccess();
    LL_IWDG_SetPrescaler(4U);
    while ((i < 1000U) && (busy == 1U))
    {
        busy = LL_IWDG_IsActiveFlag_PVU();
        i++;
    }
    TCHECK(1, busy == 1U);
    FORGE_TEST_END();
    return 0;
}
"""
INTEGRATION = """#include <stdio.h>
#include <stdint.h>
#include "stm32n6xx_ll_iwdg.h"

volatile uint32_t ll_iwdg_regs[LL_IWDG_REG_COUNT];
static int failures = 0;
#define CHECK(id, cond) do { if (cond) { printf("%s PASS\\n", (id)); } else { printf("%s FAIL\\n", (id)); \\
    failures++; } } while (0)

/** @test IT-001 @verifies IF-01 IF-02 SWC_LL */
static void it_start_sequence(void)
{
    LL_IWDG_EnableWriteAccess();
    LL_IWDG_SetPrescaler(4U);
    LL_IWDG_Enable();
    CHECK("IT-001", ((ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U] & LL_IWDG_PR_PR_MSK) == 4U) &&
          ((ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] & LL_IWDG_KR_KEY_MSK) == 0xCCCCU));
}

int main(void)
{
    uint32_t i;
    for (i = 0U; i < LL_IWDG_REG_COUNT; i++)
    {
        ll_iwdg_regs[i] = 0U;
    }
    it_start_sequence();
    return (failures == 0) ? 0 : 1;
}
"""
FILES = {"file:target": {"code": TARGET}, "file:target_timeout": {"code": TIMEOUT},
         "file:integration": {"code": INTEGRATION}}


def test_opt_in_performance_stimulus_uses_existing_swe5_authority_and_real_observer(ws3, monkeypatch):  # noqa: F811
    import json
    import re

    from forge_factory import simulation_performance as performance
    from forge_factory.lrtx import tools
    from forge_factory.policy.authz import Authorizer, Binding

    monkeypatch.setattr(S, "call", _scripted(TESTS, []))
    assert swe4.visit(ws3, "m")["status"] == "PASS" and _gate(ws3, "SWE.4", monkeypatch) == 0
    path = ws3 / ".forge-run/manifest.json"
    manifest = json.loads(path.read_text())
    manifest[performance.FIELD] = {"schema": performance.SCHEMA, "instructions_per_call": 64,
                                   "microseconds_per_call": 100, "performance_mips": 100,
                                   "test_source": performance.TEST}
    path.write_text(json.dumps(manifest))  # Synthetic prospective allocation; not an owner review.
    text = '''/** @file test_performance.c @verifies IF-01 IF-02 */
#include "stm32n6xx_ll_iwdg.h"
#include "forge_performance_calls.h"
#include "forge_target_test.h"
FORGE_MAILBOX_DEFINE;
int main(void) {
 FORGE_TEST_BEGIN();
 forge_measure_LL_IWDG_EnableWriteAccess();
 forge_measure_LL_IWDG_SetPrescaler(4U);
 forge_measure_LL_IWDG_SetReloadCounter(5U);
 TCHECK(1, forge_measure_LL_IWDG_IsActiveFlag_PVU() == 1U);
 TCHECK(2, forge_measure_LL_IWDG_IsActiveFlag_RVU() == 0U);
 forge_measure_LL_IWDG_Enable();
 forge_measure_LL_IWDG_ReloadCounter();
 forge_measure_LL_IWDG_DisableWriteAccess();
 TCHECK(3, forge_measure_LL_IWDG_IsActive() == 1U);
 FORGE_TEST_END(); return 0;
}
'''
    assert set(re.findall(r"\b(forge_measure_\w+)\(", text)) == set(performance.symbols(ws3))
    assert swe5.validate_file(ws3, "target_performance", {"code": text}) == []
    missing = text.replace("forge_measure_LL_IWDG_ReloadCounter();", "/* forge_measure_LL_IWDG_ReloadCounter(); */")
    assert "missing measurement call forge_measure_LL_IWDG_ReloadCounter" in swe5.validate_file(
        ws3, "target_performance", {"code": missing})
    authorizer = Authorizer(Binding.load(ws3 / ".forge-run/binding.json"))
    assert authorizer.decide("swe5_target_author", "write_file", {"path": performance.TEST, "content": ""}).allow
    assert not authorizer.decide("swe6_test_author", "write_file", {"path": performance.TEST, "content": ""}).allow
    observed = []
    actual_call = tools.call

    def capture(*args, **kwargs):
        result = actual_call(*args, **kwargs)
        if args[2] == "run_renode":
            observed.append(result)
            assert result["status"] == "PASS", result["issues"]
        return result

    monkeypatch.setattr(tools, "call", capture)
    calls = []
    monkeypatch.setattr(S, "call", _scripted({**FILES, "file:target_performance": {"code": text}}, calls))
    result = swe5.visit_tests(ws3, "m")
    assert result["status"] == "PASS", result
    assert len(calls) == 4 and (ws3 / performance.TEST).read_text() == text
    assert any(a["path"] == "simulation-performance-contract" for a in calls[-1]["artifacts"])
    assert performance.verify_result(ws3, observed[-1])["status"] == "PASS"
    assert swe5.visit_report(ws3)["status"] == "PASS"
    assert _gate(ws3, "SWE.5", monkeypatch) == 0


def test_structured_swe5_passes_renode_integration_and_the_unchanged_gate(ws3, monkeypatch):  # noqa: F811
    monkeypatch.setattr(S, "call", _scripted(TESTS, []))
    assert swe4.visit(ws3, "m")["status"] == "PASS" and _gate(ws3, "SWE.4", monkeypatch) == 0
    calls = []
    monkeypatch.setattr(S, "call", _scripted(FILES, calls))
    rep = swe5.visit(ws3, "m")
    assert rep["status"] == "PASS", rep
    rpt = (ws3 / "workproducts/SWE.5/integration_verification_report.md").read_text()
    assert "run_renode (simulated target): status PASS" in rpt and "## Scope exclusions" in rpt
    assert _gate(ws3, "SWE.5", monkeypatch) == 0
    assert all("= 0x0000CCCCU;" not in str(p["_messages"]) for p in calls)  # the implementation is never shown


def test_target_file_validation(ws3):  # noqa: F811
    bad = TARGET.replace("TCHECK(2,", "TCHECK(1,").replace("FORGE_MAILBOX_DEFINE;", "").replace("IF-02", "IF-07")
    found = " ".join(swe5.validate_file(ws3, "target", {"code": bad}))
    for frag in ("TCHECK number 1 is used twice", "missing the FORGE_MAILBOX_DEFINE; line",
                 "IF-07, which is not an interface"):
        assert frag in found, (frag, found)
