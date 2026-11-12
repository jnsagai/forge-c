#!/usr/bin/env python3
"""Independent normal declaration/plan oracle. No live state, model, parser patch or caller tests."""
import copy
import json
import tempfile
from pathlib import Path
from forge_factory.common import sha256_file
from forge_factory.workflow import unit_target_observation as O

FUNCTION = "HAL_WWDG_ClearEarlyWakeupFlag"
BEHAVIOUR = "Preserve other writable fields and reserved bits at reset values during writes."
SWR033 = "When writing a WWDG field, the WWDG driver shall preserve the other writable fields in that register except for fields explicitly changed by the requested operation as the driver's defined behaviour."
SWR034 = "When writing a WWDG register, the WWDG driver shall preserve its reserved bits at their reset values."
CASE = {"schema": "forge-c/swe4-wwdg-target-observation/1", "ut": "UT-023", "uspec": "USPEC-HAL-04-03", "function": FUNCTION, "scenario": "wwdg-ewif-clear-v1"}

def write(ws, rel, data):
    p = ws / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data) if isinstance(data, dict) else data)
    return p

def fixture(ws):
    vendor = write(ws, "inputs/vendor/include/stm32n6xx.h", "#include <stdint.h>\ntypedef struct { volatile uint32_t CR, CFR, SR; } WWDG_TypeDef;\n#define WWDG ((WWDG_TypeDef *)0x50002C00U)\n#define WWDG_CR_WDGA 0x80U\n#define WWDG_SR_EWIF 1U\n")
    ll = write(ws, "software/ll/stm32n6xx_ll_wwdg.h", '#include "stm32n6xx.h"\nstatic inline void LL_WWDG_ClearFlag_EWKUP(WWDG_TypeDef *x) { x->SR = 0U; }\n')
    write(ws, "software/hal/stm32n6xx_hal_wwdg.h", '#include "stm32n6xx_ll_wwdg.h"\ntypedef enum { HAL_OK, HAL_ERROR } hal_status_t;\nhal_status_t HAL_WWDG_ClearEarlyWakeupFlag(void);\n')
    write(ws, "software/hal/stm32n6xx_hal_wwdg.c", '#include "stm32n6xx_hal_wwdg.h"\nhal_status_t HAL_WWDG_ClearEarlyWakeupFlag(void) { LL_WWDG_ClearFlag_EWKUP(WWDG); return HAL_OK; }\n')
    write(ws, ".forge-run/manifest.json", {"layer": "HAL", "peripheral": "wwdg", "provided": [{"path": "software/ll/stm32n6xx_ll_wwdg.h", "sha256": sha256_file(ll), "role": "provided_ll_driver"}], "provided_build": {"style": "cmsis", "files": [{"path": "inputs/vendor/include/stm32n6xx.h", "sha256": sha256_file(vendor)}]}})
    write(ws, "workproducts/SWE.1/software_requirements.md", "- **SWR-033** " + SWR033 + "\n- **SWR-034** " + SWR034 + "\n")
    unit = write(ws, "workproducts/SWE.3/unit_specifications.md", "## SWU-HAL-04: Flag clear\n- SWC: SWC_HAL\n- Functions: " + FUNCTION + "\n- **USPEC-HAL-04-01** Write 0 to EWIF and return HAL_OK. Traces: SWR-014, SWR-015, SWR-035, SWR-036\n- **USPEC-HAL-04-03** " + BEHAVIOUR + " Traces: SWR-033, SWR-034\n")
    write(ws, "workproducts/SWE.4/unit_test_plan.json", {"unit_specification": {"path": "workproducts/SWE.3/unit_specifications.md", "sha256": sha256_file(unit)}, "tasks": [{"ut": "UT-021", "uspec": "USPEC-HAL-04-01", "functions": [FUNCTION], "behaviour": "Write 0 to EWIF and return HAL_OK.", "swrs": ["SWR-014", "SWR-015", "SWR-035", "SWR-036"], "unit": "SWU-HAL-04", "kind": "requirement", "test_kind": "positive"}, {"ut": "UT-023", "uspec": "USPEC-HAL-04-03", "functions": [FUNCTION], "behaviour": BEHAVIOUR, "swrs": ["SWR-033", "SWR-034"], "unit": "SWU-HAL-04", "kind": "requirement", "test_kind": "negative"}], "closure": []})
    write(ws, "workproducts/SWE.2/api_calls.json", {"calls": {"CLEAR": {"function": FUNCTION, "args": []}}})
    write(ws, "software/tests/unit/target_observations.json", CASE)

def main():
    with tempfile.TemporaryDirectory(prefix="rpr168-") as td:
        ws = Path(td)
        fixture(ws)
        try:
            result = O.declaration(ws)
        except ValueError as exc:
            if str(exc) not in ("TARGET_OBSERVATION_SCOPE_OR_CASE_INVALID", "TARGET_OBSERVATION_FROZEN_PREDICATE_UNSUPPORTED"):
                raise
            print("SYMPTOM_PRESENT:frozen approved preservation case cannot bind its actual plan identifiers")
            return 1
        if result != CASE:
            raise RuntimeError("VALIDATED_DECLARATION_IDENTITY_LOST")
        tests = O.expected_tests(ws)
        if len(tests) != 1 or tests[0]["id"] != "UT-023" or tests[0]["uspec"] != "USPEC-HAL-04-03" or tests[0]["status"] != "DECLARED_NOT_EXECUTED":
            raise RuntimeError("WRONG_OR_FALSE_EXECUTION_CREDIT")
        for bad in ({**CASE, "ut": "UT-021"}, {**CASE, "uspec": "USPEC-HAL-04-01"}, {**CASE, "function": "HAL_WWDG_Refresh"}):
            write(ws, "software/tests/unit/target_observations.json", bad)
            try:
                O.declaration(ws)
            except ValueError:
                pass
            else:
                raise RuntimeError("UNRELATED_FROZEN_OBLIGATION_ACCEPTED")
        print("SYMPTOM_ABSENT")
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
