"""Feature 009 slice E (PG-T010): the IWDG Renode model (key-protected PR/RLR writes, PVU/RVU update flags, start
sets ONF; scenario never_ready keeps the update flags) selected from the work order's profile."""
import pytest
from forge_factory import workorder as WO
from forge_factory.common import REPO_ROOT
from forge_factory.mcp.servers import sim

pytestmark = pytest.mark.skipif(sim.renode_bin() is None, reason="Renode not installed")
LL = """
static inline void LL_IWDG_EnableWriteAccess(void) { ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = 0x00005555U; }
static inline void LL_IWDG_SetPrescaler(uint32_t p) { ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U] = (p & LL_IWDG_PR_PR_MSK); }
static inline uint32_t LL_IWDG_IsActiveFlag_PVU(void)
{ return ((ll_iwdg_regs[LL_IWDG_SR_OFFSET / 4U] & LL_IWDG_SR_PVU_MSK) != 0U) ? 1U : 0U; }
static inline void LL_IWDG_Enable(void) { ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = 0x0000CCCCU; }
static inline uint32_t LL_IWDG_IsActive(void)
{ return ((ll_iwdg_regs[LL_IWDG_SR_OFFSET / 4U] & LL_IWDG_SR_ONF_MSK) != 0U) ? 1U : 0U; }
"""
TEST = """#include "stm32n6xx_ll_iwdg.h"
#include "forge_target_test.h"
FORGE_MAILBOX_DEFINE;
int main(void) { FORGE_TEST_BEGIN();
  LL_IWDG_SetPrescaler(4U);
  TCHECK(1, (ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U] & LL_IWDG_PR_PR_MSK) == 0U);
  LL_IWDG_EnableWriteAccess(); LL_IWDG_SetPrescaler(4U);
  TCHECK(2, (ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U] & LL_IWDG_PR_PR_MSK) == 4U);
  { uint32_t n = 0U; uint32_t f = 1U; while ((n < 1000U) && (f != 0U)) { f = LL_IWDG_IsActiveFlag_PVU(); n++; }
    TCHECK(3, %s); }
  LL_IWDG_Enable();
  TCHECK(4, LL_IWDG_IsActive() == 1U);
  FORGE_TEST_END(); return 0; }
"""


def test_iwdg_model_on_renode(tmp_path, monkeypatch):
    from forge_factory.inspection import regmap

    monkeypatch.setenv("FORGE_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("FORGE_EVENTS_DIR", str(tmp_path / "state/events"))
    ws, _ = WO.prepare(REPO_ROOT / "examples/0009a-iwdg-ll", "WO-IWDG-S")
    (ws / "workproducts/SWE.2").mkdir(parents=True)
    (ws / "workproducts/SWE.2/software_architecture.md").write_text(
        "## Register table\n\n| Register | Offset |\n|---|---|\n| IWDG_KR | 0x000 |\n| IWDG_PR | 0x004 |\n"
        "| IWDG_RLR | 0x008 |\n| IWDG_SR | 0x00C |\n")
    regmap.generate(ws)
    h = ws / "software/ll/stm32n6xx_ll_iwdg.h"
    h.write_text(h.read_text().replace(regmap.functions_marker(ws), regmap.functions_marker(ws) + LL))
    t = ws / "software/tests/target"
    t.mkdir(parents=True)
    for name, cond, scen in (("test_iwdg_target.c", "f == 0U", "default"),
                             ("test_iwdg_target_timeout.c", "f == 1U", "never_ready")):
        (t / name).write_text(TEST % cond)
        ok, _log, errs = sim.build_image(ws, t / name, tmp_path / f"{name}.elf")
        assert ok, errs
        res, _out = sim.run_image(sim.renode_bin(), tmp_path / f"{name}.elf", scen, tmp_path, ws)
        assert res == {"magic_ok": True, "passed": 4, "failed": 0, "done": True, "failed_ids": []}, (name, res)
    assert (tmp_path / "link_iwdg.ld").read_text().count("ll_iwdg_regs = 0x56004800;") == 1
