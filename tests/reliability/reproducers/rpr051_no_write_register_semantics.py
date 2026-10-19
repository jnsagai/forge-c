"""RPR-051 (HAL r164): a register-contract no_write effect naming RCC_CR.HSEON ('leave at reset value') mapped to
HAL_RCC_GPDMA1_Enable (writes RCC_AHB1ENR) became an oracle case demanding zero register accesses, so the independent
oracle failed a correct driver (ORACLE_FAIL:SWR-010/SWR-011 *_RESET_DEFAULT_PRESERVED)."""
import json
import os
import sys
import tempfile
from pathlib import Path

SIG = "no_write effect naming a register demands zero register accesses"


def main() -> int:
    root = Path(os.environ.get("FORGE_REPO_ROOT", "."))
    sys.path.insert(0, str(root / "factory/python/tests"))
    from forge_factory.assurance import oracle_gen
    from forge_factory.assurance import register_contract as RC
    from test_easa_m3_m4 import CR, SR  # RM0486 RCC_CR/RCC_SR section text used by the EASA tests

    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        files = {"inputs/sections/RM0486/14.10.1_RCC_CR.md": CR, "inputs/sections/RM0486/14.10.2_RCC_SR.md": SR,
                 RC.EFFECTS: json.dumps({"schema": "forge-c/register-effects/1", "effects": [
                     {"case": "HSE_RESET_DEFAULT_PRESERVED", "swr": "SWR-010", "register": "RCC_CR", "field": "HSEON",
                      "op": "no_write", "status": "HAL_OK"}]}),
                 RC.CALLS: json.dumps({"schema": "forge-c/api-calls/1", "calls": {"HSE_RESET_DEFAULT_PRESERVED": {
                     "function": "HAL_RCC_GPDMA1_Enable", "args": ["NULL"]}}})}
        for rel, text in files.items():
            (ws / rel).parent.mkdir(parents=True, exist_ok=True)
            (ws / rel).write_text(text)
        cases, _ = RC.cases(ws)
        src = oracle_gen.contract_source(cases, "stm32n6xx_hal_rcc.h") if cases else ""
    if not cases or "(shim_n == 0UL)" in src or "before[0U]" not in src:
        print(f"SYMPTOM_PRESENT:{SIG}")
        return 1
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
