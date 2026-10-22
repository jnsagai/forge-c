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
