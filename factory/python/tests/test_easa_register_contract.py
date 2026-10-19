"""Owner decision 2026-10-19 (option B): the independent oracle reads a machine-readable register contract (SWE.1
effects + SWE.2 calls) and the RM, never the code. r149: the sentence-parsing oracle skipped every pointer-argument API
and missed 4 of 6 seeded defects."""
import json
import shutil

import pytest
from forge_factory.assurance import oracle_gen
from forge_factory.assurance import register_contract as RC
from forge_factory.assurance import verifiers as V
from test_easa_m3_m4 import CR, SR

needs_cc = pytest.mark.skipif(not shutil.which("gcc"), reason="gcc not installed")
REQS = """- **SWR-001** When HSE enable is requested with valid parameters, the RCC driver shall set RCC_CR.HSEON and return HAL_OK when RCC_SR.HSERDY becomes 1.
- **SWR-002** When the HSE ready flag does not set within the timeout, the RCC driver shall clear RCC_CR.HSEON and return HAL_TIMEOUT.
- **SWR-003** When a NULL configuration pointer is supplied, the RCC driver shall return HAL_ERROR without any register write.
"""
ARCH = ("| SWR | Function |\n|---|---|\n| SWR-001 | HAL_RCC_HSE_Enable |\n| SWR-002 | HAL_RCC_HSE_Enable |\n"
        "| SWR-003 | HAL_RCC_HSE_Enable |\n")
EFFECTS = {"schema": "forge-c/register-effects/1", "effects": [
    {"case": "HSE_ENABLE", "swr": "SWR-001", "register": "RCC_CR", "field": "HSEON", "op": "set",
     "ready": "RCC_SR.HSERDY", "status": "HAL_OK"},
    {"case": "HSE_TIMEOUT", "swr": "SWR-002", "register": "RCC_CR", "field": "HSEON", "op": "clear", "ready": "never",
     "status": "HAL_TIMEOUT"},
    {"case": "HSE_NULL", "swr": "SWR-003", "op": "no_write", "status": "HAL_ERROR"}]}
CFG = "&(const hal_rcc_osc_config_t){ .oscillator = HAL_RCC_OSC_HSE }"
CALLS = {"schema": "forge-c/api-calls/1", "calls": {
    "HSE_ENABLE": {"function": "HAL_RCC_HSE_Enable", "args": [CFG, "{timeout}"]},
    "HSE_TIMEOUT": {"function": "HAL_RCC_HSE_Enable", "args": [CFG, "{timeout}"]},
    "HSE_NULL": {"function": "HAL_RCC_HSE_Enable", "args": ["NULL", "{timeout}"]}}}
LL = """#ifndef STM32N6XX_LL_RCC_H
#define STM32N6XX_LL_RCC_H
#include <stdint.h>
#define LL_RCC_REG_COUNT 1024U
extern volatile uint32_t ll_rcc_regs[LL_RCC_REG_COUNT];
#define LL_RCC_CR_OFFSET 0x000U
#define LL_RCC_SR_OFFSET 0x004U
#define LL_RCC_CR_HSION_MSK 0x00000008U
#define LL_RCC_CR_HSEON_MSK 0x00000010U
#define LL_RCC_SR_HSERDY_MSK 0x00000010U
static inline void LL_RCC_HSI_Enable(void) { ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= LL_RCC_CR_HSION_MSK; }
static inline void LL_RCC_HSE_Enable(void) { ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] |= LL_RCC_CR_HSEON_MSK; }
static inline void LL_RCC_HSE_Disable(void) { ll_rcc_regs[LL_RCC_CR_OFFSET / 4U] &= ~LL_RCC_CR_HSEON_MSK; }
static inline uint32_t LL_RCC_HSE_IsReady(void)
{ return ((ll_rcc_regs[LL_RCC_SR_OFFSET / 4U] & LL_RCC_SR_HSERDY_MSK) != 0U) ? 1U : 0U; }
#endif
"""
HAL_H = """#ifndef STM32N6XX_HAL_RCC_H
#define STM32N6XX_HAL_RCC_H
#include "stm32n6xx_ll_rcc.h"
typedef enum {HAL_OK=0U,HAL_ERROR=1U,HAL_TIMEOUT=2U} hal_status_t;
#define HAL_RCC_TIMEOUT_VALUE 1000U
typedef enum { HAL_RCC_OSC_HSI = 0, HAL_RCC_OSC_HSE = 1 } hal_rcc_oscillator_t;
typedef struct { hal_rcc_oscillator_t oscillator; } hal_rcc_osc_config_t;
hal_status_t HAL_RCC_HSE_Enable(const hal_rcc_osc_config_t *config, uint32_t timeout);
#endif
"""
HAL_C = """#include <stddef.h>
#include "stm32n6xx_hal_rcc.h"
hal_status_t HAL_RCC_HSE_Enable(const hal_rcc_osc_config_t *config, uint32_t timeout)
{
    hal_status_t status = HAL_TIMEOUT;
    uint32_t count = 0U;
    if ((config == NULL) || (config->oscillator != HAL_RCC_OSC_HSE) || (timeout == 0U)) { return HAL_ERROR; }
    LL_RCC_HSE_Enable();
    while ((count < timeout) && (status != HAL_OK))
    {
        if (LL_RCC_HSE_IsReady() != 0U) { status = HAL_OK; } else { count++; }
    }
    if (status != HAL_OK) { LL_RCC_HSE_Disable(); }
    return status;
}
"""


