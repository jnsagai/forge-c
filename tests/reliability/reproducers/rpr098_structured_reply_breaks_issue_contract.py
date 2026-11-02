"""RPR-098 (Fabro runs WO-F014-SWE2-IWDG-20261101-01 and WO-F014-SWE4-IWDG-20261101-L1, Omniverse2, 2026-11-01): the
structured runner cut reply issues to 300 characters while the protected agent-output contract
(specs/002-self-healing-factory/contracts/agent-output.schema.json) allows 120; every long rejection also failed
AGENT_OUTPUT_SCHEMA at the author gate and the gate kept 120-character fragments.

Scenario: a structured author reply with one validator finding of 230 characters, through the real visit.reply and the
real agent-output parser. Symptom: the reply violates the agent-output contract."""
import json
import sys
import tempfile
from pathlib import Path

SIG = "a structured author reply with an issue longer than 120 characters violates the agent-output contract"
LONG = "test:UT-002: call to LL_crc_Read_IDR: a test calls only ut_reset_regs, CHECK and LL_CRC_Read_IDR " + "x" * 130


def main() -> int:
    from forge_factory.contracts.agent_output import parse
    from forge_factory.lrtx import visit as V
    with tempfile.TemporaryDirectory() as td:
        doc = V.reply(Path(td), "SWE.4", "FAILED", [LONG])
    res = parse(json.dumps(doc))
    if "AGENT_OUTPUT_SCHEMA" in (res.errors or []) or not res.ok:
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
