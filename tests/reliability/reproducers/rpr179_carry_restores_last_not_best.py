"""RPR-179 (owner lane, Omniverse2, 2026-11-07, L90Z): L90Z's robot runs reached 24/24 tests and 22/24 requirements at
09:56:59; later edits in the same attempt (invented register names ll_crc_regs, LL_CRC_POL_OFFSET) broke the build.
The V18 carry copied the attempt's current files, so the next retry would have started from the broken state.

Scenario: first run 24/24, files then broken and rerun 2/24, both on record.
Symptom: the retry receives the broken last files instead of the 24/24 run's files."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

SIG = "a SWE.6 retry restores the attempt's last broken tests instead of its best robot run"

# Scenario: one earlier attempt whose first robot run passed 24/24 and whose later edit broke the build (2/24).
TESTS = "software/tests/software"
GOOD = {"scn_crc_init.c": b"/* good scenario */\nint scn(void){return 0;}\n",
        "test_crc_requirements.robot": b"*** Test Cases ***\nGood\n    Log    good\n"}
BROKEN = {"scn_crc_init.c": b"/* broken: invented register ll_crc_regs */\nint scn(void){return ll_crc_regs;}\n",
          "test_crc_requirements.robot": b"*** Test Cases ***\nBroken\n    Log    broken\n"}


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def build(root: Path):
    orders = ["WO-RPR-CARRY-A", "WO-RPR-CARRY-B"]
    ws = root / orders[0] / "workspace"
    (ws / TESTS).mkdir(parents=True)
    (ws / "evidence").mkdir()
    (ws / ".forge-run/test-snapshots").mkdir(parents=True)
    results, integrity = [], []
    for at, files, summary in (("2026-11-07T09:56:59Z", GOOD, "robot: 24/24 tests passed; 22/24 requirements verified"),
                               ("2026-11-07T10:20:00Z", BROKEN, "robot: 2/24 tests passed; 1/24 requirements verified")):
        for data in files.values():
            (ws / ".forge-run/test-snapshots" / _sha(data)).write_bytes(data)
        results.append({"op": "run_robot", "phase": "SWE.6", "ts_utc": at, "result": {"summary": summary}})
        integrity.append({"op": "run_robot", "phase": "SWE.6", "ts_utc": at,
                          "files": {f"{TESTS}/{n}": _sha(d) for n, d in files.items()}})
    for name, data in BROKEN.items():
        (ws / TESTS / name).write_bytes(data)
    (ws / "evidence/tool-results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in results))
    (ws / "evidence/test-integrity.jsonl").write_text("".join(json.dumps(r) + "\n" for r in integrity))
    target = root / orders[1] / "workspace"
    target.mkdir(parents=True)
    return orders, target


def main() -> int:
    from forge_factory import attempt_carry
    with tempfile.TemporaryDirectory() as td:
        orders, target = build(Path(td))
        carried = attempt_carry.install(target, orders[1], orders, Path(td))
        if not carried:
            print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:nothing carried")
            return 2
        got = {n: (target / TESTS / n).read_bytes() for n in GOOD if (target / TESTS / n).is_file()}
        if got == BROKEN:
            print(f"SYMPTOM_PRESENT:{SIG}")
            return 1
        if got != GOOD:
            print("REPRODUCER_ERROR:SCENARIO_NOT_REACHED:restored files are neither run")
            return 2
    print("SYMPTOM_ABSENT")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"REPRODUCER_ERROR:{type(exc).__name__}:{str(exc)[:160]}")
        sys.exit(2)
