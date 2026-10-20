"""Owner request 2026-10-20 ("a watchdog HAL driver"): the HAL layer on a peripheral other than RCC.

* register contract `busy` (a status flag the oracle holds set): an IWDG HAL whose update wait is bounded returns
  HAL_TIMEOUT, and the oracle checks the final register values of HAL_IWDG_Init / HAL_IWDG_Refresh;
* the generated LL test double from the real i003 IWDG LL header, with the HAL unit-test example of the prompt."""
import json
import shutil
import subprocess

import pytest
from forge_factory.assurance import oracle_gen
from forge_factory.assurance import register_contract as RC
from forge_factory.common import REPO_ROOT
from forge_factory.peripheral import load
from forge_factory.workflow import ll_fake, scaffold
from test_peripheral_contract import _ws

I003_LL = REPO_ROOT / "evidence/v0.4/runs/PG-T012/i003/stm32n6xx_ll_iwdg.h"
LL = ("static inline void LL_IWDG_Enable(void)\n{\n    ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = 0x0000CCCCU;\n}\n"
      "static inline void LL_IWDG_ReloadCounter(void)\n{\n    ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = 0x0000AAAAU;\n}\n"
      "static inline void LL_IWDG_EnableWriteAccess(void)\n{\n    ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = 0x00005555U;\n}\n"
      "static inline void LL_IWDG_DisableWriteAccess(void)\n{\n    ll_iwdg_regs[LL_IWDG_KR_OFFSET / 4U] = 0x00000000U;\n}\n"
      "static inline void LL_IWDG_SetPrescaler(uint32_t prescaler)\n{\n"
      "    ll_iwdg_regs[LL_IWDG_PR_OFFSET / 4U] = (prescaler & LL_IWDG_PR_PR_MSK);\n}\n"
      "static inline void LL_IWDG_SetReloadCounter(uint32_t counter)\n{\n"
      "    ll_iwdg_regs[LL_IWDG_RLR_OFFSET / 4U] = (counter & LL_IWDG_RLR_RL_MSK);\n}\n"
      "static inline uint32_t LL_IWDG_IsActiveFlag_PVU(void)\n{\n"
      "    return ((ll_iwdg_regs[LL_IWDG_SR_OFFSET / 4U] & LL_IWDG_SR_PVU_MSK) != 0U) ? 1U : 0U;\n}\n"
      "static inline uint32_t LL_IWDG_IsActiveFlag_RVU(void)\n{\n"
      "    return ((ll_iwdg_regs[LL_IWDG_SR_OFFSET / 4U] & LL_IWDG_SR_RVU_MSK) != 0U) ? 1U : 0U;\n}\n")
HAL_H = """#ifndef STM32N6XX_HAL_IWDG_H
#define STM32N6XX_HAL_IWDG_H
#include <stddef.h>
#include "stm32n6xx_ll_iwdg.h"
typedef enum {HAL_OK = 0U, HAL_ERROR = 1U, HAL_TIMEOUT = 2U} hal_status_t;
#define HAL_IWDG_TIMEOUT_MS 48U
uint32_t HAL_GetTick(void);
typedef struct {uint32_t prescaler; uint32_t reload;} hal_iwdg_config_t;
hal_status_t HAL_IWDG_Init(const hal_iwdg_config_t *p_config, uint32_t timeout);
hal_status_t HAL_IWDG_Refresh(void);
#endif /* STM32N6XX_HAL_IWDG_H */
"""
CHECKS = ("    if ((p_config == NULL) || (timeout_ms == 0U) || (timeout_ms > HAL_IWDG_TIMEOUT_MS) ||\n"
          "        (p_config->prescaler > 7U) || (p_config->reload > 0xFFFU))\n    {\n        return HAL_ERROR;\n    }\n")


def _hal_c(example: str) -> str:
    body = example.replace("    uint32_t start;\n", "    uint32_t start;\n" + CHECKS, 1)
    return ('#include "stm32n6xx_hal_iwdg.h"\n\n' + body +
            "\n\nhal_status_t HAL_IWDG_Refresh(void)\n{\n    LL_IWDG_ReloadCounter();\n    return HAL_OK;\n}\n")


