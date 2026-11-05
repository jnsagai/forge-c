"""RPR-096 (Fabro run WO-F014-SWE6-OBL-20261101-L4, Omniverse2, 2026-11-01): CRC IDR greenfield SWE.6 resumed from
WO-F014-SWE5-OBL-20261101-L4. SWR-003/SWR-005 concern every CRC register, but the scenario packet's generated defines cover
only the in-scope CRC_IDR and the CRC target model named reset values by register only. The author guessed the other
offsets (CRC_POL at 0x008, CRC_CR at 0x00C; the behavioural model has CRC_CR 0x008 and CRC_POL 0x014), TCHECK 3 failed
on target twice and the order was cancelled.

Scenario: the real SWE.6 scenario-packet source of the target model (lrtx/swe5._p on a CRC work order) and the register
offsets the behavioural model implements (factory/sim/stm32n6/crc_model.py). Symptom: the target model text states no
offset for a register the behavioural model implements."""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

SIG = "the CRC target model given to the SWE.6 scenario author states no offset for registers outside the generated defines"
NAMES = {0x000: "CRC_DR", 0x004: "CRC_IDR", 0x008: "CRC_CR", 0x010: "CRC_INIT", 0x014: "CRC_POL"}


def main() -> int:
    root = Path(os.environ.get("FORGE_REPO_ROOT", "."))
    model = (root / "factory/sim/stm32n6/crc_model.py").read_text()
    m = re.search(r"regs = \{([^}]*)\}", model)
    if not m:
        print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:behavioural CRC model register table not found")
        return 2
    offsets = {0x000} | {int(x, 16) for x in re.findall(r"(0x[0-9A-Fa-f]+)\s*:", m.group(1))}
    from forge_factory.lrtx import swe5
    with tempfile.TemporaryDirectory() as td:
        ws = Path(td)
        (ws / ".forge-run").mkdir()
        (ws / ".forge-run/manifest.json").write_text(json.dumps({"work_order": "WO-RPR096", "layer": "LL", "peripheral": "crc"}))
        swe5._ident = lambda _ws: {"block": "ll_crc_regs", "pfx": "CRC"}
        text = " ".join(str(swe5._p(ws)["prompt"].get("target_model") or "").split())
    missing = [NAMES.get(o, hex(o)) for o in sorted(offsets) if not re.search(rf"{NAMES.get(o, 'X')}\s+0x0*{o:X}\b", text, re.I)]
    if missing:
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
