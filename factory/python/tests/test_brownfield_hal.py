"""Feature 008 - HAL delivery on a provided LL (b002, 2026-10-20): register effects of the delivered HAL come from
the LL functions it calls in the PROVIDED header; conformance must resolve them (18 false findings in b002) and
must still find the seeded rollback defect (HSE ready timeout does not clear HSEON)."""
import json

from forge_factory.brownfield import conformance as C
from forge_factory.common import REPO_ROOT, sha256_bytes

HAL_C = (REPO_ROOT / "examples/0008b-rcc-hal-delivered/delivery/stm32n6xx_hal_rcc.c").read_text()
HAL_H = (REPO_ROOT / "examples/0008b-rcc-hal-delivered/delivery/stm32n6xx_hal_rcc.h").read_text()
LL_H = (REPO_ROOT / "examples/0008a-rcc-ll-delivered/delivery/stm32n6xx_ll_rcc.h").read_text()
FIXED_C = HAL_C.replace("    if (ready == 0U)\n    {\n      status = HAL_TIMEOUT;",
                        "    if (ready == 0U)\n    {\n      LL_RCC_HSE_Disable();\n      status = HAL_TIMEOUT;", 1)
OSC = "&(const hal_rcc_osc_config_t){ .oscillator = HAL_RCC_OSC_HSE }"
REQ = ("- **SWR-002** When HSE enable is requested, the RCC driver shall set RCC_CR.HSEON.\n"
       "- **SWR-009** If RCC_SR.HSERDY stays 0 for the whole timeout, the RCC driver shall clear RCC_CR.HSEON.\n"
       "- **SWR-008** While no RCC operation has been requested after reset, the RCC driver shall leave RCC_CR.HSEON "
       "at its reset value 0 without writing these registers.\n")


def _ws(tmp_path, hal_c):
    ws = tmp_path / "ws"
    files = {"software/hal/stm32n6xx_hal_rcc.c": hal_c, "software/hal/stm32n6xx_hal_rcc.h": HAL_H,
             "software/ll/stm32n6xx_ll_rcc.h": LL_H,
             "workproducts/SWE.1/software_requirements.md": REQ,
             "workproducts/SWE.1/register_effects.json": json.dumps({"effects": [
                 {"case": "HSE_ENABLE", "swr": "SWR-002", "register": "RCC_CR", "field": "HSEON", "op": "set"},
                 {"case": "HSE_READY_TIMEOUT", "swr": "SWR-009", "register": "RCC_CR", "field": "HSEON", "op": "clear"},
                 {"case": "HSE_INVALID_NULL", "swr": "SWR-002", "op": "no_write"},
                 {"case": "STARTUP_HSE", "swr": "SWR-008", "register": "RCC_CR", "field": "HSEON", "op": "no_write"}]}),
             "workproducts/SWE.2/api_calls.json": json.dumps({"calls": {
                 "HSE_ENABLE": {"function": "HAL_RCC_HSE_Enable", "args": [OSC, "{timeout}"]},
                 "HSE_READY_TIMEOUT": {"function": "HAL_RCC_HSE_Enable", "args": [OSC, "{timeout}"]},
                 "HSE_INVALID_NULL": {"function": "HAL_RCC_HSE_Enable", "args": ["NULL", "{timeout}"]},
                 "STARTUP_HSE": {"function": "NONE", "args": []}}}),
             ".forge-run/delivery/scope.json": json.dumps({"functions": [
                 {"name": "HAL_RCC_HSE_Enable", "file": "software/hal/stm32n6xx_hal_rcc.c", "line": 55}]})}
    for rel, t in files.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(t)
    (ws / ".forge-run/manifest.json").write_text(json.dumps({
        "work_order": "T", "code_mode": "FIX_ALLOWED", "delivery": {"build": {"style": "forge"}},
        "delivered": [{"path": p, "sha256": sha256_bytes(files[p].encode()), "role": "delivered_code"}
                      for p in ("software/hal/stm32n6xx_hal_rcc.c", "software/hal/stm32n6xx_hal_rcc.h")],
        "provided": [{"path": "software/ll/stm32n6xx_ll_rcc.h", "role": "provided_ll_driver"}]}))
    return ws


def test_seeded_rollback_defect_is_the_only_finding(tmp_path):
    r = C.check(_ws(tmp_path, HAL_C), "SWE.3", write=False)
    assert [(f["kind"], f["function"], f["requirement"]) for f in r["findings"]] == \
        [("CONTRADICTION", "HAL_RCC_HSE_Enable", "SWR-009")]


def test_corrected_hal_is_conformant(tmp_path):
    assert C.check(_ws(tmp_path, FIXED_C), "SWE.3", write=False) == {"status": "CONFORMANT", "findings": [],
                                                                       "issues": []}