EXAMPLE = load("iwdg")["prompt"]["hal_example"]
REQ = ("- **SWR-001** When the watchdog initialisation is requested with a valid configuration, the IWDG driver shall "
       "write the configured prescaler to IWDG_PR.PR.\n"
       "- **SWR-002** When the watchdog initialisation is requested, the IWDG driver shall write the configured reload "
       "value to IWDG_RLR.RL.\n"
       "- **SWR-003** When the watchdog initialisation completes, the IWDG driver shall write 0xAAAA to IWDG_KR.KEY.\n"
       "- **SWR-004** If IWDG_SR.PVU is still set after the timeout, then the IWDG driver shall return HAL_TIMEOUT.\n"
       "- **SWR-005** If the configuration pointer is NULL, then the IWDG driver shall return HAL_ERROR.\n"
       "- **SWR-006** When a refresh is requested, the IWDG driver shall write 0xAAAA to IWDG_KR.KEY.\n")
CFG = "&(const hal_iwdg_config_t){ .prescaler = 4U, .reload = 0x0FFFU }"
EFFECTS = [
    {"case": "INIT_PRESCALER", "swr": "SWR-001", "register": "IWDG_PR", "field": "PR", "op": "write", "value": 4,
     "status": "HAL_OK"},
    {"case": "INIT_RELOAD", "swr": "SWR-002", "register": "IWDG_RLR", "field": "RL", "op": "write", "value": "0xFFF",
     "status": "HAL_OK"},
    {"case": "INIT_REFRESH", "swr": "SWR-003", "register": "IWDG_KR", "field": "KEY", "op": "write",
     "value": "0xAAAA", "status": "HAL_OK"},
    {"case": "INIT_TIMEOUT", "swr": "SWR-004", "register": "IWDG_KR", "field": "KEY", "op": "write", "value": "0x0000",
     "busy": "IWDG_SR.PVU", "status": "HAL_TIMEOUT"},  # FND-08: write-protected after a timeout
    {"case": "INIT_NULL", "swr": "SWR-005", "op": "no_write", "status": "HAL_ERROR"},
    {"case": "REFRESH", "swr": "SWR-006", "register": "IWDG_KR", "field": "KEY", "op": "write", "value": "0xAAAA",
     "status": "HAL_OK"}]
CALLS = {"INIT_PRESCALER": [CFG, "{timeout}"], "INIT_RELOAD": [CFG, "{timeout}"], "INIT_REFRESH": [CFG, "{timeout}"],
         "INIT_TIMEOUT": [CFG, "{timeout}"], "INIT_NULL": ["NULL", "{timeout}"]}


def _hal_ws(tmp_path, monkeypatch, hal_c: str):
    ws = _ws(tmp_path, monkeypatch, LL)
    (ws / "workproducts/SWE.1/software_requirements.md").write_text(REQ)
    (ws / "software/hal").mkdir(parents=True, exist_ok=True)
    (ws / "software/hal/stm32n6xx_hal_iwdg.h").write_text(HAL_H)
    (ws / "software/hal/stm32n6xx_hal_iwdg.c").write_text(hal_c)
    (ws / RC.EFFECTS).write_text(json.dumps({"schema": "forge-c/register-effects/1", "effects": EFFECTS}))
    (ws / RC.CALLS).write_text(json.dumps({"schema": "forge-c/api-calls/1", "calls": {
        k: {"function": "HAL_IWDG_Refresh" if k == "REFRESH" else "HAL_IWDG_Init", "args": CALLS.get(k, [])}
        for k in (e["case"] for e in EFFECTS)}}))
    return ws


def _oracle(ws):
    return oracle_gen.run(ws, [ws / "software/hal", ws / "software/ll"], [ws / "software/hal/stm32n6xx_hal_iwdg.c"],
                          "stm32n6xx_hal_iwdg.h")


