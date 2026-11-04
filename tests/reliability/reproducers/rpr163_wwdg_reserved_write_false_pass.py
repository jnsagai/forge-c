"""Actual existing Renode model: reserved WRITE values cannot be inferred from zero readback.

No live workspace, model inference, product-code correction or requirement waiver.
The two LL origins are separate fresh CONTROL inputs, hash-bound before execution.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

from forge_factory.mcp.sdk import ToolContext
from forge_factory.workflow import unit_target_observation as O


def write(ws, rel, value):
    p = ws / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value) if isinstance(value, dict) else value)
    return p


def execute(name, statement):
    ws = Path(os.environ['FORGE_STATE_DIR']) / ('rpr163-' + name)
    vendor = write(ws, 'inputs/vendor/include/stm32n6xx.h', '''#include <stdint.h>
typedef struct { volatile uint32_t CR, CFR, SR; } WWDG_TypeDef;
#define WWDG ((WWDG_TypeDef *)0x50002C00U)
#define WWDG_CR_WDGA 0x80U
#define WWDG_SR_EWIF 1U
''')
    ll = write(ws, 'software/ll/stm32n6xx_ll_wwdg.h', '#include "stm32n6xx.h"\n'
        'static inline void LL_WWDG_ClearFlag_EWKUP(WWDG_TypeDef *x) { ' + statement + '; }\n')
    hal = write(ws, 'software/hal/stm32n6xx_hal_wwdg.c', '#include "stm32n6xx_hal_wwdg.h"\n'
        'hal_status_t HAL_WWDG_ClearEarlyWakeupFlag(void) { LL_WWDG_ClearFlag_EWKUP(WWDG); return HAL_OK; }\n')
    write(ws, 'software/hal/stm32n6xx_hal_wwdg.h', '#include "stm32n6xx_ll_wwdg.h"\n'
        'typedef enum { HAL_OK, HAL_ERROR } hal_status_t;\nhal_status_t HAL_WWDG_ClearEarlyWakeupFlag(void);\n')
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    write(ws, '.forge-run/manifest.json', {'work_order': 'WO-RPR163', 'layer': 'HAL', 'peripheral': 'wwdg',
        'provided': [{'path': ll.relative_to(ws).as_posix(), 'role': 'provided_ll_driver', 'sha256': sha(ll)}],
        'provided_build': {'style': 'cmsis', 'files': [{'path': vendor.relative_to(ws).as_posix(), 'sha256': sha(vendor)}]}})
    write(ws, 'workproducts/SWE.1/software_requirements.md', '- **SWR-034** ' + O.SWR + '\n')
    unit = write(ws, 'workproducts/SWE.3/unit_specifications.md', 'Frozen CONTROL specification.\n')
    write(ws, 'workproducts/SWE.4/unit_test_plan.json', {'tasks': [{'ut': 'UT-021', 'uspec': 'USPEC-HAL-04-03',
        'functions': [O.FUNCTION], 'behaviour': O.BEHAVIOUR, 'swrs': ['SWR-033', 'SWR-034']}],
        'unit_specification': {'path': unit.relative_to(ws).as_posix(), 'sha256': sha(unit)}})
    write(ws, 'workproducts/SWE.2/api_calls.json', {'calls': {'CLEAR': {'function': O.FUNCTION, 'args': []}}})
    write(ws, O.DECLARATION, O.CASE)
    original = {p.relative_to(ws).as_posix(): sha(p) for p in ws.rglob('*') if p.is_file()}
    ctx = ToolContext('forge-tests-mcp', 'run_unit', 'swe4-author', 'SWE.4', ws, 'RPR163-CONTROL')
    fragment = O.run(ctx)
    if not fragment or not fragment.get('metrics', {}).get(O.METRIC):
        raise RuntimeError('NO_ACTUAL_SEALED_TARGET_MEASUREMENT:' + str(fragment.get('issues') if fragment else None))
    result = {k: fragment[k] for k in ('status', 'metrics', 'artifact_refs')}
    result['provenance'] = {'invocation_id': ctx.invocation_id}
    test = O.verify(ws, result)[0]
    obs = test['observed']
    expected = 0xfffffffe if name == 'complement' else 0
    if not (obs['sr_before'] == 1 and obs['sr_after'] == 0 and obs['actual_hal_status_matches_HAL_OK']
            and obs['call_writes'] == [{'offset': 8, 'value': expected}]):
        raise RuntimeError('CONTROL_DID_NOT_REACH_EXACT_COUNTEREXAMPLE:' + json.dumps(obs))
    if any(sha(ws / rel) != value for rel, value in original.items()):
        raise RuntimeError('CONTROL_SOURCE_CHANGED')
    print(json.dumps({'case': name, 'status': fragment['status'], 'test': test, 'HAL_sha256': sha(hal),
                      'LL_sha256': sha(ll)}, sort_keys=True))
    return fragment, test


def main():
    fragment, test = execute('complement', 'x->SR = ~WWDG_SR_EWIF')
    if fragment['status'] == test['status'] == 'PASS':
        print('SYMPTOM_PRESENT:reserved SR write credited as full WWDG unit verification')
        return 1
    if not (fragment['status'] == test['status'] == 'FAIL'
            and test['observed'].get('sr_reserved_write_values_valid') is False):
        raise RuntimeError('FAILURE_DID_NOT_ESTABLISH_RESERVED_WRITE_PREDICATE')
    good, control = execute('zero', 'x->SR = 0U')
    if not (good['status'] == control['status'] == 'PASS'
            and control['observed'].get('sr_reserved_write_values_valid') is True):
        raise RuntimeError('POSITIVE_CONTROL_NOT_ACTUALLY_PASSING')
    print('SYMPTOM_ABSENT')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('ERROR:' + type(exc).__name__ + ':' + str(exc)[:350])
        sys.exit(2)
