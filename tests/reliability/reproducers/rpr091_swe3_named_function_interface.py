"""RPR-091 (Fabro run WO-F014-SWE3-OBL-20261101-L1, Omniverse2, 2026-11-01): CRC IDR greenfield SWE.3 resumed from a
structured SWE.2 that answered in the named-function shape (structured.swe2_named_functions: named_functions +
other_functions). The structured SWE.3 author found no units (UNIT:NO_UNITS) and the route stopped it as STUCK.

Scenario: a workspace whose VALID SWE.2 interface checkpoint is in the named-function shape. Symptom: structured SWE.3
derives no code units from it."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "structured SWE.3 derives no code units from a named-function SWE.2 interface"
DOC = {"named_functions": {"LL_CRC_Write_IDR": {"fields": ["CRC_IDR.IDR"], "operation": "Writes the 32-bit value to CRC_IDR.IDR.",
                                                "params": [{"name": "in_data", "type": "uint32_t"}], "returns": "void"},
                           "LL_CRC_Read_IDR": {"fields": ["CRC_IDR.IDR"], "operation": "Returns CRC_IDR.IDR.", "params": [],
                                               "returns": "uint32_t"}},
       "other_functions": [],
       "allocation": [{"swr": "SWR-001", "functions": ["LL_CRC_Write_IDR"], "responsibility": "write"},
                      {"swr": "SWR-002", "functions": ["LL_CRC_Read_IDR"], "responsibility": "read"}],
       "calls": [{"case": "WRITE_IDR", "function": "LL_CRC_Write_IDR", "args": ["0xFFFFFFFFU"]},
                 {"case": "READ_IDR", "function": "LL_CRC_Read_IDR", "args": []}]}


def main() -> int:
    from forge_factory.lrtx import swe3
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        p = ws / ".forge-run/lrtx/SWE.2/packets/interfaces.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({"task": "interfaces", "status": "VALID", "doc": DOC}))
        (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": "WO-RPR091", "layer": "LL", "peripheral": "crc"}))
        try:
            us = swe3.units(ws)
        except (KeyError, TypeError):
            us = []
    if [u["function"]["name"] for u in us] == ["LL_CRC_Write_IDR", "LL_CRC_Read_IDR"]:
        print("SYMPTOM_ABSENT")
        return 0
    print(f"SYMPTOM_PRESENT:{SIG}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
