"""RPR-129 (local run WO-F014-SWE3-CRCHAL-20261103-L27, Omniverse2, CRC HAL order 0014m on run/gen9 378aa68a,
2026-11-03): the SWE.3 author tagged its HAL code and wrote unit_specifications.md with `SWU-CRC_HAL` /
`USPEC-HAL-CRC-001` instead of the required `SWU-HAL-01` / `USPEC-HAL-01-01`. inspection/swtrace.check_units (strict
parse_units) found no unit and the deterministic rejection said only UNIT:NO_UNITS and UNIT:SWR_NOT_REFINED:...; it
never named the malformed ids or the required form, so the author repeated them and SWE.3 ended BLOCKED "STUCK:
identical deterministic rejection twice".

Scenario (synthetic HAL workspace in a scratch dir, no RM inputs): the L27 shape - a `## SWU-CRC_HAL` unit with
`**USPEC-HAL-CRC-001**` items in unit_specifications.md and the same ids in the code's @unit/@spec tags - through the
real check_units of the revision under test. Symptom: no finding names SWU-CRC_HAL and USPEC-HAL-CRC-001 together with
the required forms (SWU-HAL-01, USPEC-HAL-01-01). Controls: the parser stays strict (the malformed unit is not
accepted as a unit, UNIT:NO_UNITS stays); the same workspace with well-formed ids parses one unit and gets no
malformed-id finding (a loosened or noisy check is an error, not ABSENT)."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "malformed SWE.3 unit/spec ids are rejected only as NO_UNITS, without naming the ids or the required form"
MD = """# Software unit specifications

## {u}: CRC HAL calculation unit

- SWC: SWC_HAL
- Functions: HAL_CRC_Init
- Design: workproducts/SWE.3/detailed_design/{u}.puml
- **{s}** The unit HAL_CRC_Init shall write the configured polynomial to CRC_POL.POL. Traces: SWR-001
"""
CODE = """#include "stm32n6xx_hal_crc.h"
/**
 * @brief Initialise the calculation unit.
 * @unit {u}
 * @spec {s}
 */
hal_status_t HAL_CRC_Init(const hal_crc_config_t *p_config)
{{
    (void)p_config;
    return HAL_OK;
}}
"""
REQ = "- **SWR-001** When the CRC initialisation is requested, the CRC driver shall write CRC_POL.POL.\n"
ARCH = ("@startuml\ncomponent \"stm32n6xx_hal_crc\" as SWC_HAL <<SWC>>\nnote right of SWC_HAL\nAllocated: SWR-001\n"
        "end note\n@enduml\n")


def run(td: Path, u: str, s: str) -> tuple[list[str], int]:
    from forge_factory.inspection import swtrace

    ws = td / u
    files = {".forge-run/manifest.json": json.dumps({"layer": "HAL", "peripheral": "crc"}),
             swtrace.UNITS_MD: MD.format(u=u, s=s), "software/hal/stm32n6xx_hal_crc.c": CODE.format(u=u, s=s),
             swtrace.REQS: REQ, swtrace.ARCH: ARCH}
    for rel, text in files.items():
        (ws / rel).parent.mkdir(parents=True, exist_ok=True)
        (ws / rel).write_text(text)
    r = swtrace.check_units(ws, render=False, export=False)
    return r["major_findings"], len(r["units"])


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        bad, n_bad = run(Path(td), "SWU-CRC_HAL", "USPEC-HAL-CRC-001")
        good, n_good = run(Path(td), "SWU-HAL-01", "USPEC-HAL-01-01")
    if n_bad != 0 or "UNIT:NO_UNITS" not in bad:
        print(f"REPRODUCER_ERROR:CHECK_LOOSENED:the malformed unit was accepted ({n_bad} units)")
        return 2
    if n_good != 1 or "UNIT:NO_UNITS" in good or any("MALFORMED" in f for f in good):
        print(f"REPRODUCER_ERROR:SCENARIO_NOT_REACHED:well-formed control {n_good} units, findings {good[:3]}")
        return 2
    named = (any("SWU-CRC_HAL" in f and "SWU-HAL-01" in f for f in bad)
             and any("USPEC-HAL-CRC-001" in f and "USPEC-HAL-01-01" in f for f in bad))
    if not named:
        print(f"observed: {bad[:3]}")
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