@pytest.fixture()
def ws(tmp_path):
    w = tmp_path / "WO" / "workspace"
    files = {"workproducts/SWE.1/software_requirements.md": REQS, "workproducts/SWE.2/software_architecture.md": ARCH,
             RC.EFFECTS: json.dumps(EFFECTS), RC.CALLS: json.dumps(CALLS),
             "inputs/sections/RM0486/14.10.1_RCC_CR.md": CR, "inputs/sections/RM0486/14.10.2_RCC_SR.md": SR,
             "software/ll/stm32n6xx_ll_rcc.h": LL, "software/hal/stm32n6xx_hal_rcc.h": HAL_H,
             "software/hal/stm32n6xx_hal_rcc.c": HAL_C,
             ".forge-run/manifest.json": json.dumps({"layer": "HAL", "register_contract": "rc-v1"})}
    for rel, text in files.items():
        (w / rel).parent.mkdir(parents=True, exist_ok=True)
        (w / rel).write_text(text)
    return w


def _write(ws, rel, doc):
    (ws / rel).write_text(json.dumps(doc))


def test_valid_contract_passes_all_three_gates(ws):
    assert RC.enabled(ws)
    assert RC.check_effects(ws) == [] and RC.check_calls(ws) == []
    assert RC.check_compiles(ws, [ws / "software/hal", ws / "software/ll"], "stm32n6xx_hal_rcc.h") == []


def test_gates_reject_a_contract_that_drifts_from_the_requirements_rm_or_allocation(ws):
    bad = json.loads(json.dumps(EFFECTS))
    bad["effects"][0]["field"] = "HSION"                                # not named by SWR-001
    bad["effects"][1]["field"] = "NOPE"                                 # not in the RM
    bad["effects"].pop(2)                                               # SWR-003 has no register bit: fine
    _write(ws, RC.EFFECTS, bad)
    f = RC.check_effects(ws)
    assert any(x.startswith("CONTRACT_FIELD_NOT_IN_SWR:") and "HSE_ENABLE" in x for x in f)
    assert any(x.startswith("CONTRACT_NOT_IN_RM:") and "HSE_TIMEOUT" in x for x in f)
    _write(ws, RC.EFFECTS, {"schema": "forge-c/register-effects/1", "effects": [EFFECTS["effects"][2]]})
    assert {x.split(":")[0] for x in RC.check_effects(ws)} == {"CONTRACT_SWR_NOT_COVERED"}
    calls = json.loads(json.dumps(CALLS))
    calls["calls"]["HSE_ENABLE"]["function"] = "HAL_RCC_HSI_Enable"
    calls["calls"]["HSE_TIMEOUT"]["args"] = ["make_cfg()", "{timeout}"]
    _write(ws, RC.EFFECTS, EFFECTS)
    _write(ws, RC.CALLS, calls)
    f = RC.check_calls(ws)
    assert any(x.startswith("CONTRACT_FUNCTION_NOT_ALLOCATED:") for x in f)
    assert any(x.startswith("CONTRACT_UNSAFE_ARGS:") for x in f)
    _write(ws, RC.CALLS, CALLS)
    (ws / "software/hal/stm32n6xx_hal_rcc.h").write_text(HAL_H.replace("osc_config_t", "oscillator_config_t"))
    assert RC.check_compiles(ws, [ws / "software/hal", ws / "software/ll"], "stm32n6xx_hal_rcc.h")[0].startswith(
        "CONTRACT_CALL_DOES_NOT_COMPILE")


@needs_cc
@pytest.mark.parametrize("seed,old,new", [
    (None, "", ""),
    ("swapped oscillator", "LL_RCC_HSE_Enable();", "LL_RCC_HSI_Enable();"),
    ("no rollback", "    if (status != HAL_OK) { LL_RCC_HSE_Disable(); }\n", ""),
    ("missing NULL check", "(config == NULL) || ", ""),
])
def test_contract_oracle_runs_on_pointer_apis_and_catches_seeded_defects(ws, seed, old, new):
    if seed:
        p = ws / "software/hal/stm32n6xx_hal_rcc.c"
        p.write_text(p.read_text().replace(old, new, 1))
    r = oracle_gen.run(ws, [ws / "software/hal", ws / "software/ll"], [ws / "software/hal/stm32n6xx_hal_rcc.c"],
                       "stm32n6xx_hal_rcc.h")
    assert r["provenance"]["independence_status"] == "INDEPENDENT", r["provenance"]
    assert len(r["provenance"]["source_digests"]) >= 3                 # requirements + contract + RM sections
    if seed is None:
        assert r["status"] == "PASS" and [x[2] for x in r["results"]] == ["HSE_ENABLE", "HSE_TIMEOUT", "HSE_NULL"], r
        assert V.v_oracle(ws)["status"] == "PASS"
    else:
        assert r["status"] == "FAIL" and any(x[3] == "FAIL" for x in r["results"]), (seed, r)


@needs_cc
def test_code_that_breaks_the_interface_contract_fails_the_oracle_not_silently(ws):
    (ws / "software/hal/stm32n6xx_hal_rcc.h").write_text(HAL_H.replace("osc_config_t", "oscillator_config_t"))
    (ws / "software/hal/stm32n6xx_hal_rcc.c").write_text(HAL_C.replace("osc_config_t", "oscillator_config_t"))
    v = V.v_oracle(ws)
    assert v["status"] == "FAIL" and any(f.startswith("ORACLE_BUILD_FAILED") for f in v["findings"])