def test_busy_contract_entries_are_validated(tmp_path, monkeypatch):
    ws = _hal_ws(tmp_path, monkeypatch, _hal_c(EXAMPLE))
    assert not [x for x in RC.check_effects(ws, "HAL") if "BUSY" in x or "NOT_IN_RM" in x or "WRITE_VALUE" in x]
    cs, notes = RC.cases(ws)
    busy = next(c for c in cs if c["case"] == "INIT_TIMEOUT")
    assert busy["busy"] == (0x0C // 4, 1 << 0) and not notes  # IWDG_SR at 0x0C, PVU bit 0
    eff = json.loads((ws / RC.EFFECTS).read_text())
    eff["effects"][3].update(busy="IWDG_SR.NOPE", status="HAL_OK")
    (ws / RC.EFFECTS).write_text(json.dumps(eff))
    issues = RC.check_effects(ws, "HAL")
    assert any(x.startswith("CONTRACT_BUSY_NOT_IN_RM:") for x in issues)
    assert any(x.startswith("CONTRACT_BUSY_CASE:") for x in issues)


def test_oracle_on_an_iwdg_hal(tmp_path, monkeypatch):
    r = _oracle(_hal_ws(tmp_path, monkeypatch, _hal_c(EXAMPLE)))
    assert r["status"] == "PASS", r
    no_refresh = _hal_c(EXAMPLE).replace("        LL_IWDG_ReloadCounter();\n", "", 1)
    assert no_refresh != _hal_c(EXAMPLE)
    r = _oracle(_hal_ws(tmp_path / "a", monkeypatch, no_refresh))
    assert r["status"] == "FAIL", r
    ignores_flags = _hal_c(EXAMPLE).replace("status = HAL_TIMEOUT;", "LL_IWDG_ReloadCounter();\n        status = HAL_OK;")
    assert ignores_flags != _hal_c(EXAMPLE)
    r = _oracle(_hal_ws(tmp_path / "b", monkeypatch, ignores_flags))
    assert r["status"] == "FAIL", r
    no_protect = _hal_c(EXAMPLE).replace("        LL_IWDG_DisableWriteAccess();\n", "", 1)  # FND-08 regression
    assert no_protect != _hal_c(EXAMPLE)
    r = _oracle(_hal_ws(tmp_path / "c", monkeypatch, no_protect))
    assert r["status"] == "FAIL", r


@pytest.mark.skipif(not shutil.which("gcc"), reason="gcc not available")
def test_ll_fake_from_the_i003_iwdg_header_runs_the_prompt_example(tmp_path):
    fake = ll_fake.generate(I003_LL.read_text(), "ll_iwdg_regs")
    assert "ll_iwdg_regs[" not in fake.split("test double API")[1]  # no register array: the LL API only
    for fn in ("LL_IWDG_SetPrescaler", "LL_IWDG_IsActiveFlag_PVU", "LL_IWDG_ReloadCounter"):
        assert f"LL_FAKE_{fn}," in fake
    d = tmp_path / "fake"
    d.mkdir()
    (d / "stm32n6xx_ll_iwdg.h").write_text(fake)
    (tmp_path / "stm32n6xx_hal_iwdg.h").write_text(HAL_H)
    (tmp_path / "hal.c").write_text(_hal_c(EXAMPLE))
    pr = load("iwdg")
    iw = tmp_path / "iw"
    (iw / ".forge-run").mkdir(parents=True)
    (iw / ".forge-run/manifest.json").write_text('{"layer": "HAL", "peripheral": "iwdg"}')
    harness = scaffold._time_base(scaffold._for_peripheral(scaffold.HARNESS_FAKE, iw), iw)  # FND-07: HAL_GetTick stub
    assert "uint32_t HAL_GetTick(void)" in harness and "ut_tick = 0U;" in harness
    test = harness.replace(scaffold.TEST_CASES_MARKER, pr["prompt"]["hal_ut_example"]).replace(
        scaffold.TEST_CALLS_MARKER, "ut_iwdg_init();")
    (tmp_path / "test_iwdg.c").write_text(test)
    exe = tmp_path / "ut"
    b = subprocess.run(["gcc", "-std=c99", "-Wall", f"-I{d}", f"-I{tmp_path}", str(tmp_path / "test_iwdg.c"),
                        str(tmp_path / "hal.c"), "-o", str(exe)], capture_output=True, text=True)
    assert b.returncode == 0, b.stderr[-2000:]
    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0 and "FAIL" not in r.stdout and r.stdout.count("PASS") == 7, r.stdout


def test_fake_header_and_provided_ll_follow_the_profile(tmp_path):
    from forge_factory import workorder as WO

    (tmp_path / ".forge-run").mkdir()
    (tmp_path / ".forge-run/manifest.json").write_text(json.dumps({"layer": "HAL", "peripheral": "iwdg"}))
    assert ll_fake.fake_header(tmp_path) == "software/tests/unit/ll_fake/stm32n6xx_ll_iwdg.h"
    assert ll_fake.fake_header(None) == ll_fake.FAKE_HEADER  # RCC unchanged
    with pytest.raises(FileNotFoundError, match="PROVIDED_LL_MISSING"):
        WO.provided_ll("WO-DOES-NOT-EXIST", "iwdg")
