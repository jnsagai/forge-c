"""Normal owner-authorized CODE/PC/SWE.3 protocol; public real-LL selector must accept its reviewed copy.

All inspections here are deterministic CONTROL oracles, never model/role or
production phase qualification. No candidate-private helper/test API is used.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

from forge_factory.inspection import defects, provided_changes as PC
from forge_factory.inspection.engine import PHASES, Store, load_checklist
from forge_factory.inspection.reqif_export import export
from forge_factory.workflow import provided_ll_unit as P

LL = 'software/ll/stm32n6xx_ll_wwdg.h'
CLAUSE = 'When writing a WWDG register, the WWDG driver shall preserve its reserved bits at their reset values.'


def write(ws, rel, data):
    path = ws / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data) if isinstance(data, dict) else data)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def approve(store, phase):
    baseline = store.freeze(phase, 'swe' + phase[-1] + '-author')
    verdicts = {c['id']: {'verdict': 'PASS', 'evidence_refs': ['CONTROL-ONLY']} for c in load_checklist(phase)['checks']}
    report = store.record_inspection(phase, 'swe' + phase[-1] + '-inspector', baseline['baseline_id'], verdicts)
    if report['verdict'] != 'PASS' or store.gate(phase)['decision'] != 'PASS':
        raise RuntimeError('NORMAL_CONTROL_APPROVAL_DID_NOT_PASS:' + json.dumps(report.get('findings')))
    return baseline


def main():
    ws = Path(os.environ['FORGE_STATE_DIR']) / 'workorders/WO-RPR166/workspace'
    vendor = write(ws, 'inputs/vendor/include/stm32n6xx.h', '#ifndef DEVICE_H\n#define DEVICE_H\n#include <stdint.h>\n'
        'typedef struct { volatile uint32_t CR, CFR, SR; } WWDG_TypeDef;\n#define WWDG ((WWDG_TypeDef *)0x50002C00U)\n'
        '#define WWDG_SR_EWIF 1U\n#endif\n')
    original = '#ifndef STM32N6XX_LL_WWDG_H\n#define STM32N6XX_LL_WWDG_H\n#include "stm32n6xx.h"\n'
    original += 'static inline void LL_WWDG_ClearFlag_EWKUP(WWDG_TypeDef *x) { x->SR = ~WWDG_SR_EWIF; }\n'
    original += '#endif /* STM32N6XX_LL_WWDG_H */\n'
    header = write(ws, LL, original)
    write(ws, 'software/hal/stm32n6xx_hal_wwdg.h', '#ifndef STM32N6XX_HAL_WWDG_H\n#define STM32N6XX_HAL_WWDG_H\n'
        '#include "stm32n6xx_ll_wwdg.h"\ntypedef enum { HAL_OK, HAL_ERROR } hal_status_t;\n'
        'hal_status_t HAL_WWDG_ClearEarlyWakeupFlag(void);\n#endif /* STM32N6XX_HAL_WWDG_H */\n')
    write(ws, 'software/hal/stm32n6xx_hal_wwdg.c', '#include "stm32n6xx_hal_wwdg.h"\n'
        'hal_status_t HAL_WWDG_ClearEarlyWakeupFlag(void) { LL_WWDG_ClearFlag_EWKUP(WWDG); return HAL_OK; }\n')
    manifest = {'work_order': 'WO-RPR166', 'layer': 'HAL', 'peripheral': 'wwdg',
        'unit_verification': 'uspec-gtest-v1', 'hal_unit_isolation': 'll-fake-v1',
        'provided': [{'path': LL, 'role': 'provided_ll_driver', 'sha256': sha(header)}],
        'provided_build': {'style': 'cmsis', 'files': [{'path': vendor.relative_to(ws).as_posix(), 'sha256': sha(vendor)}]}}
    write(ws, '.forge-run/manifest.json', manifest)
    manifest_sha = sha(ws / '.forge-run/manifest.json')
    PC.save_original(ws, LL, header.read_bytes())
    write(ws, 'workproducts/SWE.1/software_requirements.md', '- **SWR-034** ' + CLAUSE + '\n')
    write(ws, 'traceability/requirements_to_tests.csv', 'requirement_id,test_id,test_file\nSWR-034,UT-021,target\n')
    write(ws, 'configuration/system_names.json', json.dumps(['WWDG driver']))
    if export(ws)['verdict'] != 'PASS':
        raise RuntimeError('CONTROL_REQIF_FAILED')
    write(ws, 'workproducts/SWE.2/software_architecture.md', '# Architecture\n## Components\nHAL, LL\n'
        '## Interfaces\nHAL_WWDG_ClearEarlyWakeupFlag\n## Requirement allocation\n| SWR | Function |\n|---|---|\n'
        '| SWR-034 | HAL_WWDG_ClearEarlyWakeupFlag |\n## Register table\n| Name | Offset |\n|---|---|\n| WWDG_SR | 0x8 |\n')
    write(ws, 'workproducts/SWE.2/architecture_static.puml', '@startuml\ncomponent "stm32n6xx_hal_wwdg" as HAL\n'
        'component "stm32n6xx_ll_wwdg" as LL\nHAL --> LL\n@enduml\n')
    write(ws, 'workproducts/SWE.2/architecture_dynamic.puml', '@startuml\nparticipant Caller\nparticipant HAL\n'
        'Caller -> HAL : HAL_WWDG_ClearEarlyWakeupFlag()\nHAL --> Caller : HAL_OK\n@enduml\n')
    write(ws, 'workproducts/SWE.3/detailed_design.md', '# CONTROL\nDelegate to provided LL.\n')
    store = Store(ws)
    for phase in PHASES[:3]:
        approve(store, phase)
    record = defects.report(ws, detected_phase='SWE.4', reported_by='swe4-author', kind='CODE',
        summary='CONTROL UT-021 USPEC-HAL-04-03: ' + LL + ' writes SR31:1 as1 contrary to SWR-034 WHEN WRITING.',
        requirement_ids=['SWR-034'], test_files=[], evidence_refs=[LL + ':4'], requirement_quote=CLAUSE)
    if defects.take_upstream(ws, 'SWE.3')[0]['id'] != record['id'] or not PC.allowed(ws, LL):
        raise RuntimeError('NORMAL_CODE_CORRECTION_NOT_AUTHORIZED')
    PC.unlock(ws)
    header.write_text(original.replace('x->SR = ~WWDG_SR_EWIF', 'x->SR = 0U'))
    if PC.findings(ws):
        raise RuntimeError('NORMAL_PROVIDED_REPORT_REJECTED')
    baseline = approve(store, 'SWE.3')
    if defects.mark_fixed(ws, 'SWE.3', baseline['baseline_id']) != [record['id']]:
        raise RuntimeError('NORMAL_FIX_EVENT_MISSING')
    report = PC.report(ws)
    if (report['files'][0]['status'] != 'CHANGED_LINKED' or not report['human_review_required']
            or sha(ws / '.forge-run/manifest.json') != manifest_sha
            or sha(ws / PC.ORIGINALS / LL) != manifest['provided'][0]['sha256']):
        raise RuntimeError('CONTROL_ORIGINAL_APPROVAL_OR_DIFF_NOT_PRESERVED')
    print(json.dumps({'scope': 'NORMAL_PROTOCOL_CONTROL_ONLY', 'phase3_gate': store.gate('SWE.3')['decision'],
                      'provided_status': report['files'][0]['status'], 'human_review_required': True}, sort_keys=True))
    try:
        accepted = P.headers(ws)
    except ValueError as exc:
        if 'PROVIDED_LL_UNIT_INPUT_CHANGED' not in str(exc):
            raise
        print('SYMPTOM_PRESENT:reviewed provided CODE correction is refused as an unauthorized input change')
        return 1
    if accepted != [header] or header.read_text() != original.replace('x->SR = ~WWDG_SR_EWIF', 'x->SR = 0U'):
        raise RuntimeError('PUBLIC_SELECTOR_DID_NOT_BIND_CORRECTED_COPY')
    # Unlinked and missing-approval contexts still refuse; acceptance is not a hash bypass.
    record_path = ws / '.forge-run/defects' / (record['id'] + '.json')
    saved = record_path.read_bytes()
    record_path.unlink()
    try:
        P.headers(ws)
    except ValueError:
        pass
    else:
        raise RuntimeError('UNLINKED_CORRECTION_WAS_ACCEPTED')
    record_path.write_bytes(saved)
    if P.headers(ws) != [header]:
        raise RuntimeError('VALID_CONTEXT_NOT_RESTORED')
    print('SYMPTOM_ABSENT')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print('ERROR:' + type(exc).__name__ + ':' + str(exc)[:500])
        sys.exit(2)
